from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.response import APIResponse
from app.schemas.theory_exam import TheoryStartRequest, TheoryStartResponse, PublicTheoryQuestion
from app.services.theory_exam_service import TheoryExamService

router = APIRouter(prefix="/evaluations", tags=["Examen teórico"])


@router.post("/start", response_model=APIResponse[TheoryStartResponse], response_model_exclude={"count"},
             summary="Iniciar examen calibrado y registrar una única vez el intento")
async def start_theory(payload: TheoryStartRequest, db: AsyncSession = Depends(get_db),
                       user: User = Depends(get_current_user)):
    result = await TheoryExamService.start(db, user, payload)
    return APIResponse.ok(message="Examen teórico iniciado. Tu intento quedó registrado.", data=result)


@router.get("/{evaluation_id}/questions", response_model=APIResponse[list[PublicTheoryQuestion]],
            summary="Consultar preguntas asignadas sin revelar referencias ni rúbricas")
async def theory_questions(evaluation_id: UUID, db: AsyncSession = Depends(get_db),
                           user: User = Depends(get_current_user)):
    result = await TheoryExamService.questions(db, user, evaluation_id)
    return APIResponse.ok(message="Preguntas del examen recuperadas exitosamente.", data=result, count=len(result))
