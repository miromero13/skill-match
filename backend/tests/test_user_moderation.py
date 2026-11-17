from uuid import uuid4
from datetime import datetime, timezone
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.db.session import async_engine, get_db
from app.main import create_application
from app.models.catalog import Category, Skill
from app.models.match import Match
from app.models.match_proposal import MatchProposal
from app.models.teaching_skill import TeachingSkill
from app.models.user import ExchangeModality, User, UserRole
from app.models.user_block import UserBlock
from app.models.user_learning_skill import UserLearningSkill
from app.models.user_report import ReportReason, ReportStatus, UserReport


@pytest.mark.asyncio
async def test_user_block_unblock_and_matching_annulment():
    """Verifica bloqueo preventivo, anulación automática de trueques y desbloqueo (HU-26 / RF-MAT-14)."""
    suffix = uuid4().hex[:8]
    async with async_engine.connect() as connection:
        transaction = await connection.begin()
        try:
            async with AsyncSession(bind=connection, expire_on_commit=False) as db:
                user_a = User(
                    email=f"alice-{suffix}@skillmatch.local",
                    full_name="Alice Demandante",
                    role=UserRole.MEMBER,
                    is_active=True,
                )
                user_b = User(
                    email=f"bob-{suffix}@skillmatch.local",
                    full_name="Bob Infractor",
                    role=UserRole.MEMBER,
                    is_active=True,
                )
                db.add_all([user_a, user_b])
                await db.flush()

                # Crear un match previo y una propuesta pendiente entre A y B
                min_id, max_id = sorted([user_a.id, user_b.id])
                match = Match(member_a_id=min_id, member_b_id=max_id, status="pending")
                db.add(match)
                await db.flush()

                proposal = MatchProposal(
                    match_id=match.id,
                    proposed_by_id=user_b.id,
                    version=1,
                    starts_at=datetime.now(timezone.utc),
                    status="pending",
                )
                db.add(proposal)
                await db.flush()

                async def override_db():
                    yield db

                app = create_application()
                app.dependency_overrides[get_db] = override_db

                headers_a = {"Authorization": f"Bearer {create_access_token(str(user_a.id), 'MEMBER')}"}

                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url="http://testserver"
                ) as client:
                    # 1. Intentar auto-bloqueo debe dar 400
                    res_self = await client.post(
                        f"/api/users/{user_a.id}/block",
                        headers=headers_a,
                        json={"reason": "OTHER"},
                    )
                    assert res_self.status_code == 400

                    # 2. Bloquear exitosamente al usuario B (RF-MAT-14)
                    res_block = await client.post(
                        f"/api/users/{user_b.id}/block",
                        headers=headers_a,
                        json={"reason": "HARASSMENT", "notes": "Lenguaje ofensivo en chat"},
                    )
                    assert res_block.status_code == 200
                    body_block = res_block.json()
                    assert body_block["statuscode"] == 200
                    assert body_block["data"]["user_id"] == str(user_b.id)
                    assert "has bloqueado a bob infractor" in body_block["message"].lower()

                    # 3. Comprobar anulación automática en base de datos
                    await db.refresh(match)
                    await db.refresh(proposal)
                    assert match.status == "blocked"
                    assert proposal.status == "declined"

                    # 4. Listar usuarios bloqueados GET /api/users/blocked
                    res_list = await client.get("/api/users/blocked", headers=headers_a)
                    assert res_list.status_code == 200
                    body_list = res_list.json()
                    assert body_list["count"] == 1
                    assert body_list["data"][0]["user_id"] == str(user_b.id)
                    assert body_list["data"][0]["full_name"] == "Bob Infractor"

                    # 5. Consultar estado de seguridad /safety-status
                    res_safety = await client.get(
                        f"/api/users/{user_b.id}/safety-status", headers=headers_a
                    )
                    assert res_safety.status_code == 200
                    safety_data = res_safety.json()["data"]
                    assert safety_data["is_blocked_by_me"] is True
                    assert safety_data["can_interact"] is False

                    # 6. Desbloquear usuario DELETE /api/users/{id}/unblock
                    res_unblock = await client.delete(
                        f"/api/users/{user_b.id}/unblock", headers=headers_a
                    )
                    assert res_unblock.status_code == 200
                    assert "desbloqueado exitosamente" in res_unblock.json()["message"].lower()

                    # 7. Verificar que la lista de bloqueados ahora está vacía
                    res_list_after = await client.get("/api/users/blocked", headers=headers_a)
                    assert res_list_after.json()["count"] == 0
        finally:
            await transaction.rollback()
            await async_engine.dispose()


@pytest.mark.asyncio
async def test_user_report_to_moderation_queue():
    """Verifica el envío de reportes formales a la cola de moderación (HU-26 / RF-NOT-06)."""
    suffix = uuid4().hex[:8]
    async with async_engine.connect() as connection:
        transaction = await connection.begin()
        try:
            async with AsyncSession(bind=connection, expire_on_commit=False) as db:
                reporter = User(
                    email=f"reporter-{suffix}@skillmatch.local",
                    full_name="Carla Denunciante",
                    role=UserRole.MEMBER,
                    is_active=True,
                )
                reported = User(
                    email=f"reported-{suffix}@skillmatch.local",
                    full_name="David Estafador",
                    role=UserRole.MEMBER,
                    is_active=True,
                )
                db.add_all([reporter, reported])
                await db.flush()

                async def override_db():
                    yield db

                app = create_application()
                app.dependency_overrides[get_db] = override_db
                headers = {"Authorization": f"Bearer {create_access_token(str(reporter.id), 'MEMBER')}"}

                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url="http://testserver"
                ) as client:
                    # 1. Enviar reporte con descripción válida y bloqueo automático
                    payload = {
                        "reason": "PAYMENT_OUTSIDE",
                        "description": "El usuario me exigió un depósito bancario externo de $50 USD en lugar de usar puntos.",
                        "evidence_url": "https://pruebas.skillmatch.local/evidencia1.png",
                        "block_user": True,
                    }
                    res = await client.post(
                        f"/api/users/{reported.id}/report",
                        headers=headers,
                        json=payload,
                    )
                    assert res.status_code == 201
                    body = res.json()
                    assert body["statuscode"] == 201
                    assert body["data"]["reported_id"] == str(reported.id)
                    assert body["data"]["reason"] == "PAYMENT_OUTSIDE"
                    assert body["data"]["status"] == "PENDING"
                    assert body["data"]["user_blocked"] is True

                    # 2. Verificar que el reporte se persistió en la tabla user_reports
                    report_in_db = await db.scalar(
                        select(UserReport).where(
                            UserReport.reporter_id == reporter.id,
                            UserReport.reported_id == reported.id,
                        )
                    )
                    assert report_in_db is not None
                    assert report_in_db.status == "PENDING"
                    assert "depósito bancario" in report_in_db.description

                    # 3. Verificar que el usuario reportado también fue bloqueado preventivamente
                    block_in_db = await db.scalar(
                        select(UserBlock).where(
                            UserBlock.blocker_id == reporter.id,
                            UserBlock.blocked_id == reported.id,
                        )
                    )
                    assert block_in_db is not None
        finally:
            await transaction.rollback()
            await async_engine.dispose()


@pytest.mark.asyncio
async def test_blocked_user_exclusion_in_search_and_matches():
    """Verifica que los usuarios bloqueados queden excluidos inmediatamente de búsquedas y matches (RF-MAT-14)."""
    suffix = uuid4().hex[:8]
    async with async_engine.connect() as connection:
        transaction = await connection.begin()
        try:
            async with AsyncSession(bind=connection, expire_on_commit=False) as db:
                category = Category(name=f"Categoría {suffix}", slug=f"cat-{suffix}")
                db.add(category)
                await db.flush()

                skill = Skill(name=f"Habilidad {suffix}", slug=f"sk-{suffix}", category_id=category.id, is_active=True)
                db.add(skill)
                await db.flush()

                user_seeker = User(
                    email=f"seeker-{suffix}@skillmatch.local",
                    full_name="Usuario Buscador",
                    role=UserRole.MEMBER,
                    is_active=True,
                )
                user_tutor = User(
                    email=f"tutor-{suffix}@skillmatch.local",
                    full_name="Tutor Bloqueable",
                    role=UserRole.MEMBER,
                    is_active=True,
                )
                db.add_all([user_seeker, user_tutor])
                await db.flush()

                # Tutor enseña la habilidad
                ts = TeachingSkill(
                    user_id=user_tutor.id,
                    skill_id=skill.id,
                    declared_level="ADVANCED",
                    years_of_experience=3,
                    status="VERIFICADA",
                )
                db.add(ts)
                await db.flush()

                async def override_db():
                    yield db

                app = create_application()
                app.dependency_overrides[get_db] = override_db
                headers = {"Authorization": f"Bearer {create_access_token(str(user_seeker.id), 'MEMBER')}"}

                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url="http://testserver"
                ) as client:
                    # 1. Búsqueda antes de bloquear: el tutor aparece
                    res_search_1 = await client.get(
                        f"/api/search/tutors?skill_id={skill.id}", headers=headers
                    )
                    assert res_search_1.status_code == 200
                    ids_before = [t["id"] for t in res_search_1.json()["data"]]
                    assert str(user_tutor.id) in ids_before

                    # 2. Bloquear al tutor
                    await client.post(
                        f"/api/users/{user_tutor.id}/block",
                        headers=headers,
                        json={"reason": "HARASSMENT"},
                    )

                    # 3. Búsqueda después de bloquear: el tutor queda excluido inmediatamente (RF-MAT-14)
                    res_search_2 = await client.get(
                        f"/api/search/tutors?skill_id={skill.id}", headers=headers
                    )
                    assert res_search_2.status_code == 200
                    ids_after = [t["id"] for t in res_search_2.json()["data"]]
                    assert str(user_tutor.id) not in ids_after
        finally:
            await transaction.rollback()
            await async_engine.dispose()
