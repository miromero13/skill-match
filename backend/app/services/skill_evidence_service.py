from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SkillMatchException
from app.models.skill_evidence import SkillEvidence
from app.schemas.skill_evidence import SkillEvidenceResponse, SkillEvidenceWrite
from app.services.teaching_skill_service import TeachingSkillService


class SkillEvidenceService:
    @staticmethod
    async def _get_evidence(
        db: AsyncSession, teaching_skill_id: UUID, evidence_id: UUID,
    ) -> SkillEvidence:
        """Usar solo después de validar la propiedad de la habilidad padre."""
        item = await db.scalar(select(SkillEvidence).where(
            SkillEvidence.id == evidence_id,
            SkillEvidence.teaching_skill_id == teaching_skill_id,
        ))
        if item is None:
            raise SkillMatchException("Recurso no encontrado", statuscode=404)
        return item

    @staticmethod
    async def list_owned(
        db: AsyncSession, user_id: UUID, teaching_skill_id: UUID,
        page: int, page_size: int,
    ) -> tuple[list[SkillEvidenceResponse], int]:
        await TeachingSkillService.get_owned(db, user_id, teaching_skill_id)
        total = await db.scalar(select(func.count()).select_from(SkillEvidence).where(
            SkillEvidence.teaching_skill_id == teaching_skill_id,
        ))
        items = await db.scalars(select(SkillEvidence).where(
            SkillEvidence.teaching_skill_id == teaching_skill_id,
        ).order_by(SkillEvidence.created_at.desc(), SkillEvidence.id.asc()).offset(
            (page - 1) * page_size,
        ).limit(page_size))
        return [SkillEvidenceResponse.model_validate(item) for item in items], total or 0

    @staticmethod
    async def save(
        db: AsyncSession, user_id: UUID, teaching_skill_id: UUID,
        payload: SkillEvidenceWrite, evidence_id: UUID | None = None,
    ) -> SkillEvidenceResponse:
        await TeachingSkillService.get_owned(db, user_id, teaching_skill_id)
        item = (
            await SkillEvidenceService._get_evidence(db, teaching_skill_id, evidence_id)
            if evidence_id is not None else None
        )
        values = payload.model_dump(mode="json")
        try:
            # La restricción UNIQUE resuelve también escrituras concurrentes.
            async with db.begin_nested():
                if item is None:
                    item = SkillEvidence(teaching_skill_id=teaching_skill_id, **values)
                    db.add(item)
                else:
                    for key, value in values.items():
                        setattr(item, key, value)
                await db.flush()
        except IntegrityError as exc:
            original = getattr(exc.orig, "__cause__", None)
            if getattr(original, "constraint_name", None) == "uq_skill_evidences_skill_url":
                raise SkillMatchException(
                    "Ya registraste esta evidencia.", statuscode=409,
                ) from exc
            raise
        return SkillEvidenceResponse.model_validate(item)

    @staticmethod
    async def delete(
        db: AsyncSession, user_id: UUID, teaching_skill_id: UUID, evidence_id: UUID,
    ) -> None:
        await TeachingSkillService.get_owned(db, user_id, teaching_skill_id)
        item = await SkillEvidenceService._get_evidence(db, teaching_skill_id, evidence_id)
        await db.delete(item)
        await db.flush()
