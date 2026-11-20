"""Servicio de Dominio de Billetera, Puntos, Pasarela y Escrow (HU-42)."""
import asyncio
import logging
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.exchange_session import ExchangeSession
from app.models.notification import NotificationType
from app.models.wallet import (
    CashoutRequest,
    CashoutStatus,
    PointTransaction,
    PointTransactionType,
    Wallet,
)
from app.schemas.wallet import (
    CashoutCalculation,
    CashoutCreateRequest,
    CashoutRequestItem,
    PointPackageItem,
    PointTransactionItem,
    SessionPayResult,
    TopupRequest,
    TopupResult,
    WalletBalanceData,
)
from app.services.fcm_service import FCMService
from app.services.notification_service import NotificationService

logger = logging.getLogger("skillmatch.wallet")

# Catálogo canónico de paquetes de compra de SkillPoints
PACKAGES_CATALOG: dict[str, PointPackageItem] = {
    "pkg_basic": PointPackageItem(
        package_id="pkg_basic",
        name="Paquete Básico",
        points=100,
        bonus_points=0,
        total_points=100,
        price_usd=10.0,
        is_popular=False,
        description="Ideal para agendar tus primeras clases directas o asegurar depósitos Escrow.",
    ),
    "pkg_student": PointPackageItem(
        package_id="pkg_student",
        name="Paquete Estudiante",
        points=250,
        bonus_points=25,
        total_points=275,
        price_usd=25.0,
        is_popular=True,
        description="El más popular: 10% de bonus en puntos para acelerar tu aprendizaje continuo.",
    ),
    "pkg_pro": PointPackageItem(
        package_id="pkg_pro",
        name="Paquete Pro",
        points=500,
        bonus_points=75,
        total_points=575,
        price_usd=50.0,
        is_popular=False,
        description="15% de bonus en puntos. Pensado para miembros con metas avanzadas en varias áreas.",
    ),
    "pkg_master": PointPackageItem(
        package_id="pkg_master",
        name="Paquete Master VIP",
        points=1000,
        bonus_points=200,
        total_points=1200,
        price_usd=100.0,
        is_popular=False,
        description="20% de bonus en puntos. Máximo ahorro y reserva prioritaria de mentores evaluados.",
    ),
}


class WalletService:
    @staticmethod
    def get_available_packages() -> list[PointPackageItem]:
        """Devuelve los paquetes de puntos configurados."""
        return list(PACKAGES_CATALOG.values())

    @staticmethod
    async def get_or_create_wallet(db: AsyncSession, user_id: UUID) -> Wallet:
        """Obtiene o inicializa de forma idempotente la billetera del miembro."""
        stmt = select(Wallet).where(Wallet.user_id == user_id)
        result = await db.execute(stmt)
        wallet = result.scalar_one_or_none()
        if not wallet:
            wallet = Wallet(user_id=user_id, balance=0, escrow_balance=0)
            db.add(wallet)
            await db.flush()
        return wallet

    @classmethod
    async def get_balance(cls, db: AsyncSession, user_id: UUID) -> WalletBalanceData:
        """Calcula el balance actual, escrow y puntos provenientes de propinas/clases."""
        wallet = await cls.get_or_create_wallet(db, user_id)

        # Puntos acumulados por enseñanza y propinas (elegibles para cashout)
        rewards_stmt = select(func.coalesce(func.sum(PointTransaction.amount), 0)).where(
            PointTransaction.user_id == user_id,
            PointTransaction.transaction_type.in_([PointTransactionType.CLASS_PAYMENT.value, PointTransactionType.TIP.value]),
            PointTransaction.amount > 0,
        )
        rewards_result = await db.execute(rewards_stmt)
        earned_rewards = rewards_result.scalar_one()

        # Restar los cashouts ya efectuados para obtener el saldo canjeable remanente
        cashout_stmt = select(func.coalesce(func.sum(CashoutRequest.points_amount), 0)).where(
            CashoutRequest.user_id == user_id,
            CashoutRequest.status.in_([CashoutStatus.PENDING.value, CashoutStatus.APPROVED.value]),
        )
        cashout_result = await db.execute(cashout_stmt)
        used_cashout = cashout_result.scalar_one()

        rewards_balance = max(0, min(wallet.balance, earned_rewards - used_cashout))
        usd_rate = settings.WALLET_POINTS_PER_USD
        usd_equivalent = round(wallet.balance / float(usd_rate), 2)

        return WalletBalanceData(
            balance=wallet.balance,
            available_balance=wallet.balance,
            escrow_balance=wallet.escrow_balance,
            rewards_balance=rewards_balance,
            total_balance=wallet.balance + wallet.escrow_balance,
            usd_equivalent=usd_equivalent,
            exchange_rate=f"{usd_rate} SP = $1.00 USD",
            points_per_usd=usd_rate,
            cashout_min_points=settings.WALLET_CASHOUT_MIN_POINTS,
            platform_fee_percentage=float(settings.WALLET_PLATFORM_FEE_PERCENTAGE),
        )

    @classmethod
    async def topup_wallet(cls, db: AsyncSession, user_id: UUID, payload: TopupRequest) -> TopupResult:
        """Procesa una recarga de puntos vía pasarela de pago o sandbox."""
        pkg = PACKAGES_CATALOG.get(payload.package_id)
        if not pkg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Paquete de puntos '{payload.package_id}' no encontrado.",
            )

        wallet = await cls.get_or_create_wallet(db, user_id)

        # Transacción contable
        total_to_add = pkg.total_points
        wallet.balance += total_to_add

        tx_id = uuid4()
        now = datetime.now(UTC)
        receipt = f"REC-{now.strftime('%Y%m%d')}-{tx_id.hex[:6].upper()}"

        card_detail = f"Tarjeta •••• {payload.card_last_four}" if payload.card_last_four and payload.payment_method == "card" else ("PayPal" if payload.payment_method == "paypal" else "Pasarela")
        description = (
            f"Adquisición de {pkg.name} (+{pkg.points} SP"
            + (f" +{pkg.bonus_points} Bonus" if pkg.bonus_points > 0 else "")
            + f") · Pago con {card_detail} de ${pkg.price_usd:.2f} USD"
        )

        # Simular latencia realista de procesamiento bancario seguro (~800ms)
        await asyncio.sleep(0.8)

        transaction = PointTransaction(
            id=tx_id,
            user_id=user_id,
            amount=total_to_add,
            balance_after=wallet.balance,
            escrow_after=wallet.escrow_balance,
            transaction_type=PointTransactionType.TOPUP.value,
            reference_id=tx_id,
            description=description,
        )
        db.add(transaction)

        # Emisión de notificación in-app y push en tiempo real
        await NotificationService.emit_in_app(
            db,
            user_id=user_id,
            event_id=tx_id,
            notification_type=NotificationType.POINTS_RECEIVED,
            title="Recarga de SkillPoints Exitosa",
            message=f"Se han acreditado +{total_to_add} SP en tu billetera ({pkg.name}). Saldo disponible: {wallet.balance} SP.",
        )

        await db.commit()
        await db.refresh(wallet)

        # Despacho de notificación push nativa a Firebase (FCM)
        try:
            await FCMService.send_push_to_user(
                db,
                user_id=user_id,
                title="Recarga de SkillPoints Exitosa",
                body=f"Se han acreditado +{total_to_add} SP en tu billetera ({pkg.name}). Saldo disponible: {wallet.balance} SP.",
                data={
                    "type": "wallet_topup",
                    "transaction_id": str(tx_id),
                    "amount": str(total_to_add),
                },
            )
        except Exception as fcm_err:  # noqa: BLE001
            logger.warning(f"No se pudo enviar push FCM tras recarga: {fcm_err}")

        return TopupResult(
            transaction_id=tx_id,
            package_id=pkg.package_id,
            points_added=pkg.points,
            bonus_points=pkg.bonus_points,
            total_points_added=total_to_add,
            new_balance=wallet.balance,
            price_usd=pkg.price_usd,
            receipt_number=receipt,
            created_at=now,
        )

    @classmethod
    async def calculate_cashout(cls, db: AsyncSession, user_id: UUID, points_amount: int) -> CashoutCalculation:
        """Calcula de forma interactiva la comisión y el monto neto a transferir."""
        wallet = await cls.get_or_create_wallet(db, user_id)
        min_points = settings.WALLET_CASHOUT_MIN_POINTS
        fee_pct = Decimal(str(settings.WALLET_PLATFORM_FEE_PERCENTAGE))

        rate = Decimal(str(settings.WALLET_POINTS_PER_USD))
        gross = Decimal(points_amount) / rate
        fee = round(gross * (fee_pct / Decimal("100.0")), 2)
        net = round(gross - fee, 2)

        is_eligible = True
        ineligible_reason = None

        if points_amount < min_points:
            is_eligible = False
            ineligible_reason = f"El monto mínimo para solicitar retiro es de {min_points} SP (${float(min_points / rate):.2f} USD)."
        elif points_amount > wallet.balance:
            is_eligible = False
            ineligible_reason = f"Saldo insuficiente. Tu saldo disponible actual es de {wallet.balance} SP."

        return CashoutCalculation(
            points_amount=points_amount,
            gross_amount_usd=float(gross),
            fee_percentage=float(fee_pct),
            fee_amount_usd=float(fee),
            net_amount_usd=float(net),
            is_eligible=is_eligible,
            ineligible_reason=ineligible_reason,
        )

    @classmethod
    async def request_cashout(cls, db: AsyncSession, user_id: UUID, payload: CashoutCreateRequest) -> CashoutRequestItem:
        """Registra la solicitud formal de retiro bancario deduciendo los puntos de inmediato."""
        min_points = settings.WALLET_CASHOUT_MIN_POINTS
        if payload.points_amount < min_points:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El monto mínimo de retiro es de {min_points} SP.",
            )

        wallet = await cls.get_or_create_wallet(db, user_id)
        if wallet.balance < payload.points_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Saldo insuficiente. Tienes {wallet.balance} SP y solicitaste retirar {payload.points_amount} SP.",
            )

        # Cálculo financiero
        rate = Decimal(str(settings.WALLET_POINTS_PER_USD))
        gross = Decimal(payload.points_amount) / rate
        fee_pct = Decimal(str(settings.WALLET_PLATFORM_FEE_PERCENTAGE))
        fee = round(gross * (fee_pct / Decimal("100.0")), 2)
        net = round(gross - fee, 2)

        # Deducción de saldo
        wallet.balance -= payload.points_amount

        req_id = uuid4()

        cashout_req = CashoutRequest(
            id=req_id,
            user_id=user_id,
            points_amount=payload.points_amount,
            gross_amount_usd=gross,
            fee_percentage=fee_pct,
            fee_amount_usd=fee,
            net_amount_usd=net,
            status=CashoutStatus.PENDING.value,
            bank_name=payload.bank_name,
            account_number=payload.account_number,
            account_holder_name=payload.account_holder_name,
            account_holder_id=payload.account_holder_id,
        )
        db.add(cashout_req)

        # Auditoría contable (egreso)
        tx = PointTransaction(
            id=uuid4(),
            user_id=user_id,
            amount=-payload.points_amount,
            balance_after=wallet.balance,
            escrow_after=wallet.escrow_balance,
            transaction_type=PointTransactionType.CASHOUT.value,
            reference_id=req_id,
            description=f"Solicitud de retiro bancario a {payload.bank_name} (-{payload.points_amount} SP = ${float(net):.2f} USD netos)",
        )
        db.add(tx)

        # Emisión de notificación para solicitud de retiro
        await NotificationService.emit_in_app(
            db,
            user_id=user_id,
            event_id=req_id,
            notification_type=NotificationType.OTHER,
            title="Solicitud de Retiro Bancario Registrada",
            message=f"Tu solicitud de retiro por ${float(net):.2f} USD ({payload.points_amount} SP) ha sido recibida y se encuentra en revisión para transferencia a {payload.bank_name}.",
        )

        await db.commit()
        await db.refresh(cashout_req)

        # Despacho de notificación push nativa a Firebase (FCM)
        try:
            await FCMService.send_push_to_user(
                db,
                user_id=user_id,
                title="Solicitud de Retiro Registrada",
                body=f"Tu solicitud de retiro por ${float(net):.2f} USD ({payload.points_amount} SP) fue enviada a revisión.",
                data={"type": "wallet_cashout", "request_id": str(req_id)},
            )
        except Exception as fcm_err:  # noqa: BLE001
            logger.warning(f"No se pudo enviar push FCM tras solicitud de retiro: {fcm_err}")

        masked_account = (
            f"•••• {payload.account_number[-4:]}"
            if len(payload.account_number) >= 4
            else payload.account_number
        )

        return CashoutRequestItem(
            id=cashout_req.id,
            points_amount=cashout_req.points_amount,
            gross_amount_usd=float(cashout_req.gross_amount_usd),
            fee_percentage=float(cashout_req.fee_percentage),
            fee_amount_usd=float(cashout_req.fee_amount_usd),
            net_amount_usd=float(cashout_req.net_amount_usd),
            status=cashout_req.status,
            bank_name=cashout_req.bank_name,
            account_number_masked=masked_account,
            account_holder_name=cashout_req.account_holder_name,
            account_holder_id=cashout_req.account_holder_id,
            admin_notes=cashout_req.admin_notes,
            created_at=cashout_req.created_at,
            reviewed_at=cashout_req.reviewed_at,
        )

    @staticmethod
    async def list_transactions(
        db: AsyncSession,
        user_id: UUID,
        type_filter: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[PointTransactionItem], int]:
        """Devuelve el historial paginado de movimientos contables."""
        query = select(PointTransaction).where(PointTransaction.user_id == user_id)
        if type_filter and type_filter != "ALL":
            query = query.where(PointTransaction.transaction_type == type_filter)

        count_query = select(func.count()).select_from(query.subquery())
        count_res = await db.execute(count_query)
        total = count_res.scalar_one()

        query = query.order_by(PointTransaction.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        res = await db.execute(query)
        rows = res.scalars().all()

        items = [
            PointTransactionItem(
                id=r.id,
                amount=r.amount,
                balance_after=r.balance_after,
                escrow_after=r.escrow_after,
                transaction_type=r.transaction_type,
                reference_id=r.reference_id,
                description=r.description,
                created_at=r.created_at,
            )
            for r in rows
        ]
        return items, total

    @classmethod
    async def pay_session_escrow(cls, db: AsyncSession, user_id: UUID, session_id: UUID) -> SessionPayResult:
        """Retiene los puntos de una sesión no recíproca en custodia Escrow (RF-WAL-01)."""
        stmt = select(ExchangeSession).where(ExchangeSession.id == session_id)
        res = await db.execute(stmt)
        session = res.scalar_one_or_none()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sesión de intercambio no encontrada.",
            )

        if session.learner_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo el aprendiz de la sesión puede realizar el pago en puntos.",
            )

        if session.payment_state == "RESERVED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Los puntos para esta sesión ya se encuentran en custodia Escrow.",
            )

        if session.payment_state == "RELEASED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Esta sesión ya fue completada y los fondos ya fueron liberados.",
            )

        # Puntos requeridos de la sesión (por defecto 50 SP si no está explícito en la sesión de trueque)
        points_to_lock = session.points_required if (session.points_required and session.points_required > 0) else 50

        wallet = await cls.get_or_create_wallet(db, user_id)
        if wallet.balance < points_to_lock:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Saldo insuficiente ({wallet.balance} SP). Se requieren {points_to_lock} SP para asegurar esta clase.",
            )

        # Descontar de disponible y añadir a custodia
        wallet.balance -= points_to_lock
        wallet.escrow_balance += points_to_lock
        session.points_required = points_to_lock
        session.payment_state = "RESERVED"
        session.is_free = False

        # Registrar transacción contable de custodia
        tx = PointTransaction(
            id=uuid4(),
            user_id=user_id,
            amount=-points_to_lock,
            balance_after=wallet.balance,
            escrow_after=wallet.escrow_balance,
            transaction_type=PointTransactionType.CLASS_PAYMENT.value,
            reference_id=session.id,
            description=f"Depósito de garantía (Escrow) retenido para sesión de mentoría · {session.modality}",
        )
        db.add(tx)

        # Emisión de notificación para garantía Escrow retenida
        await NotificationService.emit_in_app(
            db,
            user_id=user_id,
            event_id=tx.id,
            notification_type=NotificationType.OTHER,
            title="Garantía Escrow Asegurada",
            message=f"Se aseguraron {points_to_lock} SP en custodia Escrow para tu sesión ({session.modality}). Fondos protegidos.",
        )

        await db.commit()
        await db.refresh(wallet)
        await db.refresh(session)

        # Despacho de notificación push nativa a Firebase (FCM)
        try:
            await FCMService.send_push_to_user(
                db,
                user_id=user_id,
                title="Garantía Escrow Asegurada",
                body=f"Se aseguraron {points_to_lock} SP en custodia Escrow para tu sesión ({session.modality}). Fondos protegidos.",
                data={"type": "session_escrow_locked", "session_id": str(session.id)},
            )
        except Exception as fcm_err:  # noqa: BLE001
            logger.warning(f"No se pudo enviar push FCM tras retener Escrow: {fcm_err}")

        return SessionPayResult(
            session_id=session.id,
            points_locked=points_to_lock,
            payment_state=session.payment_state,
            wallet_balance_after=wallet.balance,
            wallet_escrow_after=wallet.escrow_balance,
            message="Depósito de puntos retenido exitosamente en garantía Escrow.",
        )

    @classmethod
    async def release_session_escrow(cls, db: AsyncSession, session_id: UUID) -> None:
        """Libera automáticamente los puntos en custodia al tutor cuando la sesión se completa."""
        stmt = select(ExchangeSession).where(ExchangeSession.id == session_id)
        res = await db.execute(stmt)
        session = res.scalar_one_or_none()
        if not session or session.payment_state != "RESERVED":
            return

        points = session.points_required or 50

        # Disminuir custodia del aprendiz
        learner_wallet = await cls.get_or_create_wallet(db, session.learner_id)
        learner_wallet.escrow_balance = max(0, learner_wallet.escrow_balance - points)

        # Acreditar al tutor
        tutor_wallet = await cls.get_or_create_wallet(db, session.instructor_id)
        tutor_wallet.balance += points

        # Registrar ingreso en el tutor
        tx_tutor = PointTransaction(
            id=uuid4(),
            user_id=session.instructor_id,
            amount=points,
            balance_after=tutor_wallet.balance,
            escrow_after=tutor_wallet.escrow_balance,
            transaction_type=PointTransactionType.CLASS_PAYMENT.value,
            reference_id=session.id,
            description=f"Liberación de fondos de Escrow por clase completada exitosamente (+{points} SP)",
        )
        db.add(tx_tutor)
        session.payment_state = "RELEASED"

        # Emisión de notificación al tutor por fondos liberados
        await NotificationService.emit_in_app(
            db,
            user_id=session.instructor_id,
            event_id=tx_tutor.id,
            notification_type=NotificationType.POINTS_RECEIVED,
            title="Pago de Clase Recibido",
            message=f"Has recibido +{points} SP por completar exitosamente la sesión de mentoría. Fondos disponibles en tu billetera.",
        )

        await db.flush()


wallet_service = WalletService()
