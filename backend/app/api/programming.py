from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin_user, get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.programming import (
    ChallengeCreateRequest,
    ChallengePreviewRequest,
    ChallengeResponse,
    ChallengeSummary,
    ChallengeRunRequest,
    ChallengeRunResponse,
    ChallengeSubmissionResponse,
)
from app.schemas.response import APIResponse
from app.services.programming_service import ChallengeService

admin_router = APIRouter(
    prefix="/admin/challenges",
    tags=["admin-challenges"],
    dependencies=[Depends(get_current_admin_user)],
)
member_router = APIRouter(prefix="/challenges", tags=["challenges"])


@admin_router.get("/challenges", response_model=APIResponse[list[ChallengeSummary]])
async def list_challenges(
    skill_id: UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    items = await ChallengeService.list_challenges(db, skill_id)
    return APIResponse(statuscode=200, message="Retos recuperados exitosamente.", data=items, count=len(items))


@admin_router.post("/challenges/test", response_model=APIResponse[ChallengeRunResponse])
async def preview_challenge(
    payload: ChallengePreviewRequest,
    admin: User = Depends(get_current_admin_user),
):
    result = await ChallengeService.preview_challenge(payload)
    return APIResponse(statuscode=200, message="Prueba del reto ejecutada exitosamente.", data=result)


@admin_router.post("/challenges", response_model=APIResponse[ChallengeResponse], status_code=status.HTTP_201_CREATED)
async def create_challenge(
    payload: ChallengeCreateRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    item = await ChallengeService.create_challenge(db, admin, payload)
    return APIResponse(statuscode=201, message="Reto creado exitosamente.", data=item)


@admin_router.post("/challenges/{challenge_id}/publish", response_model=APIResponse[ChallengeSummary])
async def publish_challenge(
    challenge_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    item = await ChallengeService.publish_challenge(db, challenge_id)
    return APIResponse(statuscode=200, message="Reto publicado exitosamente.", data=item)


@member_router.get("/evaluations/{evaluation_id}/challenge", response_model=APIResponse[ChallengeResponse])
async def get_evaluation_challenge(
    evaluation_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = await ChallengeService.get_challenge_for_evaluation(db, user, evaluation_id)
    return APIResponse(statuscode=200, message="Reto recuperado exitosamente.", data=item)


@member_router.get("/challenges/{challenge_id}", response_model=APIResponse[ChallengeResponse])
async def get_member_challenge(
    challenge_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = await ChallengeService.get_challenge(db, challenge_id, include_hidden=False)
    return APIResponse(statuscode=200, message="Reto recuperado exitosamente.", data=item)


@member_router.post("/challenges/{challenge_id}/run", response_model=APIResponse[ChallengeRunResponse])
async def run_public_tests(
    challenge_id: UUID,
    payload: ChallengeRunRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await ChallengeService.run_public_tests(db, challenge_id, payload.code)
    return APIResponse(statuscode=200, message="Pruebas públicas ejecutadas exitosamente.", data=result)


@member_router.post("/evaluations/{evaluation_id}/challenges/{challenge_id}/submit", response_model=APIResponse[ChallengeSubmissionResponse], status_code=status.HTTP_201_CREATED)
async def submit_solution(
    evaluation_id: UUID,
    challenge_id: UUID,
    payload: ChallengeRunRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    submission = await ChallengeService.submit(db, user, evaluation_id, challenge_id, payload.code)
    result = ChallengeRunResponse.model_validate(submission.result)
    response = ChallengeSubmissionResponse(
        submission_id=submission.id,
        submitted_at=submission.submitted_at,
        **result.model_dump(),
    )
    return APIResponse(statuscode=201, message="Solución entregada exitosamente.", data=response)
