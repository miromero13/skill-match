import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin_user, get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.programming import (
    ProgrammingChallengeCreateRequest,
    ProgrammingChallengeResponse,
    ProgrammingChallengeSummary,
    ProgrammingRunRequest,
    ProgrammingRunResponse,
    ProgrammingSubmissionResponse,
)
from app.schemas.response import APIResponse
from app.services.programming_service import ProgrammingService

admin_router = APIRouter(
    prefix="/admin/programming",
    tags=["admin-programming"],
    dependencies=[Depends(get_current_admin_user)],
)
member_router = APIRouter(prefix="/programming", tags=["programming"])


@admin_router.get("/challenges", response_model=APIResponse[list[ProgrammingChallengeSummary]])
async def list_challenges(
    skill_id: UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    items = await ProgrammingService.list_challenges(db, skill_id)
    return APIResponse(statuscode=200, message="Retos de programación recuperados exitosamente.", data=items, count=len(items))


@admin_router.post("/challenges", response_model=APIResponse[ProgrammingChallengeResponse], status_code=status.HTTP_201_CREATED)
async def create_challenge(
    payload: ProgrammingChallengeCreateRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    item = await ProgrammingService.create_challenge(db, admin, payload)
    return APIResponse(statuscode=201, message="Reto de programación creado exitosamente.", data=item)


@admin_router.post("/challenges/{challenge_id}/publish", response_model=APIResponse[ProgrammingChallengeSummary])
async def publish_challenge(
    challenge_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    item = await ProgrammingService.publish_challenge(db, challenge_id)
    return APIResponse(statuscode=200, message="Reto de programación publicado exitosamente.", data=item)


@member_router.get("/evaluations/{evaluation_id}/challenge", response_model=APIResponse[ProgrammingChallengeResponse])
async def get_evaluation_challenge(
    evaluation_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = await ProgrammingService.get_challenge_for_evaluation(db, user, evaluation_id)
    return APIResponse(statuscode=200, message="Reto de programación recuperado exitosamente.", data=item)


@member_router.get("/challenges/{challenge_id}", response_model=APIResponse[ProgrammingChallengeResponse])
async def get_member_challenge(
    challenge_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = await ProgrammingService.get_challenge(db, challenge_id, include_hidden=False)
    return APIResponse(statuscode=200, message="Reto de programación recuperado exitosamente.", data=item)


@member_router.post("/challenges/{challenge_id}/run", response_model=APIResponse[ProgrammingRunResponse])
async def run_public_tests(
    challenge_id: UUID,
    payload: ProgrammingRunRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await ProgrammingService.run_public_tests(db, challenge_id, payload.code)
    return APIResponse(statuscode=200, message="Pruebas públicas ejecutadas exitosamente.", data=result)


@member_router.post("/evaluations/{evaluation_id}/challenges/{challenge_id}/submit", response_model=APIResponse[ProgrammingSubmissionResponse], status_code=status.HTTP_201_CREATED)
async def submit_solution(
    evaluation_id: UUID,
    challenge_id: UUID,
    payload: ProgrammingRunRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    submission = await ProgrammingService.submit(db, user, evaluation_id, challenge_id, payload.code)
    result = ProgrammingRunResponse.model_validate(submission.result)
    response = ProgrammingSubmissionResponse(
        submission_id=submission.id,
        submitted_at=submission.submitted_at,
        **result.model_dump(),
    )
    return APIResponse(statuscode=201, message="Solución de programación entregada exitosamente.", data=response)
