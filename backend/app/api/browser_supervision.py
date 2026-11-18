"""SM-43 trial endpoints; no exam lifecycle or debit endpoints."""
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.browser_supervision import (
    BatchResponse, IncidentBatch, IncidentResponse, TabRequest, TrialRequest, TrialResponse,
)
from app.schemas.response import APIResponse
from app.services.browser_supervision_service import BrowserSupervisionService as Service

router = APIRouter(prefix="/browser-supervision/trials", tags=["Supervisión de navegador: prueba sin examen"])


@router.post("", response_model=APIResponse[TrialResponse], response_model_exclude={"count"},
             summary="Crear o recuperar prueba con autorización exclusiva de pestaña durante veinte segundos")
async def start(payload: TrialRequest, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    trial = await Service.start(db, user, payload)
    return APIResponse.ok(data=TrialResponse.model_validate(trial),
                          message="Sesión de prueba preparada. No inicia un examen ni consume intentos.")


@router.get("/{trial_id}", response_model=APIResponse[TrialResponse], response_model_exclude={"count"},
            summary="Consultar una prueba propia sin activarla")
async def state(trial_id: UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return APIResponse.ok(data=TrialResponse.model_validate(await Service.owned(db, user, trial_id)),
                          message="Estado de prueba recuperado.")


@router.post("/{trial_id}/heartbeat", response_model=APIResponse[TrialResponse], response_model_exclude={"count"},
             summary="Renovar autorización de pestaña; no consume intentos")
async def heartbeat(trial_id: UUID, payload: TabRequest, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    trial = await Service.action(db, user, trial_id, payload.tab_id, "heartbeat")
    return APIResponse.ok(data=TrialResponse.model_validate(trial), message="Autorización de pestaña renovada.")


@router.post("/{trial_id}/release", response_model=APIResponse[TrialResponse], response_model_exclude={"count"},
             summary="Liberar pestaña sin borrar incidentes ni cerrar la prueba")
async def release(trial_id: UUID, payload: TabRequest, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    trial = await Service.action(db, user, trial_id, payload.tab_id, "release")
    return APIResponse.ok(data=TrialResponse.model_validate(trial), message="Pestaña de prueba liberada.")


@router.post("/{trial_id}/close", response_model=APIResponse[TrialResponse], response_model_exclude={"count"},
             summary="Cerrar prueba manteniendo la bitácora; no finaliza ningún examen")
async def close(trial_id: UUID, payload: TabRequest, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    trial = await Service.action(db, user, trial_id, payload.tab_id, "close")
    return APIResponse.ok(data=TrialResponse.model_validate(trial), message="Prueba cerrada. La bitácora se conserva.")


@router.post("/{trial_id}/events", response_model=APIResponse[BatchResponse], response_model_exclude={"count"},
             summary="Guardar1–50 incidentes idempotentes; máximo200 nuevos por minuto y10000 por prueba")
async def append(trial_id: UUID, payload: IncidentBatch, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await Service.append(db, user, trial_id, payload)
    return APIResponse.ok(data=BatchResponse.model_validate(result), message="Incidentes de prueba guardados.")


@router.get("/{trial_id}/events", response_model=APIResponse[list[IncidentResponse]],
            summary="Consultar bitácora propia por secuencia, incluidos ensayos cerrados")
async def ledger(trial_id: UUID, after: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
                 db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rows, total = await Service.ledger(db, user, trial_id, after, limit)
    return APIResponse.ok(data=[IncidentResponse.model_validate(row) for row in rows], count=total,
                          message="Bitácora de prueba recuperada.")
