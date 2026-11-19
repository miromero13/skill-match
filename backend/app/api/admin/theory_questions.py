"""Administrative routes; the shared admin dependency conceals unauthorized access."""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin_user
from app.db.session import get_db
from app.schemas.response import APIResponse
from app.schemas.theory_question import (
    QuestionCreate, QuestionResponse, QuestionEditRequest, QuestionVersionRequest,
)
from app.services.theory_question_service import TheoryQuestionService

router = APIRouter(prefix="/admin/theory/questions", tags=["Banco de preguntas"],
                   dependencies=[Depends(get_current_admin_user)])


@router.post("", response_model=APIResponse[QuestionResponse], response_model_exclude={"count"},
             status_code=201, summary="Crear un borrador teórico sin publicar ni consumir intentos")
async def create_question(payload: QuestionCreate, db: AsyncSession = Depends(get_db)):
    item = await TheoryQuestionService.create(db, payload)
    return APIResponse(statuscode=201, message="Borrador de pregunta creado exitosamente.",
                       data=QuestionResponse.model_validate(item))


@router.get("", response_model=APIResponse[list[QuestionResponse]],
            summary="Listar últimas versiones por habilidad, nivel y estado")
async def list_questions(skill_id: UUID | None = None,
                         level_number: int | None = Query(default=None, ge=1, le=5),
                         status: Literal["DRAFT", "PUBLISHED", "ARCHIVED"] | None = None,
                         offset: int = Query(default=0, ge=0, le=100000),
                         limit: int = Query(default=20, ge=1, le=100),
                         db: AsyncSession = Depends(get_db)):
    items, count = await TheoryQuestionService.page(db, skill_id, level_number, status, offset, limit)
    return APIResponse(statuscode=200, message="Preguntas teóricas recuperadas exitosamente.",
                       data=[QuestionResponse.model_validate(item) for item in items], count=count)


@router.get("/{question_id}", response_model=APIResponse[QuestionResponse],
            response_model_exclude={"count"}, summary="Consultar la última versión de una pregunta")
async def get_question(question_id: UUID, db: AsyncSession = Depends(get_db)):
    item = await TheoryQuestionService.get(db, question_id)
    return APIResponse.ok(message="Pregunta teórica recuperada exitosamente.",
                          data=QuestionResponse.model_validate(item))


@router.patch("/{question_id}", response_model=APIResponse[QuestionResponse],
              response_model_exclude={"count"}, summary="Crear revisión de borrador sin modificar el historial")
async def edit_question(question_id: UUID, payload: QuestionEditRequest,
                        db: AsyncSession = Depends(get_db)):
    item = await TheoryQuestionService.revise(db, question_id, payload.expected_version, "edit", payload.content)
    return APIResponse.ok(message="Nueva versión de pregunta creada.", data=QuestionResponse.model_validate(item))


@router.post("/{question_id}/publish", response_model=APIResponse[QuestionResponse],
             response_model_exclude={"count"}, summary="Publicar una versión con referencia y rúbrica completas")
async def publish_question(question_id: UUID, payload: QuestionVersionRequest,
                           db: AsyncSession = Depends(get_db)):
    item = await TheoryQuestionService.revise(db, question_id, payload.expected_version, "publish")
    return APIResponse.ok(message="Pregunta publicada exitosamente.", data=QuestionResponse.model_validate(item))


@router.post("/{question_id}/archive", response_model=APIResponse[QuestionResponse],
             response_model_exclude={"count"}, summary="Archivar conservando versiones anteriores")
async def archive_question(question_id: UUID, payload: QuestionVersionRequest,
                           db: AsyncSession = Depends(get_db)):
    item = await TheoryQuestionService.revise(db, question_id, payload.expected_version, "archive")
    return APIResponse.ok(message="Pregunta archivada exitosamente.", data=QuestionResponse.model_validate(item))


@router.get("/{question_id}/versions", response_model=APIResponse[list[QuestionResponse]],
            summary="Consultar historial de versiones inmutables")
async def question_versions(question_id: UUID, db: AsyncSession = Depends(get_db)):
    items = await TheoryQuestionService.history(db, question_id)
    return APIResponse.ok(message="Versiones de pregunta recuperadas exitosamente.",
                          data=[QuestionResponse.model_validate(item) for item in items], count=len(items))
