from typing import Optional
from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.response import APIResponse
from app.schemas.auth import (
    TokenRefreshRequest,
    TokenRefreshResponse,
    UserMeResponse
)
from app.services.auth_service import AuthService

router = APIRouter(
    prefix="/auth",
    tags=["Unified Authentication & Sessions (HU-09)"]
)

@router.post(
    "/refresh",
    response_model=APIResponse[TokenRefreshResponse],
    status_code=status.HTTP_200_OK,
    summary="Renovación y rotación de tokens de sesión (HU-09 / RF-USR-04)",
    description=(
        "Renueva el token de acceso rotando el Refresh Token y preservando el claim dinámico 'role' "
        "('MEMBER' o 'ADMIN'). El Refresh Token provisto es revocado inmediatamente para impedir su reuso."
    )
)
async def refresh_session_token(
    payload: TokenRefreshRequest,
    db: AsyncSession = Depends(get_db)
) -> APIResponse[TokenRefreshResponse]:
    """Endpoint de rotación segura de tokens JWT."""
    tokens = await AuthService.refresh_tokens(db, payload.refresh_token)
    return APIResponse.ok(
        data=tokens,
        message="Sesión renovada y token rotado exitosamente."
    )

@router.post(
    "/logout",
    response_model=APIResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Cierre y revocación de sesión JWT (HU-09 / RF-USR-04 / RF-USR-12)",
    description=(
        "Revoca el Access Token de la sesión activa y opcionalmente el Refresh Token, "
        "impidiendo cualquier acceso subsiguiente hasta una nueva autenticación."
    )
)
async def logout(
    authorization: Optional[str] = Header(None, description="Bearer <token>"),
    payload: Optional[TokenRefreshRequest] = None,
    current_user: User = Depends(get_current_user)
) -> APIResponse[None]:
    """Revoca el token de sesión y finaliza la sesión activa."""
    refresh_token = payload.refresh_token if payload else None
    AuthService.logout(access_token=authorization or "", refresh_token=refresh_token)
    return APIResponse.ok(
        data=None,
        message="Sesión cerrada y tokens revocados exitosamente."
    )

@router.get(
    "/me",
    response_model=APIResponse[UserMeResponse],
    status_code=status.HTTP_200_OK,
    summary="Consulta de identidad y perfil del usuario autenticado (HU-09 / RF-USR-12)",
    description=(
        "Retorna la identidad, perfil y rol del usuario autenticado actual validando vigencia temporal, "
        "algoritmo, firma y no revocación del JWT."
    )
)
async def get_my_identity(
    current_user: User = Depends(get_current_user)
) -> APIResponse[UserMeResponse]:
    """Retorna el perfil del usuario actual autenticado."""
    profile = AuthService.get_current_user_profile(current_user)
    return APIResponse.ok(
        data=profile,
        message="Identidad de usuario verificada exitosamente."
    )
