from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.response import APIResponse
from app.schemas.skill_evidence import (
    SkillEvidenceCreate, SkillEvidenceResponse, SkillEvidenceUpdate,
)
from app.services.skill_evidence_service import SkillEvidenceService

router = APIRouter(
    prefix="/users/me/teaching-skills", tags=["Evidencias de habilidades"],
    responses={
        401: {"model": APIResponse[None], "description": "Autenticación requerida"},
        403: {"model": APIResponse[None], "description": "Cuenta inactiva"},
        404: {"model": APIResponse[None], "description": "Recurso inexistente o ajeno"},
        423: {"model": APIResponse[None], "description": "Cuenta bloqueada"},
    },
)


@router.get("/{id}/evidences", response_model=APIResponse[list[SkillEvidenceResponse]])
async def list_evidences(
    id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Lista las evidencias de una habilidad ofrecida por el usuario autenticado.

    MEMBER y ADMIN solo pueden consultar sus propias habilidades; un recurso
    inexistente o ajeno devuelve 404. Orden: created_at DESC, id ASC.
    count indica el total de la habilidad, incluso si la página está vacía.
    La lectura pública del pasaporte queda fuera de este contrato privado.
    """
    items, total = await SkillEvidenceService.list_owned(db, user.id, id, page, page_size)
    return APIResponse.ok(
        data=items, count=total, message="Evidencias recuperadas exitosamente.",
    )


@router.post(
    "/{id}/evidences", status_code=201,
    response_model=APIResponse[SkillEvidenceResponse], response_model_exclude={"count"},
    responses={409: {"model": APIResponse[None], "description": "URL ya registrada en esta habilidad"}},
)
async def create_evidence(
    id: UUID, payload: SkillEvidenceCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Añade un enlace complementario a una habilidad propia.

    La URL HTTP(S) se normaliza y almacena sin descargar el recurso.
    Una URL normalizada repetida en la misma habilidad devuelve 409;
    está permitida en habilidades diferentes. No certifica la habilidad
    ni modifica su nivel. MEMBER y ADMIN están sujetos a la misma propiedad.
    """
    item = await SkillEvidenceService.save(db, user.id, id, payload)
    return APIResponse(statuscode=201, message="Evidencia registrada exitosamente.", data=item)


@router.put(
    "/{id}/evidences/{evidence_id}",
    response_model=APIResponse[SkillEvidenceResponse], response_model_exclude={"count"},
    responses={409: {"model": APIResponse[None], "description": "URL ya registrada en esta habilidad"}},
)
async def update_evidence(
    id: UUID, evidence_id: UUID, payload: SkillEvidenceUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Reemplaza los campos editables de una evidencia propia.

    Requiere title, url y evidence_type; description omitida o vacía
    se reemplaza por null. No es una actualización parcial.
    Una evidencia ajena o de otra habilidad devuelve 404;
    una URL duplicada en la habilidad devuelve 409.
    """
    item = await SkillEvidenceService.save(db, user.id, id, payload, evidence_id)
    return APIResponse.ok(data=item, message="Evidencia actualizada exitosamente.")


@router.delete(
    "/{id}/evidences/{evidence_id}",
    response_model=APIResponse[None], response_model_exclude={"count"},
)
async def delete_evidence(
    id: UUID, evidence_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Elimina físicamente una evidencia de una habilidad propia.

    Devuelve 200 con data null y sin count. Una evidencia inexistente,
    ajena o de otra habilidad devuelve 404, también al repetir el borrado.
    El borrado de la habilidad padre elimina sus evidencias en cascada.
    """
    await SkillEvidenceService.delete(db, user.id, id, evidence_id)
    return APIResponse.ok(message="Evidencia eliminada exitosamente.")
