from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.response import APIResponse
from app.schemas.user_profile import (
    BiometricEnrollRequest,
    IdentityVerifyRequest,
    UserProfilePatch,
    UserProfileResponse,
    UserProfileUpdate,
)
from app.services.user_profile_service import UserProfileService

router = APIRouter(
    prefix="/users/me",
    tags=["Perfil y Biometría"],
)


@router.get(
    "/profile",
    response_model=APIResponse[UserProfileResponse],
    response_model_exclude={"count"},
)
async def get_my_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = await UserProfileService.get_profile(db, current_user)
    return APIResponse.ok(
        data=data,
        message="Perfil de usuario recuperado exitosamente.",
    )


@router.put(
    "/profile",
    response_model=APIResponse[UserProfileResponse],
    response_model_exclude={"count"},
)
async def update_my_profile(
    payload: UserProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = await UserProfileService.update_profile(db, current_user, payload)
    return APIResponse.ok(
        data=data,
        message="Perfil y preferencias actualizados exitosamente.",
    )


@router.patch(
    "/profile",
    response_model=APIResponse[UserProfileResponse],
    response_model_exclude={"count"},
)
async def patch_my_profile(
    payload: UserProfilePatch,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = await UserProfileService.patch_profile(db, current_user, payload)
    return APIResponse.ok(
        data=data,
        message="Cambios del perfil guardados exitosamente.",
    )


@router.post(
    "/biometrics/enroll",
    response_model=APIResponse[UserProfileResponse],
    response_model_exclude={"count"},
)
async def enroll_my_biometrics(
    payload: BiometricEnrollRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = await UserProfileService.enroll_biometrics(db, current_user, payload)
    return APIResponse.ok(
        data=data,
        message="Rostro testigo enrolado y verificado exitosamente con biometría local.",
    )


@router.post(
    "/identity/verify",
    response_model=APIResponse[UserProfileResponse],
    response_model_exclude={"count"},
)
async def verify_my_identity(
    payload: IdentityVerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Verifica automáticamente la identidad del usuario cotejando el anverso de su
    carnet de identidad CI/DNI contra su rostro en vivo frente a la cámara web.
    """
    data = await UserProfileService.verify_identity(db, current_user, payload)
    similarity_pct = round((data.id_face_similarity_score or 0.0) * 100.0, 1)
    return APIResponse.ok(
        data=data,
        message=f"Identidad verificada exitosamente con carnet de identidad CI/DNI (Cotejo facial: {similarity_pct}%).",
    )
