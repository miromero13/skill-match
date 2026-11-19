"""HU-39: Script de Carga de Datos y Semilla Determinista para QA y Pruebas Visuales.

Propósito:
- Cargar un escenario reproducible y exhaustivo para probar visualmente la HU-39 (Confirmación y Cierre de Sesión).
- Permite la prueba visual en el Frontend sin requerir Google OAuth mediante snippets directos para la consola DevTools.
- Cubre todos los casos de uso:
  1. Sesión Virtual recién finalizada (lista para 1ra confirmación).
  2. Sesión Virtual con 1ra confirmación realizada (esperando contraparte / lista para completar con 50 min).
  3. Sesión Presencial con PINs deterministas derivados del secreto local.
  4. Sesión Virtual elegible para reporte de inasistencia (No-Show).
  5. Sesión Completada exitosamente (historial con badge verde esmeralda y 60 min efectivos).
  6. Sesión Futura programada (para contrastar que no permite confirmar antes de tiempo).
- Incluye bandera `--cleanup` para eliminar quirúrgicamente los datos generados.
"""

import argparse
import asyncio
import json
import sys
import uuid as _uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select

# Asegurar path de importación
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.catalog import Category, Skill
from app.models.exchange_session import (
    ExchangeSession,
    SessionAuditEvent,
    SessionConfirmation,
    SessionNoShowReport,
    SessionPresencePin,
)
from app.models.match import Match
from app.models.notification import Notification
from app.models.notification_preference import NotificationPreference
from app.models.teaching_skill import TeachingSkill
from app.models.user import User, UserRole
from app.models.user_learning_skill import UserLearningSkill
from app.models.wallet import Wallet
from app.services.session_completion_policy import generate_presence_pin, hash_presence_pin

QA_EMAILS = {
    "learner": "carlos.aprendiz.hu39@skillmatch.io",
    "instructor": "ana.instructora.hu39@skillmatch.io",
}

QA_CATEGORY_SLUG = "cat-hu39-qa"
QA_SKILL_SLUG = "skill-hu39-qa-react"

# Identificadores deterministas
QA_USER_CARLOS_ID = _uuid.UUID("a1111111-1111-4111-8111-111111111111")
QA_USER_ANA_ID = _uuid.UUID("b2222222-2222-4222-8222-222222222222")
QA_CATEGORY_ID = _uuid.UUID("c3333333-3333-4333-8333-333333333333")
QA_SKILL_ID = _uuid.UUID("d4444444-4444-4444-8444-444444444444")
QA_TEACHING_SKILL_ID = _uuid.UUID("e5555555-5555-4555-8555-555555555555")
QA_MATCH_ID = _uuid.UUID("f6666666-6666-4666-8666-666666666666")

# Sesiones deterministas
SESSION_1_ID = _uuid.UUID("11111111-3939-4000-8000-000000000001")
SESSION_2_ID = _uuid.UUID("22222222-3939-4000-8000-000000000002")
SESSION_3_ID = _uuid.UUID("33333333-3939-4000-8000-000000000003")
SESSION_4_ID = _uuid.UUID("44444444-3939-4000-8000-000000000004")
SESSION_5_ID = _uuid.UUID("55555555-3939-4000-8000-000000000005")
SESSION_6_ID = _uuid.UUID("66666666-3939-4000-8000-000000000006")


def assert_not_production():
    env = (getattr(settings, "ENVIRONMENT", "") or "").strip().lower()
    if env in ("production", "prod"):
        print("\n[ERROR CRÍTICO] seed_hu39_qa.py no puede ejecutarse en PRODUCCIÓN.")
        sys.exit(1)


async def cleanup_qa_data(db) -> dict[str, int]:
    """Elimina quirúrgicamente las entidades asociadas a los identificadores QA de HU-39."""
    stats = {}
    user_ids = [QA_USER_CARLOS_ID, QA_USER_ANA_ID]

    users = (
        await db.scalars(
            select(User).where((User.email.in_(list(QA_EMAILS.values()))) | (User.id.in_(user_ids)))
        )
    ).all()
    all_user_ids = list(set([u.id for u in users] + user_ids))

    if all_user_ids:
        # 1. Sesiones de los usuarios
        sessions = (
            await db.scalars(
                select(ExchangeSession).where(
                    (ExchangeSession.instructor_id.in_(all_user_ids))
                    | (ExchangeSession.learner_id.in_(all_user_ids))
                )
            )
        ).all()
        session_ids = [s.id for s in sessions]

        if session_ids:
            res_conf = await db.execute(
                delete(SessionConfirmation).where(SessionConfirmation.session_id.in_(session_ids))
            )
            stats["session_confirmations"] = res_conf.rowcount

            res_pin = await db.execute(
                delete(SessionPresencePin).where(SessionPresencePin.session_id.in_(session_ids))
            )
            stats["session_presence_pins"] = res_pin.rowcount

            res_ns = await db.execute(
                delete(SessionNoShowReport).where(SessionNoShowReport.session_id.in_(session_ids))
            )
            stats["session_no_show_reports"] = res_ns.rowcount

            res_audit = await db.execute(
                delete(SessionAuditEvent).where(SessionAuditEvent.session_id.in_(session_ids))
            )
            stats["session_audit_events"] = res_audit.rowcount

            res_sess = await db.execute(
                delete(ExchangeSession).where(ExchangeSession.id.in_(session_ids))
            )
            stats["exchange_sessions"] = res_sess.rowcount

        # 2. Notificaciones y preferencias
        res_notif = await db.execute(
            delete(Notification).where(Notification.user_id.in_(all_user_ids))
        )
        stats["notifications"] = res_notif.rowcount

        res_pref = await db.execute(
            delete(NotificationPreference).where(NotificationPreference.user_id.in_(all_user_ids))
        )
        stats["notification_preferences"] = res_pref.rowcount

        # 3. Matches
        res_m = await db.execute(
            delete(Match).where(
                (Match.member_a_id.in_(all_user_ids)) | (Match.member_b_id.in_(all_user_ids))
            )
        )
        stats["matches"] = res_m.rowcount

        # 4. Habilidades y ofertas
        res_learn = await db.execute(
            delete(UserLearningSkill).where(UserLearningSkill.user_id.in_(all_user_ids))
        )
        stats["user_learning_skills"] = res_learn.rowcount

        res_teach = await db.execute(
            delete(TeachingSkill).where(TeachingSkill.user_id.in_(all_user_ids))
        )
        stats["teaching_skills"] = res_teach.rowcount

        # 5. Billeteras y usuarios
        res_w = await db.execute(delete(Wallet).where(Wallet.user_id.in_(all_user_ids)))
        stats["wallets"] = res_w.rowcount

        res_u = await db.execute(delete(User).where(User.id.in_(all_user_ids)))
        stats["users"] = res_u.rowcount

    # 6. Skill y Categoría específicas
    res_sk = await db.execute(
        delete(Skill).where((Skill.id == QA_SKILL_ID) | (Skill.slug == QA_SKILL_SLUG))
    )
    stats["skills"] = res_sk.rowcount

    res_cat = await db.execute(
        delete(Category).where(
            (Category.id == QA_CATEGORY_ID) | (Category.slug == QA_CATEGORY_SLUG)
        )
    )
    stats["categories"] = res_cat.rowcount

    await db.commit()
    return stats


async def seed_qa_data(db) -> dict[str, Any]:
    """Siembra el grafo completo y consistente para pruebas de HU-39."""
    now = datetime.now(UTC)

    # 1. Categoría
    category = Category(
        id=QA_CATEGORY_ID,
        name="Desarrollo Web Frontend (HU-39 QA)",
        slug=QA_CATEGORY_SLUG,
        description="Categoría determinista para pruebas de confirmación y cierre de sesiones.",
        is_active=True,
    )
    db.add(category)
    await db.flush()

    # 2. Habilidad
    skill = Skill(
        id=QA_SKILL_ID,
        category_id=category.id,
        name="React & Zustand Avanzado (HU-39)",
        slug=QA_SKILL_SLUG,
        description="Habilidad determinista para pruebas funcionales de sesiones.",
        is_active=True,
    )
    db.add(skill)
    await db.flush()

    # 3. Usuarios
    carlos = User(
        id=QA_USER_CARLOS_ID,
        email=QA_EMAILS["learner"],
        full_name="Carlos Gómez (Aprendiz)",
        role=UserRole.MEMBER,
        is_active=True,
        provider="google",
        timezone="America/La_Paz",
    )
    ana = User(
        id=QA_USER_ANA_ID,
        email=QA_EMAILS["instructor"],
        full_name="Ana Martínez (Instructora)",
        role=UserRole.MEMBER,
        is_active=True,
        provider="google",
        timezone="America/La_Paz",
    )
    db.add_all([carlos, ana])
    await db.flush()

    # 4. Billeteras y Preferencias
    wallet_carlos = Wallet(user_id=carlos.id, balance=10)
    wallet_ana = Wallet(user_id=ana.id, balance=10)
    pref_carlos = NotificationPreference(
        user_id=carlos.id, in_app=True, email=True, interchanges=True
    )
    pref_ana = NotificationPreference(user_id=ana.id, in_app=True, email=True, interchanges=True)
    db.add_all([wallet_carlos, wallet_ana, pref_carlos, pref_ana])
    await db.flush()

    # 5. Oferta e Interés
    offer = TeachingSkill(
        id=QA_TEACHING_SKILL_ID,
        user_id=ana.id,
        skill_id=skill.id,
        declared_level="ADVANCED",
        years_of_experience=4,
        accepts_points=False,
    )
    interest = UserLearningSkill(
        user_id=carlos.id,
        skill_id=skill.id,
    )
    first_id, second_id = sorted([carlos.id, ana.id])
    match = Match(
        id=QA_MATCH_ID,
        member_a_id=first_id,
        member_b_id=second_id,
        status="confirmed",
    )
    db.add_all([offer, interest, match])
    await db.flush()

    # -------------------------------------------------------------
    # SESIÓN 1: Virtual — Recién finalizada, lista para 1ra confirmación
    # -------------------------------------------------------------
    s1_starts = now - timedelta(hours=2)
    s1_ends = now - timedelta(hours=1)
    session_1 = ExchangeSession(
        id=SESSION_1_ID,
        match_id=match.id,
        teaching_skill_id=offer.id,
        created_by_id=carlos.id,
        instructor_id=ana.id,
        learner_id=carlos.id,
        starts_at=s1_starts,
        ends_at=s1_ends,
        timezone="America/La_Paz",
        modality="VIRTUAL",
        status="ACCEPTED",
        is_free=True,
    )

    # -------------------------------------------------------------
    # SESIÓN 2: Virtual — Carlos ya confirmó 50 min; Ana lista para confirmar y completar
    # -------------------------------------------------------------
    s2_starts = now - timedelta(hours=3)
    s2_ends = now - timedelta(hours=2)
    session_2 = ExchangeSession(
        id=SESSION_2_ID,
        match_id=match.id,
        teaching_skill_id=offer.id,
        created_by_id=carlos.id,
        instructor_id=ana.id,
        learner_id=carlos.id,
        starts_at=s2_starts,
        ends_at=s2_ends,
        timezone="America/La_Paz",
        modality="VIRTUAL",
        status="ACCEPTED",
        is_free=True,
    )
    conf_carlos_s2 = SessionConfirmation(
        session_id=session_2.id,
        user_id=carlos.id,
        actual_minutes=50,
        topics=["Custom Hooks", "Zustand Selectors"],
        modality="VIRTUAL",
        confirmed_at=s2_ends + timedelta(minutes=5),
        request_key=_uuid.uuid4(),
    )

    # -------------------------------------------------------------
    # SESIÓN 3: Presencial — Lista para PIN presencial y confirmación mutua
    # -------------------------------------------------------------
    s3_starts = now - timedelta(minutes=90)
    s3_ends = now - timedelta(minutes=30)
    session_3 = ExchangeSession(
        id=SESSION_3_ID,
        match_id=match.id,
        teaching_skill_id=offer.id,
        created_by_id=carlos.id,
        instructor_id=ana.id,
        learner_id=carlos.id,
        starts_at=s3_starts,
        ends_at=s3_ends,
        timezone="America/La_Paz",
        modality="PRESENCIAL",
        status="ACCEPTED",
        is_free=True,
    )
    pin_secret = settings.SECRET_KEY.get_secret_value()
    pin_carlos = generate_presence_pin(
        session_id=session_3.id,
        user_id=carlos.id,
        secret=pin_secret,
    )
    pin_ana = generate_presence_pin(
        session_id=session_3.id,
        user_id=ana.id,
        secret=pin_secret,
    )
    pin_record_carlos = SessionPresencePin(
        session_id=session_3.id,
        user_id=carlos.id,
        pin_hash=hash_presence_pin(
            pin_carlos,
            session_id=session_3.id,
            user_id=carlos.id,
            secret=pin_secret,
        ),
        attempt_count=0,
        expires_at=s3_ends + timedelta(hours=24),
    )
    pin_record_ana = SessionPresencePin(
        session_id=session_3.id,
        user_id=ana.id,
        pin_hash=hash_presence_pin(
            pin_ana,
            session_id=session_3.id,
            user_id=ana.id,
            secret=pin_secret,
        ),
        attempt_count=0,
        expires_at=s3_ends + timedelta(hours=24),
    )

    # -------------------------------------------------------------
    # SESIÓN 4: Virtual — Elegible para reporte de inasistencia (No-Show)
    # -------------------------------------------------------------
    s4_starts = now - timedelta(hours=4)
    s4_ends = now - timedelta(hours=3)
    session_4 = ExchangeSession(
        id=SESSION_4_ID,
        match_id=match.id,
        teaching_skill_id=offer.id,
        created_by_id=ana.id,
        instructor_id=ana.id,
        learner_id=carlos.id,
        starts_at=s4_starts,
        ends_at=s4_ends,
        timezone="America/La_Paz",
        modality="VIRTUAL",
        status="ACCEPTED",
        is_free=True,
    )

    # -------------------------------------------------------------
    # SESIÓN 5: Virtual — Completada exitosamente (Historial / Tab Completadas)
    # -------------------------------------------------------------
    s5_starts = now - timedelta(days=1, hours=2)
    s5_ends = now - timedelta(days=1, hours=1)
    session_5 = ExchangeSession(
        id=SESSION_5_ID,
        match_id=match.id,
        teaching_skill_id=offer.id,
        created_by_id=carlos.id,
        instructor_id=ana.id,
        learner_id=carlos.id,
        starts_at=s5_starts,
        ends_at=s5_ends,
        timezone="America/La_Paz",
        modality="VIRTUAL",
        status="COMPLETED",
        is_free=True,
        actual_minutes=60,
        completed_at=s5_ends + timedelta(minutes=10),
    )
    conf_carlos_s5 = SessionConfirmation(
        session_id=session_5.id,
        user_id=carlos.id,
        actual_minutes=60,
        topics=["Fundamentos de TypeScript"],
        modality="VIRTUAL",
        confirmed_at=s5_ends + timedelta(minutes=5),
        request_key=_uuid.uuid4(),
    )
    conf_ana_s5 = SessionConfirmation(
        session_id=session_5.id,
        user_id=ana.id,
        actual_minutes=60,
        topics=["Fundamentos de TypeScript", "Ejercicios prácticos"],
        modality="VIRTUAL",
        confirmed_at=s5_ends + timedelta(minutes=10),
        request_key=_uuid.uuid4(),
    )

    # -------------------------------------------------------------
    # SESIÓN 6: Virtual — Futura / Programada (no confirmable aún)
    # -------------------------------------------------------------
    s6_starts = now + timedelta(days=1)
    s6_ends = s6_starts + timedelta(minutes=60)
    session_6 = ExchangeSession(
        id=SESSION_6_ID,
        match_id=match.id,
        teaching_skill_id=offer.id,
        created_by_id=carlos.id,
        instructor_id=ana.id,
        learner_id=carlos.id,
        starts_at=s6_starts,
        ends_at=s6_ends,
        timezone="America/La_Paz",
        modality="VIRTUAL",
        status="ACCEPTED",
        is_free=True,
    )

    db.add_all(
        [
            session_1,
            session_2,
            conf_carlos_s2,
            session_3,
            pin_record_carlos,
            pin_record_ana,
            session_4,
            session_5,
            conf_carlos_s5,
            conf_ana_s5,
            session_6,
        ]
    )
    await db.commit()

    # Tokens JWT para pruebas (1 año de vigencia para evitar expiración durante pruebas de QA)
    token_carlos = create_access_token(
        str(carlos.id), UserRole.MEMBER.value, expires_delta=timedelta(days=365)
    )
    token_ana = create_access_token(
        str(ana.id), UserRole.MEMBER.value, expires_delta=timedelta(days=365)
    )

    return {
        "carlos": {
            "id": str(carlos.id),
            "email": carlos.email,
            "full_name": carlos.full_name,
            "token": token_carlos,
            "pin": pin_carlos,
        },
        "ana": {
            "id": str(ana.id),
            "email": ana.email,
            "full_name": ana.full_name,
            "token": token_ana,
            "pin": pin_ana,
        },
        "sessions": {
            "s1_virtual_ready": str(session_1.id),
            "s2_virtual_waiting": str(session_2.id),
            "s3_presencial_pin": str(session_3.id),
            "s4_noshow_eligible": str(session_4.id),
            "s5_completed": str(session_5.id),
            "s6_future": str(session_6.id),
        },
    }


def print_browser_snippet(user_name: str, user_dict: dict[str, Any]):
    storage_obj = {
        "state": {
            "user": {
                "id": user_dict["id"],
                "email": user_dict["email"],
                "fullName": user_dict["full_name"],
                "role": "MEMBER",
                "skillPointsBalance": 10,
                "reputationScore": 5.0,
                "trustLevel": 5,
                "isVerified": True,
            },
            "token": user_dict["token"],
            "refreshToken": None,
            "isAuthenticated": True,
            "isLoading": False,
        },
        "version": 0,
    }
    js_code = (
        f"localStorage.setItem('skillmatch-auth-storage', JSON.stringify({json.dumps(storage_obj)})); "
        "window.location.href = '/app/sessions';"
    )
    print(f"\n👉 [CONSOLA DEL NAVEGADOR] Iniciar sesión como {user_name}:")
    print(js_code)


async def main():
    assert_not_production()

    parser = argparse.ArgumentParser(
        description="Semilla determinista para pruebas de QA y UI de HU-39"
    )
    parser.add_argument(
        "--cleanup", action="store_true", help="Limpia exclusivamente los datos de prueba de HU-39."
    )
    args = parser.parse_args()

    async with AsyncSessionLocal() as session:
        if args.cleanup:
            print("[INFO] Ejecutando limpieza quirúrgica de datos de prueba HU-39...")
            stats = await cleanup_qa_data(session)
            print("[OK] Limpieza finalizada:")
            for k, v in stats.items():
                if v:
                    print(f"  - {k}: {v} eliminados")
            return

        print("[INFO] Limpiando ejecuciones previas de HU-39...")
        await cleanup_qa_data(session)

        print("[INFO] Sembrando escenario determinista para HU-39...")
        data = await seed_qa_data(session)

        print("\n" + "=" * 70)
        print("✅ ESCENARIO SEMBRADO EXITOSAMENTE PARA HU-39 (CONFIRMACIÓN Y CIERRE)")
        print("=" * 70)
        print(
            f"👤 Carlos (Aprendiz):   {data['carlos']['email']} (PIN Presencial: {data['carlos']['pin']})"
        )
        print(
            f"👤 Ana (Instructora):  {data['ana']['email']} (PIN Presencial: {data['ana']['pin']})"
        )
        print("\n📅 Sesiones creadas:")
        print(
            f"  1. [VIRTUAL]    Lista para 1ra confirmación:       {data['sessions']['s1_virtual_ready']}"
        )
        print(
            f"  2. [VIRTUAL]    Carlos confirmó 50m (Ana pendiente): {data['sessions']['s2_virtual_waiting']}"
        )
        print(
            f"  3. [PRESENCIAL] Con PINs (Carlos: 4829, Ana: 9153):  {data['sessions']['s3_presencial_pin']}"
        )
        print(
            f"  4. [VIRTUAL]    Elegible para Reporte No-Show:     {data['sessions']['s4_noshow_eligible']}"
        )
        print(
            f"  5. [VIRTUAL]    Completada con éxito (60 min):     {data['sessions']['s5_completed']}"
        )
        print(
            f"  6. [VIRTUAL]    Futura / Programada:               {data['sessions']['s6_future']}"
        )

        print("\n" + "=" * 70)
        print(
            "📋 CÓDIGOS PARA LA CONSOLA DEL NAVEGADOR (DevTools -> Console en http://localhost:5173)"
        )
        print("=" * 70)
        print_browser_snippet("Carlos Aprendiz", data["carlos"])
        print_browser_snippet("Ana Instructora", data["ana"])
        print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
