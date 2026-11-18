from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.evaluation import (
    EvaluationConsentRequest, EvaluationConsentResponse, EvaluationPreflightResponse,
)
from app.schemas.response import APIResponse
from app.services.evaluation_preflight_service import EvaluationPreflightService
from app.schemas.calibration import CalibrationChallengeResponse, CalibrationVerifyRequest, CalibrationStateResponse
from app.services.evaluation_calibration_service import EvaluationCalibrationService

router = APIRouter(prefix="/evaluations", tags=["Evaluación: preparación compartida"])


@router.post("/{evaluation_id}/liveness/challenge", response_model=APIResponse[CalibrationChallengeResponse],
             response_model_exclude={"count"}, summary="Emitir un reto de calibración válido por cinco segundos")
async def calibration_challenge(evaluation_id: UUID, db: AsyncSession = Depends(get_db),
                                user: User = Depends(get_current_user)):
    data = await EvaluationCalibrationService.challenge(db, user, evaluation_id)
    return APIResponse.ok(data=CalibrationChallengeResponse.model_validate(data), message="Reto de calibración preparado.")


@router.post("/{evaluation_id}/liveness/verify-identity", response_model=APIResponse[CalibrationStateResponse],
             response_model_exclude={"count"}, summary="Comprobar ambiente, reto e identidad sin consumir el intento")
async def calibration_verify(evaluation_id: UUID, payload: CalibrationVerifyRequest,
                             db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    data = await EvaluationCalibrationService.verify(db, user, evaluation_id, payload)
    return APIResponse.ok(data=data, message="Calibración completada. El examen todavía no comenzó ni consumió tu intento.")


@router.get("/{evaluation_id}/environment/verify", response_model=APIResponse[CalibrationStateResponse],
            response_model_exclude={"count"}, summary="Consultar el resultado de calibración, sin volver a capturar")
async def calibration_state(evaluation_id: UUID, db: AsyncSession = Depends(get_db),
                            user: User = Depends(get_current_user)):
    data = await EvaluationCalibrationService.state(db, user, evaluation_id)
    return APIResponse.ok(data=data, message="Estado de calibración recuperado.")


@router.get("/skills/{teaching_skill_id}/preflight", response_model=APIResponse[EvaluationPreflightResponse],
            response_model_exclude={"count"}, summary="Consultar preparación sin consumir un intento")
async def preflight(teaching_skill_id: UUID, db: AsyncSession = Depends(get_db),
                    user: User = Depends(get_current_user)):
    data = await EvaluationPreflightService.preflight(db, user, teaching_skill_id)
    return APIResponse.ok(data=data, message="Preparación de evaluación recuperada exitosamente.")


@router.post("/skills/{teaching_skill_id}/consent", response_model=APIResponse[EvaluationConsentResponse],
             response_model_exclude={"count"}, summary="Registrar consentimiento sin iniciar ni consumir el intento")
async def consent(teaching_skill_id: UUID, payload: EvaluationConsentRequest, request: Request,
                  db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    data = await EvaluationPreflightService.consent(
        db, user, teaching_skill_id, payload,
        request.client.host if request.client else "unknown", request.headers.get("user-agent", ""),
    )
    return APIResponse.ok(data=EvaluationConsentResponse.model_validate(data),
                          message="Consentimiento registrado. El intento aún no comenzó ni se descontó.")
