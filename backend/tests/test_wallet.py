"""Pruebas de Billetera, Recargas de Puntos, Escrow y Cashout (HU-42 / RF-SES-09 / RF-WAL-01 / RF-WAL-02)."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.session import get_db

from app.core.config import settings
from app.core.security import create_access_token
from app.main import app
from app.models.catalog import Category, Skill
from app.models.exchange_session import ExchangeSession
from app.models.match import Match
from app.models.teaching_skill import TeachingSkill
from app.models.user import User, UserRole
from app.models.wallet import (
    CashoutRequest,
    CashoutStatus,
    PointTransaction,
    PointTransactionType,
    Wallet,
)
from app.schemas.wallet import CashoutCreateRequest, TopupRequest
from app.services.wallet_service import PACKAGES_CATALOG, wallet_service


@pytest.fixture
async def async_engine():
    """Keep pooled connections on the event loop that created them."""
    engine = create_async_engine(settings.async_database_url)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_wallet_balance_and_packages(async_engine):
    """Verifica balance inicial idempotente y listado de paquetes de recarga (RF-SES-09)."""
    user_id = uuid4()
    async with async_engine.connect() as connection:
        trans = await connection.begin()
        try:
            async with AsyncSession(bind=connection, expire_on_commit=False) as db:
                user = User(
                    id=user_id,
                    email=f"member_{uuid4().hex[:6]}@example.com",
                    full_name="Usuario Billetera",
                    role=UserRole.MEMBER,
                    is_active=True,
                    is_locked=False,
                )
                db.add(user)
                await db.flush()

                balance_data = await wallet_service.get_balance(db, user_id)
                assert balance_data.balance == 0
                assert balance_data.escrow_balance == 0
                assert balance_data.rewards_balance == 0
                assert balance_data.usd_equivalent == 0.0
                assert balance_data.points_per_usd == 10
                assert balance_data.cashout_min_points == 100
                assert balance_data.platform_fee_percentage == 15.0

                packages = wallet_service.get_available_packages()
                assert len(packages) >= 4
                pkg_student = next(p for p in packages if p.package_id == "pkg_student")
                assert pkg_student.points == 250
                assert pkg_student.bonus_points == 25
                assert pkg_student.total_points == 275
                assert pkg_student.is_popular is True
        finally:
            await trans.rollback()


@pytest.mark.asyncio
async def test_wallet_topup_and_cashout_flow(async_engine):
    """Verifica recarga de puntos con pasarela simulada y retiro bancario con comisión 15% (RF-WAL-02)."""
    user_id = uuid4()
    async with async_engine.connect() as connection:
        trans = await connection.begin()
        try:
            async with AsyncSession(bind=connection, expire_on_commit=False) as db:
                user = User(
                    id=user_id,
                    email=f"member_{uuid4().hex[:6]}@example.com",
                    full_name="Usuario Topup",
                    role=UserRole.MEMBER,
                    is_active=True,
                    is_locked=False,
                )
                db.add(user)
                await db.flush()

                # 1. Recargar Paquete Estudiante (250 + 25 = 275 SP)
                topup_res = await wallet_service.topup_wallet(
                    db,
                    user_id,
                    TopupRequest(package_id="pkg_student", payment_method="card", card_last_four="4242"),
                )
                assert topup_res.total_points_added == 275
                assert topup_res.new_balance == 275
                assert topup_res.receipt_number.startswith("REC-")

                # 2. Verificar cálculo interactivo de retiro para 100 SP
                calc = await wallet_service.calculate_cashout(db, user_id, 100)
                assert calc.is_eligible is True
                assert calc.gross_amount_usd == 10.0
                assert calc.fee_amount_usd == 1.50
                assert calc.net_amount_usd == 8.50
                assert calc.fee_percentage == 15.0

                # 3. Solicitar retiro de 100 SP
                cashout_res = await wallet_service.request_cashout(
                    db,
                    user_id,
                    CashoutCreateRequest(
                        points_amount=100,
                        bank_name="Banco Santander",
                        account_number="12345678901234",
                        account_holder_name="Usuario Topup",
                        account_holder_id="CI-99887766",
                    ),
                )
                assert cashout_res.points_amount == 100
                assert cashout_res.gross_amount_usd == 10.0
                assert cashout_res.fee_amount_usd == 1.50
                assert cashout_res.net_amount_usd == 8.50
                assert cashout_res.status == "PENDING"
                assert cashout_res.bank_name == "Banco Santander"
                assert cashout_res.account_number_masked == "•••• 1234"

                # 4. Verificar nuevo saldo disponible (275 - 100 = 175 SP)
                balance_after = await wallet_service.get_balance(db, user_id)
                assert balance_after.balance == 175

                # 5. Listar movimientos contables
                txs, total = await wallet_service.list_transactions(db, user_id)
                assert total == 2
                types = [t.transaction_type for t in txs]
                assert PointTransactionType.CASHOUT.value in types
                assert PointTransactionType.TOPUP.value in types
        finally:
            await trans.rollback()


@pytest.mark.asyncio
async def test_wallet_cashout_insufficient_balance_rejected(async_engine):
    """Valida rechazo si no se cuenta con saldo suficiente o si es inferior al mínimo."""
    user_id = uuid4()
    async with async_engine.connect() as connection:
        trans = await connection.begin()
        try:
            async with AsyncSession(bind=connection, expire_on_commit=False) as db:
                user = User(
                    id=user_id,
                    email=f"member_{uuid4().hex[:6]}@example.com",
                    full_name="Usuario Pobre",
                    role=UserRole.MEMBER,
                    is_active=True,
                    is_locked=False,
                )
                db.add(user)
                await db.flush()

                # Intento de retiro por debajo del mínimo (ej. 50 SP < 100 SP)
                with pytest.raises(Exception) as exc:
                    await wallet_service.request_cashout(
                        db,
                        user_id,
                        CashoutCreateRequest(
                            points_amount=50,
                            bank_name="Banco",
                            account_number="123456",
                            account_holder_name="Persona",
                            account_holder_id="CI-12345",
                        ),
                    )
                assert "mínimo de retiro es de 100 SP" in str(exc.value)

                # Intento de retiro con saldo 0
                with pytest.raises(Exception) as exc:
                    await wallet_service.request_cashout(
                        db,
                        user_id,
                        CashoutCreateRequest(
                            points_amount=100,
                            bank_name="Banco",
                            account_number="123456",
                            account_holder_name="Persona",
                            account_holder_id="CI-12345",
                        ),
                    )
                assert "Saldo insuficiente" in str(exc.value)
        finally:
            await trans.rollback()


@pytest.mark.asyncio
async def test_session_escrow_locking_and_release(async_engine):
    """Verifica retención en Escrow al pagar sesión y liberación automática al tutor al completarse (RF-WAL-01)."""
    learner_id = uuid4()
    instructor_id = uuid4()
    match_id = uuid4()
    category_id = uuid4()
    skill_id = uuid4()
    teaching_skill_id = uuid4()
    session_id = uuid4()

    async with async_engine.connect() as connection:
        trans = await connection.begin()
        try:
            async with AsyncSession(bind=connection, expire_on_commit=False) as db:
                learner = User(
                    id=learner_id,
                    email=f"learner_{uuid4().hex[:6]}@example.com",
                    full_name="Aprendiz Escrow",
                    role=UserRole.MEMBER,
                    is_active=True,
                    is_locked=False,
                )
                instructor = User(
                    id=instructor_id,
                    email=f"tutor_{uuid4().hex[:6]}@example.com",
                    full_name="Tutor Escrow",
                    role=UserRole.MEMBER,
                    is_active=True,
                    is_locked=False,
                )
                db.add_all([learner, instructor])
                await db.flush()

                cat = Category(id=category_id, name=f"Cat_{uuid4().hex[:4]}", slug=f"cat-{uuid4().hex[:6]}")
                db.add(cat)
                await db.flush()
                sk = Skill(id=skill_id, name="Programación FastAPI", slug=f"skill-{uuid4().hex[:6]}", category_id=category_id)
                db.add(sk)
                await db.flush()
                ts = TeachingSkill(id=teaching_skill_id, user_id=instructor_id, skill_id=skill_id, declared_level="ADVANCED", years_of_experience=3)
                db.add(ts)
                await db.flush()

                m_a = min(learner_id, instructor_id)
                m_b = max(learner_id, instructor_id)
                match_obj = Match(id=match_id, member_a_id=m_a, member_b_id=m_b, status="confirmed")
                db.add(match_obj)
                await db.flush()

                now = datetime.now(timezone.utc)
                session_obj = ExchangeSession(
                    id=session_id,
                    match_id=match_id,
                    teaching_skill_id=teaching_skill_id,
                    created_by_id=learner_id,
                    instructor_id=instructor_id,
                    learner_id=learner_id,
                    starts_at=now,
                    ends_at=now + timedelta(minutes=60),
                    timezone="UTC",
                    modality="VIRTUAL",
                    status="ACCEPTED",
                    is_free=False,
                    points_required=50,
                    payment_state="PENDING",
                )
                db.add(session_obj)

                # Cargar saldo al aprendiz (100 SP)
                await wallet_service.topup_wallet(
                    db,
                    learner_id,
                    TopupRequest(package_id="pkg_basic", payment_method="card"),
                )

                # 1. Pagar y retener fondos en Escrow
                pay_res = await wallet_service.pay_session_escrow(db, learner_id, session_id)
                assert pay_res.points_locked == 50
                assert pay_res.payment_state == "RESERVED"
                assert pay_res.wallet_balance_after == 50
                assert pay_res.wallet_escrow_after == 50

                # Verificar balance del aprendiz
                l_bal = await wallet_service.get_balance(db, learner_id)
                assert l_bal.balance == 50
                assert l_bal.escrow_balance == 50

                # 2. Liberar fondos de Escrow al tutor
                await wallet_service.release_session_escrow(db, session_id)

                # Saldo tutor debe tener +50 SP
                t_bal = await wallet_service.get_balance(db, instructor_id)
                assert t_bal.balance == 50

                # Custodia del aprendiz debe volver a 0
                l_bal_final = await wallet_service.get_balance(db, learner_id)
                assert l_bal_final.escrow_balance == 0
                assert l_bal_final.balance == 50
        finally:
            await trans.rollback()


@pytest.mark.asyncio
async def test_wallet_api_endpoints(async_engine):
    """Verifica endpoints REST documentados de la Billetera en /api/wallet (Swagger/OpenAPI)."""
    session_factory = async_sessionmaker(async_engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    user_id = uuid4()
    async with session_factory() as db:
        user = User(
            id=user_id,
            email=f"member_api_{uuid4().hex[:6]}@example.com",
            full_name="Usuario API Billetera",
            role=UserRole.MEMBER,
            is_active=True,
            is_locked=False,
        )
        db.add(user)
        await db.commit()

    try:
        token = create_access_token(subject=str(user_id), role=UserRole.MEMBER.value)
        headers = {"Authorization": f"Bearer {token}"}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # GET /api/wallet/balance
            resp = await client.get("/api/wallet/balance", headers=headers)
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["balance"] == 0
            assert data["exchange_rate"] == "10 SP = $1.00 USD"

            # GET /api/wallet/packages
            resp = await client.get("/api/wallet/packages", headers=headers)
            assert resp.status_code == 200
            pkgs = resp.json()["data"]
            assert len(pkgs) >= 4

            # POST /api/wallet/topup
            resp = await client.post(
                "/api/wallet/topup",
                headers=headers,
                json={"package_id": "pkg_basic", "payment_method": "card", "card_last_four": "1122"},
            )
            assert resp.status_code == 201
            res = resp.json()["data"]
            assert res["total_points_added"] == 100
            assert res["new_balance"] == 100

            # POST /api/wallet/cashout/calculate
            resp = await client.post(
                "/api/wallet/cashout/calculate",
                headers=headers,
                json={"points_amount": 100},
            )
            assert resp.status_code == 200
            calc = resp.json()["data"]
            assert calc["gross_amount_usd"] == 10.0
            assert calc["fee_amount_usd"] == 1.50
            assert calc["net_amount_usd"] == 8.50

            # POST /api/wallet/cashout
            resp = await client.post(
                "/api/wallet/cashout",
                headers=headers,
                json={
                    "points_amount": 100,
                    "bank_name": "Banco Santander",
                    "account_number": "98765432101234",
                    "account_holder_name": "Usuario API Billetera",
                    "account_holder_id": "CI-11223344",
                },
            )
            assert resp.status_code == 201
            cashout_data = resp.json()["data"]
            assert cashout_data["net_amount_usd"] == 8.50

            # GET /api/wallet/transactions
            resp = await client.get("/api/wallet/transactions", headers=headers)
            assert resp.status_code == 200
            body = resp.json()
            assert body["count"] == 2
            assert len(body["data"]) == 2
    finally:
        app.dependency_overrides.pop(get_db, None)
        async with session_factory() as db:
            await db.execute(User.__table__.delete().where(User.id == user_id))
            await db.commit()
