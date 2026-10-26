import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.response import APIResponse
from app.schemas.admin import (
    AdminCreateRequest,
    AdminStatusUpdateRequest,
    AdminItemResponse,
    AdminListResponse,
)
from app.services.admin_service import AdminService

router = APIRouter(
    prefix="/admin",
    tags=["admin-management"]
)

@router.get(
    "",
    response_model=AdminListResponse,
    status_code=status.HTTP_200_OK,
    summary="Listado de cuentas de administradores",
    description="Retorna el listado de todos los administradores registrados y el total con 'count' (RF-USR-15, HU-10). Protegido con ofuscación 404 estricta."
)
async def list_administrators(
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user),
):
    admins, total_count = await AdminService.list_administrators(db)
    return AdminListResponse(
        statuscode=status.HTTP_200_OK,
        message="Listado de administradores recuperado exitosamente.",
        data=[AdminItemResponse.model_validate(admin) for admin in admins],
        count=total_count
    )

@router.post(
    "",
    response_model=APIResponse[AdminItemResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Alta de nuevo usuario administrador",
    description="Crea una nueva cuenta administrativa con contraseña hasheada y rol canónico ADMIN (RF-USR-10, HU-10)."
)
async def create_administrator(
    request: AdminCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user),
):
    new_admin = await AdminService.create_administrator(db, request, current_admin)
    return APIResponse(
        statuscode=status.HTTP_201_CREATED,
        message="Administrador creado exitosamente.",
        data=AdminItemResponse.model_validate(new_admin)
    )

@router.patch(
    "/{id}/status",
    response_model=APIResponse[AdminItemResponse],
    status_code=status.HTTP_200_OK,
    summary="Suspender o reactivar cuenta administrativa",
    description="Suspende o reactiva un administrador con registro de auditoría (RF-USR-15, HU-10). Impide la auto-suspensión de la cuenta propia en sesión."
)
async def update_administrator_status(
    id: uuid.UUID,
    request: AdminStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user),
):
    updated_admin = await AdminService.update_administrator_status(
        db=db,
        admin_id=id,
        request=request,
        current_admin=current_admin
    )
    action = "reactivada" if updated_admin.is_active else "suspendida"
    return APIResponse(
        statuscode=status.HTTP_200_OK,
        message=f"Cuenta de administrador {action} exitosamente.",
        data=AdminItemResponse.model_validate(updated_admin)
    )
