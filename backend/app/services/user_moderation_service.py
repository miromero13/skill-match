from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SkillMatchException
from app.models.match import Match
from app.models.match_proposal import MatchProposal
from app.models.user import User, UserRole
from app.models.user_block import UserBlock
from app.models.user_report import ReportStatus, UserReport
from app.schemas.user_moderation import (
    BlockedUserItem,
    ReportUserRequest,
    ReportUserResponse,
    UserSafetyStatusResponse,
)


class UserModerationService:
    """Servicio de dominio para bloqueo preventivo y reporte formal a moderación (HU-26 / RF-MAT-14, RF-NOT-06)."""

    @classmethod
    async def list_blocked_users(
        cls, db: AsyncSession, blocker_id: UUID
    ) -> tuple[list[BlockedUserItem], int]:
        """Obtiene la lista de usuarios bloqueados por el miembro solicitante."""
        stmt = (
            select(UserBlock, User)
            .join(User, UserBlock.blocked_id == User.id)
            .where(UserBlock.blocker_id == blocker_id)
            .order_by(UserBlock.created_at.desc())
        )
        result = await db.execute(stmt)
        rows = result.all()

        items = [
            BlockedUserItem(
                block_id=block.id,
                user_id=user.id,
                full_name=user.full_name,
                avatar_url=user.avatar_url,
                reason=block.reason,
                blocked_at=block.created_at,
            )
            for block, user in rows
        ]
        return items, len(items)

    @classmethod
    async def block_user(
        cls,
        db: AsyncSession,
        blocker_id: UUID,
        target_id: UUID,
        reason: str | None = None,
        notes: str | None = None,
    ) -> BlockedUserItem:
        """
        Bloquea preventivamente a un usuario, anulando automáticamente coincidencias y propuestas activas (RF-MAT-14).
        """
        if blocker_id == target_id:
            raise SkillMatchException("No puedes bloquear tu propia cuenta de usuario.", statuscode=400)

        target_user = await db.get(User, target_id)
        if not target_user or target_user.role != UserRole.MEMBER:
            raise SkillMatchException("Recurso no encontrado", statuscode=404)

        # 1. Registrar o actualizar el bloqueo
        existing_block = await db.scalar(
            select(UserBlock).where(
                UserBlock.blocker_id == blocker_id,
                UserBlock.blocked_id == target_id,
            )
        )

        if not existing_block:
            block = UserBlock(
                blocker_id=blocker_id,
                blocked_id=target_id,
                reason=reason,
                notes=notes,
            )
            db.add(block)
            await db.flush()
        else:
            block = existing_block
            if reason:
                block.reason = reason
            if notes:
                block.notes = notes
            await db.flush()

        # 2. Anulación automática de coincidencias y propuestas previas bilaterales (RF-MAT-14)
        min_id, max_id = sorted([blocker_id, target_id])
        matches = list(
            (
                await db.scalars(
                    select(Match).where(
                        Match.member_a_id == min_id,
                        Match.member_b_id == max_id,
                    )
                )
            ).all()
        )

        for match in matches:
            match.status = "blocked"
            # Cancelar propuestas de trueque pendientes asociadas marcándolas como declined
            proposals = list(
                (
                    await db.scalars(
                        select(MatchProposal).where(
                            MatchProposal.match_id == match.id,
                            MatchProposal.status == "pending",
                        )
                    )
                ).all()
            )
            for proposal in proposals:
                proposal.status = "declined"

        await db.flush()

        return BlockedUserItem(
            block_id=block.id,
            user_id=target_user.id,
            full_name=target_user.full_name,
            avatar_url=target_user.avatar_url,
            reason=block.reason,
            blocked_at=block.created_at,
        )

    @classmethod
    async def unblock_user(
        cls, db: AsyncSession, blocker_id: UUID, target_id: UUID
    ) -> None:
        """Desbloquea a un usuario previamente bloqueado."""
        if blocker_id == target_id:
            raise SkillMatchException("No puedes desbloquear tu propia cuenta.", statuscode=400)

        existing_block = await db.scalar(
            select(UserBlock).where(
                UserBlock.blocker_id == blocker_id,
                UserBlock.blocked_id == target_id,
            )
        )

        if not existing_block:
            raise SkillMatchException("El usuario no se encuentra bloqueado.", statuscode=404)

        await db.delete(existing_block)
        await db.flush()

    @classmethod
    async def report_user(
        cls,
        db: AsyncSession,
        reporter_id: UUID,
        target_id: UUID,
        payload: ReportUserRequest,
    ) -> ReportUserResponse:
        """
        Envía un reporte formal a la moderación administrativa con tipología y evidencia (RF-NOT-06).
        Opcionalmente aplica bloqueo preventivo inmediato (RF-MAT-14).
        """
        if reporter_id == target_id:
            raise SkillMatchException("No puedes reportar tu propia cuenta de usuario.", statuscode=400)

        target_user = await db.get(User, target_id)
        if not target_user or target_user.role != UserRole.MEMBER:
            raise SkillMatchException("Recurso no encontrado", statuscode=404)

        report = UserReport(
            reporter_id=reporter_id,
            reported_id=target_id,
            reason=payload.reason.value,
            description=payload.description,
            evidence_url=payload.evidence_url,
            status=ReportStatus.PENDING.value,
        )
        db.add(report)
        await db.flush()

        user_blocked = False
        if payload.block_user:
            await cls.block_user(
                db,
                blocker_id=reporter_id,
                target_id=target_id,
                reason=payload.reason.value,
                notes=f"Bloqueo automático derivado de reporte ID: {report.id}",
            )
            user_blocked = True

        return ReportUserResponse(
            report_id=report.id,
            reported_id=target_user.id,
            reported_name=target_user.full_name,
            reason=report.reason,
            status=report.status,
            created_at=report.created_at,
            user_blocked=user_blocked,
        )

    @classmethod
    async def get_safety_status(
        cls, db: AsyncSession, user_a_id: UUID, user_b_id: UUID
    ) -> UserSafetyStatusResponse:
        """Verifica si existe algún bloqueo preventivo activo entre dos miembros."""
        if user_a_id == user_b_id:
            return UserSafetyStatusResponse(
                target_user_id=user_b_id,
                is_blocked_by_me=False,
                is_blocking_me=False,
                can_interact=True,
                blocked_at=None,
            )

        block_by_me = await db.scalar(
            select(UserBlock).where(
                UserBlock.blocker_id == user_a_id,
                UserBlock.blocked_id == user_b_id,
            )
        )
        block_by_other = await db.scalar(
            select(UserBlock).where(
                UserBlock.blocker_id == user_b_id,
                UserBlock.blocked_id == user_a_id,
            )
        )

        is_blocked_by_me = block_by_me is not None
        is_blocking_me = block_by_other is not None
        can_interact = not (is_blocked_by_me or is_blocking_me)

        return UserSafetyStatusResponse(
            target_user_id=user_b_id,
            is_blocked_by_me=is_blocked_by_me,
            is_blocking_me=is_blocking_me,
            can_interact=can_interact,
            blocked_at=block_by_me.created_at if block_by_me else None,
        )
