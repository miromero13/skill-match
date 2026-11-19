"""Esquemas Pydantic para Billetera, Recargas, Escrow y Cashout (HU-42)."""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WalletBalanceData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    balance: int = Field(..., description="Saldo disponible para trueques o clases directas")
    escrow_balance: int = Field(..., description="Puntos retenidos en garantía por sesiones activas")
    rewards_balance: int = Field(..., description="Puntos generados por mentorías y propinas elegibles para retiro")
    total_balance: int = Field(..., description="Suma de saldo disponible y retenido en escrow")
    usd_equivalent: float = Field(..., description="Equivalente monetario en USD del saldo disponible")
    exchange_rate: str = Field(default="10 SP = $1.00 USD", description="Tasa de cambio estándar")
    points_per_usd: int = Field(default=10, description="Puntos requeridos por 1 USD")
    cashout_min_points: int = Field(default=100, description="Mínimo de puntos para retiro")
    platform_fee_percentage: float = Field(default=15.0, description="Comisión retenida en retiros")


class PointPackageItem(BaseModel):
    package_id: str
    name: str
    points: int
    bonus_points: int
    total_points: int
    price_usd: float
    is_popular: bool = False
    description: str


class TopupRequest(BaseModel):
    package_id: str = Field(..., description="ID del paquete seleccionado (pkg_basic, pkg_student, pkg_pro, pkg_master)")
    payment_method: str = Field(default="card", description="Método de pago (card, paypal, mock_gateway)")
    card_last_four: Optional[str] = Field(default="4291", description="Últimos 4 dígitos para comprobante")
    payment_token: Optional[str] = Field(default=None, description="Token seguro de pasarela si aplica")


class TopupResult(BaseModel):
    transaction_id: UUID
    package_id: str
    points_added: int
    bonus_points: int
    total_points_added: int
    new_balance: int
    price_usd: float
    receipt_number: str
    created_at: datetime


class CashoutCalculateRequest(BaseModel):
    points_amount: int = Field(..., ge=1, description="Cantidad de puntos a calcular")


class CashoutCalculation(BaseModel):
    points_amount: int
    gross_amount_usd: float
    fee_percentage: float
    fee_amount_usd: float
    net_amount_usd: float
    is_eligible: bool
    ineligible_reason: Optional[str] = None


class CashoutCreateRequest(BaseModel):
    points_amount: int = Field(..., ge=10, description="Puntos a canjear por dinero real (mínimo 100)")
    bank_name: str = Field(..., min_length=2, max_length=100, description="Entidad bancaria receptora")
    account_number: str = Field(..., min_length=4, max_length=100, description="Número de cuenta bancaria o CBU/IBAN/CLABE")
    account_holder_name: str = Field(..., min_length=3, max_length=150, description="Nombre completo del titular de la cuenta")
    account_holder_id: str = Field(..., min_length=4, max_length=50, description="Documento de identidad oficial (DNI / CI / Tax ID)")

    @field_validator("bank_name", "account_number", "account_holder_name", "account_holder_id")
    @classmethod
    def clean_text(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("El campo no puede estar vacío.")
        return cleaned


class CashoutRequestItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    points_amount: int
    gross_amount_usd: float
    fee_percentage: float
    fee_amount_usd: float
    net_amount_usd: float
    status: str
    bank_name: str
    account_number_masked: str
    account_holder_name: str
    account_holder_id: str
    admin_notes: Optional[str] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None


class PointTransactionItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    amount: int
    balance_after: int
    escrow_after: int
    transaction_type: str
    reference_id: Optional[UUID] = None
    description: str
    created_at: datetime


class SessionPayResult(BaseModel):
    session_id: UUID
    points_locked: int
    payment_state: str
    wallet_balance_after: int
    wallet_escrow_after: int
    message: str
