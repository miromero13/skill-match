from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.exceptions import SkillMatchException
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.assistant import ChatHistoryItem, ChatMessageRequest, ChatMessageResponse
from app.schemas.response import APIResponse
from app.services.assistant_service import assistant_service

router = APIRouter(prefix="/assistant", tags=["Asistente Virtual IA"])


async def current_member(user: Annotated[User, Depends(get_current_user)]) -> User:
    """Restringe el asistente virtual exclusivamente a usuarios con rol MEMBER (404 obfuscation)."""
    if user.role != UserRole.MEMBER:
        raise SkillMatchException("Recurso no encontrado", statuscode=404)
    return user


@router.post(
    "/chat",
    response_model=APIResponse[ChatMessageResponse],
    status_code=status.HTTP_200_OK,
    summary="Enviar mensaje al Asistente Virtual",
    description="Procesa la consulta del usuario con Gemini AI, ejecuta herramientas de dominio y genera sugerencias interactivas.",
)
async def chat_with_assistant(
    payload: ChatMessageRequest,
    user: Annotated[User, Depends(current_member)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> APIResponse[ChatMessageResponse]:
    response = await assistant_service.send_message(
        db=db,
        user=user,
        user_message=payload.message,
    )
    return APIResponse(
        statuscode=status.HTTP_200_OK,
        message="Respuesta generada exitosamente",
        data=response,
    )


@router.get(
    "/history",
    response_model=APIResponse[list[ChatHistoryItem]],
    status_code=status.HTTP_200_OK,
    summary="Consultar historial de conversación",
    description="Obtiene los mensajes de la sesión conversacional actual del usuario autenticado.",
)
async def get_chat_history(
    user: Annotated[User, Depends(current_member)],
) -> APIResponse[list[ChatHistoryItem]]:
    history = assistant_service.get_history(str(user.id))
    return APIResponse(
        statuscode=status.HTTP_200_OK,
        message="Historial recuperado exitosamente",
        data=history,
        count=len(history),
    )


@router.delete(
    "/history",
    response_model=APIResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Limpiar historial de conversación",
    description="Reinicia el contexto conversacional del usuario.",
)
async def clear_chat_history(
    user: Annotated[User, Depends(current_member)],
) -> APIResponse[None]:
    assistant_service.clear_history(str(user.id))
    return APIResponse(
        statuscode=status.HTTP_200_OK,
        message="Conversación reiniciada exitosamente",
        data=None,
    )
