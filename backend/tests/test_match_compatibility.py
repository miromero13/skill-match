from uuid import uuid4
from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.db.session import async_engine, get_db
from app.main import create_application
from app.models.catalog import Category, Skill
from app.models.match import Match
from app.models.teaching_skill import TeachingSkill
from app.models.user import ExchangeModality, User, UserRole
from app.models.user_availability import UserAvailability
from app.models.user_learning_skill import UserLearningSkill


@pytest.mark.asyncio
async def test_match_compatibility_calculation_and_factors():
    """Verifica el cálculo determinístico del score ponderado y desglose de factores (HU-22 / RF-MAT-04, RF-MAT-06)."""
    suffix = uuid4().hex[:8]
    async with async_engine.connect() as connection:
        transaction = await connection.begin()
        try:
            async with AsyncSession(bind=connection, expire_on_commit=False) as db:
                category = Category(name="Música y Programación", slug=f"cat-{suffix}")
                member_a = User(
                    email=f"ana-{suffix}@skillmatch.local",
                    full_name="Ana Programadora",
                    role=UserRole.MEMBER,
                    exchange_modality=ExchangeModality.VIRTUAL,
                    is_active=True,
                    biometric_enrolled_at=datetime.now(timezone.utc),
                )
                member_b = User(
                    email=f"bruno-{suffix}@skillmatch.local",
                    full_name="Bruno Músico",
                    role=UserRole.MEMBER,
                    exchange_modality=ExchangeModality.VIRTUAL,
                    is_active=True,
                )
                member_c = User(
                    email=f"carlos-ajeno-{suffix}@skillmatch.local",
                    full_name="Carlos Ajeno",
                    role=UserRole.MEMBER,
                    is_active=True,
                )
                db.add_all([category, member_a, member_b, member_c])
                await db.flush()

                # Habilidades
                skill_python = Skill(
                    name="Python Backend", slug=f"python-{suffix}", category_id=category.id, is_active=True
                )
                skill_guitar = Skill(
                    name="Guitarra Clásica", slug=f"guitar-{suffix}", category_id=category.id, is_active=True
                )
                db.add_all([skill_python, skill_guitar])
                await db.flush()

                # Reciprocidad: A enseña Python y busca Guitarra; B enseña Guitarra y busca Python
                # Ana tiene Python VERIFICADA con 4 años de exp
                ts_a = TeachingSkill(
                    user_id=member_a.id,
                    skill_id=skill_python.id,
                    declared_level="ADVANCED",
                    years_of_experience=4,
                    status="VERIFICADA",
                )
                ts_b = TeachingSkill(
                    user_id=member_b.id,
                    skill_id=skill_guitar.id,
                    declared_level="INTERMEDIATE",
                    years_of_experience=3,
                    status="DECLARADA",
                )
                ls_a = UserLearningSkill(
                    user_id=member_a.id, skill_id=skill_guitar.id, current_level=1, target_level=3
                )
                ls_b = UserLearningSkill(
                    user_id=member_b.id, skill_id=skill_python.id, current_level=1, target_level=2
                )
                db.add_all([ts_a, ts_b, ls_a, ls_b])

                # Disponibilidad horaria coincidente el fin de semana (Sábado = día 5)
                # Ana: Sábado 10:00 - 14:00
                # Bruno: Sábado 11:00 - 13:00
                av_a = UserAvailability(
                    user_id=member_a.id,
                    day_of_week=5,
                    start_time="10:00",
                    end_time="14:00",
                    is_enabled=True,
                    modality="VIRTUAL",
                )
                av_b = UserAvailability(
                    user_id=member_b.id,
                    day_of_week=5,
                    start_time="11:00",
                    end_time="13:00",
                    is_enabled=True,
                    modality="VIRTUAL",
                )
                db.add_all([av_a, av_b])
                await db.flush()

                # Crear Match entre A y B (ordenado member_a_id < member_b_id)
                first_id, second_id = sorted([member_a.id, member_b.id])
                match = Match(member_a_id=first_id, member_b_id=second_id, status="pending")
                db.add(match)
                await db.flush()

                async def override_db():
                    yield db

                app = create_application()
                app.dependency_overrides[get_db] = override_db

                headers_a = {"Authorization": f"Bearer {create_access_token(str(member_a.id), 'MEMBER')}"}
                headers_b = {"Authorization": f"Bearer {create_access_token(str(member_b.id), 'MEMBER')}"}
                headers_c = {"Authorization": f"Bearer {create_access_token(str(member_c.id), 'MEMBER')}"}

                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url="http://testserver"
                ) as client:
                    # 1. Verificación anónima
                    res_anon = await client.get(f"/api/matches/{match.id}/compatibility")
                    assert res_anon.status_code == 401

                    # 2. Solicitud exitosa por el miembro A participante
                    res_a = await client.get(f"/api/matches/{match.id}/compatibility", headers=headers_a)
                    assert res_a.status_code == 200
                    body_a = res_a.json()
                    assert body_a["statuscode"] == 200
                    data_a = body_a["data"]

                    assert data_a["match_id"] == str(match.id)
                    assert data_a["counterpart_id"] == str(member_b.id)
                    assert data_a["counterpart_name"] == "Bruno Músico"

                    # Score global ponderado
                    score = data_a["compatibility_score"]
                    assert 80 <= score <= 100

                    # Matriz de factores
                    factors = data_a["factors"]
                    assert factors["skill_affinity"]["weight"] == 40
                    assert factors["schedule_overlap"]["weight"] == 25
                    assert factors["modality_location"]["weight"] == 20
                    assert factors["reputation_verification"]["weight"] == 15

                    # Explicabilidad y razones
                    reasons = data_a["match_reasons"]
                    assert any("fines de semana" in r.lower() for r in reasons)
                    assert any("verificada" in r.lower() for r in reasons)

                    # 3. Solicitud exitosa por el miembro B participante (bidireccional)
                    res_b = await client.get(f"/api/matches/{match.id}/compatibility", headers=headers_b)
                    assert res_b.status_code == 200
                    data_b = res_b.json()["data"]
                    assert data_b["counterpart_name"] == "Ana Programadora"
                    assert data_b["compatibility_score"] == score

                    # 4. Política estricta de Ofuscación 404: Tercero ajeno C recibe 404
                    res_c = await client.get(f"/api/matches/{match.id}/compatibility", headers=headers_c)
                    assert res_c.status_code == 404
                    assert "no encontrado" in res_c.json()["message"].lower()

                    # 5. Compatibilidad directa por usuario (para tarjeta o vista previa)
                    res_direct = await client.get(
                        f"/api/matches/user/{member_b.id}/compatibility", headers=headers_a
                    )
                    assert res_direct.status_code == 200
                    assert res_direct.json()["data"]["compatibility_score"] == score
        finally:
            await transaction.rollback()
            await async_engine.dispose()
