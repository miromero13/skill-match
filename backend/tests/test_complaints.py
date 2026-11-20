"""Pruebas del Centro de Quejas, Resolución Arbitral y Compensaciones (HU-43 / RF-GOV-01, 02, 03)."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.complaint import Complaint, ComplaintReason, ComplaintStatus
from app.models.exchange_session import ExchangeSession
from app.models.user import User, UserRole
from app.models.wallet import PointTransaction, PointTransactionType, Wallet
from app.schemas.complaint import ComplaintCreateRequest, ComplaintResolveRequest
from app.services.complaint_service import ComplaintService


@pytest.fixture
async def async_engine():
    engine = create_async_engine(settings.async_database_url)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_member_submit_complaint_and_list_my(async_engine):
    """Verifica que un miembro puede radicar una queja formal y consultar su historial (RF-GOV-01)."""
    user_id = uuid4()
    async with async_engine.connect() as connection:
        trans = await connection.begin()
        try:
            async with AsyncSession(bind=connection, expire_on_commit=False) as db:
                user = User(
                    id=user_id,
                    email=f"member_{user_id.hex[:6]}@example.com",
                    full_name="Carlos Reclamante",
                    role=UserRole.MEMBER,
                    is_active=True,
                    is_locked=False,
                )
                db.add(user)
                await db.flush()

                # 1. Radicar queja
                payload = ComplaintCreateRequest(
                    title="Inasistencia injustificada a la sesión",
                    reason=ComplaintReason.NO_SHOW,
                    description="El instructor no se conectó tras 30 minutos de espera sin previo aviso.",
                    evidence_urls=["https://storage.example.com/screenshot1.png"],
                )
                created = await ComplaintService.create_complaint(db, user, payload)
                assert created.id is not None
                assert created.title == "Inasistencia injustificada a la sesión"
                assert created.status == ComplaintStatus.OPEN.value
                assert created.reason == ComplaintReason.NO_SHOW.value
                assert len(created.evidence_urls) == 1

                # 2. Consultar historial del miembro
                my_complaints, count = await ComplaintService.get_user_complaints(db, user_id=user.id)
                assert count == 1
                assert my_complaints[0].id == created.id
                assert my_complaints[0].points_compensated == 0
        finally:
            await trans.rollback()


@pytest.mark.asyncio
async def test_admin_resolve_complaint_with_point_compensation(async_engine):
    """Verifica el dictamen arbitral del admin con acreditación contable de SkillPoints (RF-GOV-02, RF-GOV-03)."""
    member_id = uuid4()
    admin_id = uuid4()
    async with async_engine.connect() as connection:
        trans = await connection.begin()
        try:
            async with AsyncSession(bind=connection, expire_on_commit=False) as db:
                member = User(
                    id=member_id,
                    email=f"victim_{member_id.hex[:6]}@example.com",
                    full_name="Ana Alumna",
                    role=UserRole.MEMBER,
                    is_active=True,
                    is_locked=False,
                )
                admin = User(
                    id=admin_id,
                    email=f"admin_{admin_id.hex[:6]}@example.com",
                    full_name="Super Admin",
                    role=UserRole.ADMIN,
                    is_active=True,
                    is_locked=False,
                )
                # Billetera inicial del miembro con 50 SP
                wallet = Wallet(user_id=member_id, balance=50, escrow_balance=0)
                db.add_all([member, admin, wallet])
                await db.flush()

                # Crear queja
                complaint = Complaint(
                    id=uuid4(),
                    user_id=member_id,
                    reason=ComplaintReason.TECHNICAL_FAILURE.value,
                    title="Corte reiterado de plataforma en clase",
                    description="El sistema se cayó 4 veces durante la llamada interactiva.",
                    status=ComplaintStatus.OPEN.value,
                )
                db.add(complaint)
                await db.flush()

                # Resolución administrativa con 75 SP de compensación
                resolve_payload = ComplaintResolveRequest(
                    status=ComplaintStatus.RESOLVED,
                    admin_response="Se verificó la caída del servidor en los logs. Procedemos a compensarte con 75 SP.",
                    points_to_compensate=75,
                )
                resolved = await ComplaintService.resolve_complaint(db, admin, complaint.id, resolve_payload)

                assert resolved.status == ComplaintStatus.RESOLVED.value
                assert resolved.points_compensated == 75
                assert resolved.resolved_by_name == "Super Admin"
                assert resolved.admin_response.startswith("Se verificó la caída")

                # Verificar billetera actualizada (50 + 75 = 125 SP)
                await db.refresh(wallet)
                assert wallet.balance == 125

                # Verificar transacción contable ADMIN_REWARD
                from sqlalchemy import select
                stmt = select(PointTransaction).where(
                    PointTransaction.user_id == member_id,
                    PointTransaction.transaction_type == PointTransactionType.ADMIN_REWARD.value,
                )
                tx = (await db.execute(stmt)).scalar_one()
                assert tx.amount == 75
                assert tx.balance_after == 125
                assert "Compensación arbitral" in tx.description
        finally:
            await trans.rollback()


@pytest.mark.asyncio
async def test_complaint_api_endpoints_and_404_obfuscation(async_engine):
    """Verifica endpoints HTTP, autorización de miembros y la política estricta de ofuscación 404."""
    member_id = uuid4()
    admin_id = uuid4()
    session_factory = async_sessionmaker(async_engine, expire_on_commit=False)

    async with session_factory() as db:
        member = User(
            id=member_id,
            email=f"user_{member_id.hex[:6]}@example.com",
            full_name="Mario Member",
            role=UserRole.MEMBER,
            is_active=True,
            is_locked=False,
        )
        admin = User(
            id=admin_id,
            email=f"admin_{admin_id.hex[:6]}@example.com",
            full_name="Laura Arbitro",
            role=UserRole.ADMIN,
            is_active=True,
            is_locked=False,
        )
        db.add_all([member, admin])
        await db.commit()

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    try:
        member_token = create_access_token(
            subject=str(member_id), role=UserRole.MEMBER.value
        )
        admin_token = create_access_token(
            subject=str(admin_id), role=UserRole.ADMIN.value
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Miembro radica queja exitosamente (POST /api/complaints)
            resp = await ac.post(
                "/api/complaints",
                headers={"Authorization": f"Bearer {member_token}"},
                json={
                    "title": "Cobro indebido de puntos",
                    "reason": "PAYMENT_DISPUTE",
                    "description": "Se me debitaron puntos sin haber confirmado la clase.",
                },
            )
            assert resp.status_code == 201
            body = resp.json()
            assert body["statuscode"] == 201
            complaint_id = body["data"]["id"]

            # 2. Miembro consulta sus quejas (GET /api/complaints/my)
            resp_my = await ac.get(
                "/api/complaints/my",
                headers={"Authorization": f"Bearer {member_token}"},
            )
            assert resp_my.status_code == 200
            assert resp_my.json()["count"] >= 1

            # 3. POLÍTICA 404: Miembro intenta consultar /api/admin/complaints -> 404 NOT FOUND
            resp_forbidden = await ac.get(
                "/api/admin/complaints",
                headers={"Authorization": f"Bearer {member_token}"},
            )
            assert resp_forbidden.status_code == 404
            assert resp_forbidden.json()["statuscode"] == 404
            assert resp_forbidden.json()["message"] == "Recurso no encontrado"

            # 4. POLÍTICA 404: Visitante anónimo intenta acceder a /api/admin/complaints -> 404 NOT FOUND
            resp_anon = await ac.get("/api/admin/complaints")
            assert resp_anon.status_code == 404
            assert resp_anon.json()["statuscode"] == 404
            assert resp_anon.json()["message"] == "Recurso no encontrado"

            # 5. Administrador legítimo consulta listado (GET /api/admin/complaints) -> 200 OK
            resp_admin = await ac.get(
                "/api/admin/complaints",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            if resp_admin.status_code != 200:
                print("422 detail:", resp_admin.json())
            assert resp_admin.status_code == 200
            assert resp_admin.json()["count"] >= 1

            # 6. Administrador resuelve queja (PATCH /api/admin/complaints/{id}/resolve)
            resp_resolve = await ac.patch(
                f"/api/admin/complaints/{complaint_id}/resolve",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={
                    "status": "RESOLVED",
                    "admin_response": "Disputa comprobada. Se ha corregido y devuelto la satisfacción del servicio.",
                    "points_to_compensate": 50,
                },
            )
            assert resp_resolve.status_code == 200
            assert resp_resolve.json()["data"]["status"] == "RESOLVED"
            assert resp_resolve.json()["data"]["points_compensated"] == 50
    finally:
        app.dependency_overrides.clear()
        async with session_factory() as db:
            from sqlalchemy import delete
            await db.execute(delete(PointTransaction).where(PointTransaction.user_id == member_id))
            await db.execute(delete(Complaint).where(Complaint.user_id == member_id))
            await db.execute(delete(Wallet).where(Wallet.user_id == member_id))
            await db.execute(delete(User).where(User.id.in_([member_id, admin_id])))
            await db.commit()
