"""Servicio de Dominio para Quejas, Arbitraje y Compensaciones (HU-43 / RF-GOV-01, 02, 03)."""
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.complaint import Complaint, ComplaintReason, ComplaintStatus
from app.models.exchange_session import ExchangeSession
from app.models.notification import NotificationType
from app.models.user import User
from app.models.wallet import PointTransaction, PointTransactionType
from app.schemas.complaint import (
    ComplaintCreateRequest,
    ComplaintResolveRequest,
    ComplaintResponse,
)
from app.services.notification_service import NotificationService
from app.services.wallet_service import WalletService


class ComplaintService:
    @staticmethod
    def _map_to_response(complaint: Complaint) -> ComplaintResponse:
        user_name = None
        user_email = None
        if complaint.user:
            user_name = complaint.user.full_name
            user_email = complaint.user.email

        session_modality = None
        if complaint.session:
            session_modality = complaint.session.modality

        resolved_by_name = None
        if complaint.resolved_by:
            resolved_by_name = complaint.resolved_by.full_name

        return ComplaintResponse(
            id=complaint.id,
            user_id=complaint.user_id,
            user_name=user_name,
            user_email=user_email,
            session_id=complaint.session_id,
            session_modality=session_modality,
            reason=complaint.reason,
            title=complaint.title,
            description=complaint.description,
            evidence_urls=complaint.evidence_urls or [],
            status=complaint.status,
            admin_response=complaint.admin_response,
            points_compensated=complaint.points_compensated,
            resolved_by_id=complaint.resolved_by_id,
            resolved_by_name=resolved_by_name,
            resolved_at=complaint.resolved_at,
            created_at=complaint.created_at,
            updated_at=complaint.updated_at,
        )

    @classmethod
    async def create_complaint(
        cls,
        db: AsyncSession,
        user: User,
        payload: ComplaintCreateRequest,
    ) -> ComplaintResponse:
        """Radica una nueva queja formal por parte del miembro."""
        if payload.session_id:
            stmt = select(ExchangeSession).where(ExchangeSession.id == payload.session_id)
            res = await db.execute(stmt)
            session = res.scalar_one_or_none()
            if not session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="La sesión indicada no existe en el sistema.",
                )
            if session.learner_id != user.id and session.instructor_id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Solo los participantes directos de una sesión pueden vincularla a un reclamo.",
                )

        complaint = Complaint(
            id=uuid4(),
            user_id=user.id,
            session_id=payload.session_id,
            reason=payload.reason.value,
            title=payload.title.strip(),
            description=payload.description.strip(),
            evidence_urls=payload.evidence_urls,
            status=ComplaintStatus.OPEN.value,
        )
        db.add(complaint)

        # Emisión de acuse de recibo al usuario
        await NotificationService.emit_in_app(
            db,
            user_id=user.id,
            event_id=complaint.id,
            notification_type=NotificationType.OTHER,
            title="Queja Recibida Formalmente",
            message=f"Hemos recibido tu reporte '{complaint.title}'. El equipo administrativo arbitrará el caso a la brevedad.",
        )

        await db.commit()
        await db.refresh(complaint)

        # Cargar relaciones para el response
        stmt = (
            select(Complaint)
            .options(
                selectinload(Complaint.user),
                selectinload(Complaint.session),
            )
            .where(Complaint.id == complaint.id)
        )
        complaint_loaded = (await db.execute(stmt)).scalar_one()
        return cls._map_to_response(complaint_loaded)

    @classmethod
    async def get_user_complaints(
        cls,
        db: AsyncSession,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[ComplaintResponse], int]:
        """Obtiene las quejas emitidas por un miembro específico."""
        base_query = select(Complaint).where(Complaint.user_id == user_id)
        count_stmt = select(func.count()).select_from(base_query.subquery())
        total = (await db.execute(count_stmt)).scalar_one()

        query = (
            base_query.options(
                selectinload(Complaint.user),
                selectinload(Complaint.session),
                selectinload(Complaint.resolved_by),
            )
            .order_by(Complaint.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await db.execute(query)).scalars().all()
        return [cls._map_to_response(r) for r in rows], total

    @classmethod
    async def get_admin_complaints(
        cls,
        db: AsyncSession,
        status_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[ComplaintResponse], int]:
        """Listado de todas las quejas del sistema para el panel arbitral de administración."""
        base_query = select(Complaint)
        if status_filter and status_filter != "ALL":
            base_query = base_query.where(Complaint.status == status_filter)

        count_stmt = select(func.count()).select_from(base_query.subquery())
        total = (await db.execute(count_stmt)).scalar_one()

        query = (
            base_query.options(
                selectinload(Complaint.user),
                selectinload(Complaint.session),
                selectinload(Complaint.resolved_by),
            )
            .order_by(Complaint.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await db.execute(query)).scalars().all()
        return [cls._map_to_response(r) for r in rows], total

    @classmethod
    async def get_complaint_by_id(
        cls,
        db: AsyncSession,
        complaint_id: UUID,
    ) -> ComplaintResponse:
        """Obtiene una queja por su ID."""
        stmt = (
            select(Complaint)
            .options(
                selectinload(Complaint.user),
                selectinload(Complaint.session),
                selectinload(Complaint.resolved_by),
            )
            .where(Complaint.id == complaint_id)
        )
        complaint = (await db.execute(stmt)).scalar_one_or_none()
        if not complaint:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Queja no encontrada.",
            )
        return cls._map_to_response(complaint)

    @classmethod
    async def resolve_complaint(
        cls,
        db: AsyncSession,
        admin_user: User,
        complaint_id: UUID,
        payload: ComplaintResolveRequest,
    ) -> ComplaintResponse:
        """Dictamen arbitral del administrador, cierre de disputa y compensación opcional."""
        stmt = (
            select(Complaint)
            .options(
                selectinload(Complaint.user),
                selectinload(Complaint.session),
            )
            .where(Complaint.id == complaint_id)
        )
        complaint = (await db.execute(stmt)).scalar_one_or_none()
        if not complaint:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Queja no encontrada.",
            )

        now = datetime.now(timezone.utc)
        complaint.admin_response = payload.admin_response.strip()
        complaint.status = payload.status.value
        complaint.resolved_by_id = admin_user.id
        complaint.resolved_at = now

        # Compensación con SkillPoints si el administrador lo aprobó
        points_to_give = payload.points_to_compensate
        if points_to_give > 0:
            wallet = await WalletService.get_or_create_wallet(db, complaint.user_id)
            wallet.balance += points_to_give

            tx = PointTransaction(
                id=uuid4(),
                user_id=complaint.user_id,
                amount=points_to_give,
                balance_after=wallet.balance,
                escrow_after=wallet.escrow_balance,
                transaction_type=PointTransactionType.ADMIN_REWARD.value,
                reference_id=complaint.id,
                description=f"Compensación arbitral por queja: {complaint.title}",
            )
            db.add(tx)
            complaint.points_compensated += points_to_give

            # Notificación de puntos acreditados
            await NotificationService.emit_in_app(
                db,
                user_id=complaint.user_id,
                event_id=tx.id,
                notification_type=NotificationType.POINTS_RECEIVED,
                title="Compensación en SkillPoints Acreditada",
                message=f"Se acreditaron +{points_to_give} SP en tu billetera como resolución favorable de tu reporte.",
            )

        # Notificación formal de resolución de queja
        res_label = "resuelta favorablemente" if payload.status == ComplaintStatus.RESOLVED else "desestimada"
        await NotificationService.emit_in_app(
            db,
            user_id=complaint.user_id,
            event_id=uuid4(),
            notification_type=NotificationType.OTHER,
            title="Resolución Oficial de Reclamo",
            message=f"Tu queja '{complaint.title}' fue {res_label}. Respuesta oficial: {payload.admin_response}",
        )

        await db.commit()
        await db.refresh(complaint)

        # Recargar con resolved_by para el payload
        return await cls.get_complaint_by_id(db, complaint.id)
