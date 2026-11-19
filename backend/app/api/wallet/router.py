"""Router API para Billetera de Puntos, Recargas y Retiros (HU-42)."""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.exceptions import SkillMatchException
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.response import APIResponse
from app.schemas.wallet import (
    CashoutCalculateRequest,
    CashoutCalculation,
    CashoutCreateRequest,
    CashoutRequestItem,
    PointPackageItem,
    PointTransactionItem,
    TopupRequest,
    TopupResult,
    WalletBalanceData,
)
from app.services.wallet_service import wallet_service

router = APIRouter(prefix="/wallet", tags=["Billetera & Puntos"])


async def current_member(user: User = Depends(get_current_user)) -> User:
    """Restringe la billetera al rol MEMBER y oculta a otros roles."""
    if user.role != UserRole.MEMBER:
        raise SkillMatchException("Recurso no encontrado", statuscode=404)
    return user


@router.get(
    "/balance",
    response_model=APIResponse[WalletBalanceData],
    summary="Consultar balance de billetera",
    description="Devuelve saldo disponible, retenido en escrow, propinas/recompensas y equivalente monetario en USD.",
)
async def get_wallet_balance(
    user: User = Depends(current_member),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[WalletBalanceData]:
    data = await wallet_service.get_balance(db, user.id)
    return APIResponse.ok(
        data=data,
        message="Balance de billetera consultado exitosamente.",
    )


@router.get(
    "/packages",
    response_model=APIResponse[List[PointPackageItem]],
    summary="Listar paquetes de puntos disponibles",
    description="Devuelve el catálogo oficial de paquetes para recarga con bonus calculados.",
)
async def get_point_packages(
    user: User = Depends(current_member),
) -> APIResponse[List[PointPackageItem]]:
    packages = wallet_service.get_available_packages()
    return APIResponse.ok(
        data=packages,
        count=len(packages),
        message="Paquetes de puntos recuperados exitosamente.",
    )


@router.post(
    "/topup",
    response_model=APIResponse[TopupResult],
    status_code=status.HTTP_201_CREATED,
    summary="Adquirir paquete de SkillPoints",
    description="Procesa la compra y acredita los puntos con bonus correspondientes de forma inmediata.",
)
async def topup_wallet(
    payload: TopupRequest,
    user: User = Depends(current_member),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[TopupResult]:
    result = await wallet_service.topup_wallet(db, user.id, payload)
    return APIResponse.created(
        data=result,
        message=f"Acreditación exitosa de {result.total_points_added} SkillPoints en tu billetera.",
    )


@router.post(
    "/cashout/calculate",
    response_model=APIResponse[CashoutCalculation],
    summary="Calcular comisión y monto neto de retiro",
    description="Calcula en tiempo real el desglose financiero del retiro según la comisión institucional (15%).",
)
async def calculate_cashout(
    payload: CashoutCalculateRequest,
    user: User = Depends(current_member),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[CashoutCalculation]:
    calc = await wallet_service.calculate_cashout(db, user.id, payload.points_amount)
    return APIResponse.ok(
        data=calc,
        message="Cálculo de retiro generado exitosamente.",
    )


@router.post(
    "/cashout",
    response_model=APIResponse[CashoutRequestItem],
    status_code=status.HTTP_201_CREATED,
    summary="Solicitar retiro de fondos a cuenta bancaria",
    description="Valida saldo mínimo, debita los puntos de la billetera y registra la solicitud para transferencia.",
)
async def request_cashout(
    payload: CashoutCreateRequest,
    user: User = Depends(current_member),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[CashoutRequestItem]:
    result = await wallet_service.request_cashout(db, user.id, payload)
    return APIResponse.created(
        data=result,
        message=f"Solicitud de retiro por ${result.net_amount_usd:.2f} USD registrada exitosamente.",
    )


@router.get(
    "/transactions",
    response_model=APIResponse[List[PointTransactionItem]],
    summary="Historial de movimientos contables",
    description="Devuelve el historial inmutable de movimientos con filtros opcionales por tipología.",
)
async def list_wallet_transactions(
    user: User = Depends(current_member),
    db: AsyncSession = Depends(get_db),
    type_filter: Optional[str] = Query(default=None, description="TOPUP | CLASS_PAYMENT | TIP | CASHOUT | ADMIN_REWARD"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> APIResponse[List[PointTransactionItem]]:
    items, total = await wallet_service.list_transactions(
        db,
        user.id,
        type_filter=type_filter,
        page=page,
        page_size=page_size,
    )
    return APIResponse.ok(
        data=items,
        count=total,
        message="Historial de transacciones recuperado exitosamente.",
    )
