from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.response import APIResponse
from app.schemas.admin_auth import AdminLoginRequest, AdminTokenData
from app.services.admin_auth_service import AdminAuthService

router = APIRouter(
    prefix="/admin/auth",
    tags=["Admin Authentication (HU-08)"]
)

@router.post(
    "/login",
    response_model=APIResponse[AdminTokenData],
    status_code=status.HTTP_200_OK,
    summary="Login exclusivo de Administradores (HU-08 / RF-USR-04 / RF-USR-16)",
    description=(
        "Autentica a un usuario administrador con correo institucional y contraseña. "
        "Verifica estrictamente que posea rol 'ADMIN' y cuenta activa. "
        "Emite tokens JWT conteniendo el claim dinámico 'role': 'ADMIN'. "
        "Aplica bloqueo preventivo de cuenta tras 5 intentos fallidos consecutivos."
    )
)
async def admin_login(
    payload: AdminLoginRequest,
    db: AsyncSession = Depends(get_db)
) -> APIResponse[AdminTokenData]:
    """Endpoint de inicio de sesión exclusivo para cuentas con rol ADMIN."""
    token_data = await AdminAuthService.authenticate_admin(db, payload)
    return APIResponse.ok(
        data=token_data,
        message="Inicio de sesión administrativo concedido exitosamente."
    )
