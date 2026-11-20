"""Pruebas del Asistente Virtual Inteligente (Tool Calling, Memoria, RBAC y Obfuscation 404)."""
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.catalog import Category, Skill
from app.models.teaching_skill import TeachingSkill
from app.models.user import User, UserRole
from app.models.wallet import Wallet
from app.services.assistant_service import AssistantService


@pytest.fixture
async def async_engine():
    """Motor de base de datos asíncrono para pruebas."""
    engine = create_async_engine(settings.async_database_url)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_assistant_faq_tool():
    """Verifica que la herramienta de FAQ responde coherentemente a temas clave."""
    service = AssistantService()

    faq_escrow = service._tool_get_platform_faq("escrow")
    assert "Escrow" in faq_escrow["topic"]
    assert "protege" in faq_escrow["explanation"]

    faq_wallet = service._tool_get_platform_faq("puntos y billetera")
    assert "Economía" in faq_wallet["topic"]
    assert any("10 SkillPoints" in r for r in faq_wallet["rules"])

    faq_cancel = service._tool_get_platform_faq("cancelar sesión")
    assert "2 horas" in faq_cancel["explanation"]

    faq_kyc = service._tool_get_platform_faq("verificación kyc")
    assert "identidad" in faq_kyc["explanation"]


@pytest.mark.asyncio
async def test_assistant_memory_lifecycle():
    """Verifica el ciclo de vida de la memoria conversacional e historial."""
    service = AssistantService()
    test_uid = str(uuid4())

    history_empty = service.get_history(test_uid)
    assert len(history_empty) == 0

    # Simular guardado de mensaje
    service._conversations[test_uid] = [{"role": "user", "parts": [{"text": "Hola"}]}]
    from app.schemas.assistant import ChatHistoryItem
    service._history_items[test_uid] = [
        ChatHistoryItem(
            id="1",
            role="user",
            content="Hola",
            timestamp=datetime.now(UTC),
        )
    ]

    history = service.get_history(test_uid)
    assert len(history) == 1
    assert history[0].content == "Hola"

    # Limpiar historial
    service.clear_history(test_uid)
    assert len(service.get_history(test_uid)) == 0


@pytest.mark.asyncio
async def test_assistant_actionable_skill_cards():
    """Verifica la generación de payloads de acción para creación de habilidades."""
    service = AssistantService()

    # 1. Action para Teaching Skill
    teaching_data = {
        "success": True,
        "action": "creada",
        "skill_name": "Programación en Python",
        "level": "ADVANCED",
        "experience_years": 4,
        "hourly_points_rate": 25,
        "accepts_points": True,
    }
    action_teaching = service._create_action_for_tool("create_my_teaching_skill", teaching_data)
    assert action_teaching is not None
    assert action_teaching.type == "skill_created"
    assert action_teaching.data["skill_name"] == "Programación en Python"

    summary_teaching = service._format_tool_direct_summary("create_my_teaching_skill", teaching_data)
    assert "Programación en Python" in summary_teaching
    assert "25 SP/h" in summary_teaching

    # 2. Action para Learning Skill
    learning_data = {
        "success": True,
        "action": "registrado",
        "skill_name": "Tocar flauta",
        "current_level": 1,
        "target_level": 3,
        "urgency": "HIGH",
    }
    action_learning = service._create_action_for_tool("create_my_learning_skill", learning_data)
    assert action_learning is not None
    assert action_learning.type == "learning_skill_created"
    assert action_learning.data["urgency"] == "HIGH"

    summary_learning = service._format_tool_direct_summary("create_my_learning_skill", learning_data)
    assert "Tocar flauta" in summary_learning
    assert "Nivel 1" in summary_learning
    assert "Nivel 3" in summary_learning


@pytest.mark.asyncio
async def test_assistant_tools_execution(async_engine):
    """Verifica la ejecución de las herramientas del dominio en base de datos."""
    async with async_engine.connect() as connection:
        trans = await connection.begin()
        try:
            async with AsyncSession(bind=connection, expire_on_commit=False) as db:
                user = User(
                    id=uuid4(),
                    email=f"member_{uuid4().hex[:8]}@example.com",
                    full_name="Usuario Asistente Test",
                    role=UserRole.MEMBER,
                    is_active=True,
                    identity_status="VERIFIED",
                )
                db.add(user)
                wallet = Wallet(user_id=user.id, balance=250, escrow_balance=50)
                db.add(wallet)

                cat = Category(
                    id=uuid4(),
                    name="Música Test",
                    slug=f"musica-test-{uuid4().hex[:6]}",
                )
                db.add(cat)
                await db.flush()

                skill = Skill(
                    id=uuid4(),
                    category_id=cat.id,
                    name="Violín Test",
                    slug=f"violin-test-{uuid4().hex[:6]}",
                )
                db.add(skill)
                await db.flush()

                ts = TeachingSkill(
                    id=uuid4(),
                    user_id=user.id,
                    skill_id=skill.id,
                    declared_level="INTERMEDIATE",
                    years_of_experience=4,
                    accepts_points=True,
                    hourly_points_rate=30,
                    status="VERIFICADA",
                )
                db.add(ts)
                await db.flush()

                service = AssistantService()

                # 1. Tool: get_my_profile_summary
                summary = await service.execute_tool("get_my_profile_summary", {}, db, user)
                assert summary["full_name"] == "Usuario Asistente Test"
                assert summary["is_verified_kyc"] is True
                assert summary["wallet"]["available_points"] == 250
                assert summary["wallet"]["escrow_points"] == 50

                # 2. Tool: search_instructors_and_skills
                search_res = await service.execute_tool(
                    "search_instructors_and_skills",
                    {"query": "Violín"},
                    db,
                    user,
                )
                assert search_res["found"] >= 1
                assert search_res["instructors"][0]["skill_name"] == "Violín Test"

                # 3. Tool: get_my_upcoming_sessions (sin sesiones creadas)
                sessions_res = await service.execute_tool("get_my_upcoming_sessions", {}, db, user)
                assert sessions_res["count"] == 0
        finally:
            await trans.rollback()


@pytest.mark.asyncio
async def test_assistant_chat_endpoint_member_and_obfuscation(async_engine):
    """Verifica autenticación de MEMBER y ofuscación 404 para ADMIN en /api/assistant/chat."""
    async with async_engine.connect() as connection:
        trans = await connection.begin()
        try:
            async with AsyncSession(bind=connection, expire_on_commit=False) as db:
                member = User(
                    id=uuid4(),
                    email=f"member_{uuid4().hex[:8]}@example.com",
                    full_name="Member Asistente",
                    role=UserRole.MEMBER,
                    is_active=True,
                )
                admin = User(
                    id=uuid4(),
                    email=f"admin_{uuid4().hex[:8]}@example.com",
                    full_name="Admin No Autorizado",
                    role=UserRole.ADMIN,
                    is_active=True,
                )
                db.add_all([member, admin])
                await db.flush()

                member_token = create_access_token(
                    subject=str(member.id), role=member.role.value
                )
                admin_token = create_access_token(
                    subject=str(admin.id), role=admin.role.value
                )

                async def override_get_db():
                    yield db

                app.dependency_overrides[get_db] = override_get_db

                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    # 1. Solicitud sin autenticación -> 401
                    resp_unauth = await client.post(
                        "/api/assistant/chat",
                        json={"message": "¿Cuál es mi saldo?"},
                    )
                    assert resp_unauth.status_code == 401

                    # 2. Solicitud con rol ADMIN -> 404 (Security by Obfuscation según AGENTS.md 1.3)
                    resp_admin = await client.post(
                        "/api/assistant/chat",
                        json={"message": "¿Cuál es mi saldo?"},
                        headers={"Authorization": f"Bearer {admin_token}"},
                    )
                    assert resp_admin.status_code == 404
                    assert resp_admin.json()["message"] == "Recurso no encontrado"

                    # 3. Solicitud con rol MEMBER -> 200 OK
                    resp_member = await client.post(
                        "/api/assistant/chat",
                        json={"message": "¿Cómo funciona el sistema de escrow?"},
                        headers={"Authorization": f"Bearer {member_token}"},
                    )
                    assert resp_member.status_code == 200
                    data = resp_member.json()
                    assert data["statuscode"] == 200
                    assert "Escrow" in data["data"]["reply"] or "custodia" in data["data"]["reply"].lower()

                    # 4. Historial para MEMBER
                    resp_hist = await client.get(
                        "/api/assistant/history",
                        headers={"Authorization": f"Bearer {member_token}"},
                    )
                    assert resp_hist.status_code == 200
                    assert resp_hist.json()["count"] >= 2

                    # 5. Borrado de historial
                    resp_del = await client.delete(
                        "/api/assistant/history",
                        headers={"Authorization": f"Bearer {member_token}"},
                    )
                    assert resp_del.status_code == 200

        finally:
            app.dependency_overrides.clear()
            await trans.rollback()
