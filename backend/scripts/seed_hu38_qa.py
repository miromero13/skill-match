"""HU-38: Script de Carga de Datos y Limpieza Controlada para Desarrollo y QA.

Propósito:
- Cargar un escenario reproducible y consistente para probar la HU-38 (agendamiento de sesiones).
- Permite la prueba automatizada y la prueba visual en el frontend sin necesidad de Google OAuth.
- No utiliza migraciones Alembic de prueba ni contamina la base de datos de producción.
- Incluye bandera `--cleanup` para eliminar quirúrgicamente los datos generados sin truncar tablas ni afectar otros usuarios.
"""

import argparse
import asyncio
import json
import sys
import uuid as _uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select

# Asegurar path de importación
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.catalog import Category, Skill
from app.models.exchange_session import (
    BookingRestriction,
    ExchangeSession,
    SessionAuditEvent,
    SessionCancellation,
    SessionQuotaMovement,
    SessionReminderDispatch,
    WeeklySessionQuota,
)
from app.models.match import Match
from app.models.notification import Notification
from app.models.notification_preference import NotificationPreference
from app.models.teaching_skill import TeachingSkill
from app.models.user import ExchangeModality, User, UserRole
from app.models.user_availability import UserAvailability
from app.models.user_block import UserBlock
from app.models.user_learning_skill import UserLearningSkill
from app.models.wallet import Wallet
from app.services.exchange_session_policy import local_week_bounds

QA_EMAILS = {
    "learner": "learner-hu38-qa@skillmatch.io",
    "instructor": "instructor-hu38-qa@skillmatch.io",
    "outsider": "outsider-hu38-qa@skillmatch.io",
}

QA_CATEGORY_SLUG = "cat-hu38-qa-deterministic"
QA_SKILL_SLUG = "skill-hu38-qa-deterministic"

# IDs deterministas para estabilidad absoluta en pruebas manuales y Frontend

QA_USER_A_ID = _uuid.UUID("11111111-1111-4111-8111-111111111111")  # Learner
QA_USER_B_ID = _uuid.UUID("22222222-2222-4222-8222-222222222222")  # Instructor
QA_USER_C_ID = _uuid.UUID("33333333-3333-4333-8333-333333333333")  # Outsider
QA_CATEGORY_ID = _uuid.UUID("44444444-4444-4444-8444-444444444444")
QA_SKILL_ID = _uuid.UUID("55555555-5555-4555-8555-555555555555")
QA_TEACHING_SKILL_ID = _uuid.UUID("66666666-6666-4666-8666-666666666666")
QA_MATCH_ID = _uuid.UUID("77777777-7777-4777-8777-777777777777")


def assert_not_production():
    """Valida que el script no se ejecute en entorno productivo."""
    env = (getattr(settings, "ENVIRONMENT", "") or "").strip().lower()
    if env in ("production", "prod"):
        print("\n[ERROR CRÍTICO] seed_hu38_qa.py no puede ejecutarse en un entorno de PRODUCCIÓN.")
        sys.exit(1)


async def cleanup_qa_data(db) -> dict[str, int]:
    """Elimina de manera quirúrgica exclusivamente las entidades asociadas a los identificadores QA de HU-38."""
    stats = {}

    # 1. Obtener usuarios QA por email o ID determinista. Los tokens revocados
    # no tienen relación con un usuario, por lo que no se eliminan: hacerlo
    # afectaría credenciales ajenas al escenario HU-38.
    users = (
        await db.scalars(
            select(User).where(
                (User.email.in_(list(QA_EMAILS.values())))
                | (User.id.in_([QA_USER_A_ID, QA_USER_B_ID, QA_USER_C_ID]))
            )
        )
    ).all()
    user_ids = list(set([u.id for u in users] + [QA_USER_A_ID, QA_USER_B_ID, QA_USER_C_ID]))

    if user_ids:
        # Obtener sesiones asociadas
        sessions = (
            await db.scalars(
                select(ExchangeSession).where(
                    (ExchangeSession.instructor_id.in_(user_ids))
                    | (ExchangeSession.learner_id.in_(user_ids))
                )
            )
        ).all()
        session_ids = [s.id for s in sessions]

        if session_ids:
            res_disp = await db.execute(
                delete(SessionReminderDispatch).where(SessionReminderDispatch.session_id.in_(session_ids))
            )
            stats["session_reminder_dispatches"] = res_disp.rowcount
            res_canc = await db.execute(
                delete(SessionCancellation).where(SessionCancellation.session_id.in_(session_ids))
            )
            stats["session_cancellations"] = res_canc.rowcount
            res_audit = await db.execute(
                delete(SessionAuditEvent).where(SessionAuditEvent.session_id.in_(session_ids))
            )
            stats["session_audit_events"] = res_audit.rowcount
            res_quota = await db.execute(
                delete(SessionQuotaMovement).where(SessionQuotaMovement.session_id.in_(session_ids))
            )
            stats["session_quota_movements"] = res_quota.rowcount
            res_sess = await db.execute(
                delete(ExchangeSession).where(ExchangeSession.id.in_(session_ids))
            )
            stats["exchange_sessions"] = res_sess.rowcount

        res_rest = await db.execute(
            delete(BookingRestriction).where(BookingRestriction.user_id.in_(user_ids))
        )
        stats["booking_restrictions"] = res_rest.rowcount

        res_notif = await db.execute(
            delete(Notification).where(Notification.user_id.in_(user_ids))
        )
        stats["notifications"] = res_notif.rowcount

        res_pref = await db.execute(
            delete(NotificationPreference).where(NotificationPreference.user_id.in_(user_ids))
        )
        stats["notification_preferences"] = res_pref.rowcount

        res_block = await db.execute(
            delete(UserBlock).where(
                (UserBlock.blocker_id.in_(user_ids)) | (UserBlock.blocked_id.in_(user_ids))
            )
        )
        stats["user_blocks"] = res_block.rowcount

        res_match = await db.execute(
            delete(Match).where(
                (Match.member_a_id.in_(user_ids)) | (Match.member_b_id.in_(user_ids))
            )
        )
        stats["matches"] = res_match.rowcount

        res_teach = await db.execute(
            delete(TeachingSkill).where(TeachingSkill.user_id.in_(user_ids))
        )
        stats["teaching_skills"] = res_teach.rowcount

        res_learn = await db.execute(
            delete(UserLearningSkill).where(UserLearningSkill.user_id.in_(user_ids))
        )
        stats["user_learning_skills"] = res_learn.rowcount

        res_avail = await db.execute(
            delete(UserAvailability).where(UserAvailability.user_id.in_(user_ids))
        )
        stats["user_availabilities"] = res_avail.rowcount

        res_wall = await db.execute(
            delete(Wallet).where(Wallet.user_id.in_(user_ids))
        )
        stats["wallets"] = res_wall.rowcount

        res_users = await db.execute(
            delete(User).where(User.id.in_(user_ids))
        )
        stats["users"] = res_users.rowcount

    # Eliminar habilidad y categoría QA
    qa_skill = await db.scalar(select(Skill).where(Skill.slug == QA_SKILL_SLUG))
    if qa_skill:
        await db.execute(delete(TeachingSkill).where(TeachingSkill.skill_id == qa_skill.id))
        await db.execute(delete(UserLearningSkill).where(UserLearningSkill.skill_id == qa_skill.id))
        res_sk = await db.execute(delete(Skill).where(Skill.id == qa_skill.id))
        stats["skills"] = res_sk.rowcount

    qa_cat = await db.scalar(select(Category).where(Category.slug == QA_CATEGORY_SLUG))
    if qa_cat:
        res_cat = await db.execute(delete(Category).where(Category.id == qa_cat.id))
        stats["categories"] = res_cat.rowcount

    await db.commit()
    return stats


async def seed_qa_data(db) -> dict[str, Any]:
    """Inserta el escenario reproducible de QA HU-38 en la base de datos."""
    # 1. Asegurar limpieza previa
    await cleanup_qa_data(db)

    # 2. Categoría y Habilidad
    category = Category(
        id=QA_CATEGORY_ID,
        name="Desarrollo & QA HU-38",
        slug=QA_CATEGORY_SLUG,
        description="Categoría para pruebas QA HU-38",
        is_active=True,
    )
    db.add(category)
    await db.flush()

    skill = Skill(
        id=QA_SKILL_ID,
        name="Testing y Agendamiento HU-38",
        slug=QA_SKILL_SLUG,
        category_id=category.id,
        description="Habilidad canónica para verificación de agendamiento y ciclos de vida HU-38.",
        is_active=True,
    )
    db.add(skill)
    await db.flush()

    # 3. Usuarios A (Learner), B (Instructor), C (Outsider)
    learner = User(
        id=QA_USER_A_ID,
        email=QA_EMAILS["learner"],
        full_name="Usuario A (Learner QA HU-38)",
        role=UserRole.MEMBER,
        timezone="America/La_Paz",
        exchange_modality=ExchangeModality.BOTH,
        provider="google",
        provider_user_id="google-qa-learner-001",
        avatar_url="https://api.dicebear.com/7.x/bottts/svg?seed=LearnerHU38",
        is_active=True,
    )
    instructor = User(
        id=QA_USER_B_ID,
        email=QA_EMAILS["instructor"],
        full_name="Usuario B (Instructor QA HU-38)",
        role=UserRole.MEMBER,
        timezone="America/La_Paz",
        exchange_modality=ExchangeModality.BOTH,
        provider="google",
        provider_user_id="google-qa-instructor-002",
        avatar_url="https://api.dicebear.com/7.x/bottts/svg?seed=InstructorHU38",
        is_active=True,
    )
    outsider = User(
        id=QA_USER_C_ID,
        email=QA_EMAILS["outsider"],
        full_name="Usuario C (Tercero QA HU-38)",
        role=UserRole.MEMBER,
        timezone="America/La_Paz",
        exchange_modality=ExchangeModality.BOTH,
        provider="google",
        provider_user_id="google-qa-outsider-003",
        avatar_url="https://api.dicebear.com/7.x/bottts/svg?seed=OutsiderHU38",
        is_active=True,
    )
    db.add_all([learner, instructor, outsider])
    await db.flush()

    # 4. Billeteras y Preferencias de Notificaciones
    for u in (learner, instructor, outsider):
        db.add(Wallet(user_id=u.id, balance=200 if u.id == learner.id else 10))
        db.add(
            NotificationPreference(
                user_id=u.id,
                revision=1,
                in_app=True,
                push=True,
                email=True,
                interchanges=True,
                points=True,
                general=True,
            )
        )

    # 5. Habilidad de enseñanza de B y de aprendizaje de A
    teaching_skill = TeachingSkill(
        id=QA_TEACHING_SKILL_ID,
        user_id=instructor.id,
        skill_id=skill.id,
        declared_level="ADVANCED",
        years_of_experience=4,
        accepts_points=True,
        hourly_points_rate=40,
    )
    learning_skill = UserLearningSkill(
        user_id=learner.id,
        skill_id=skill.id,
        current_level=1,
        target_level=3,
    )
    db.add_all([teaching_skill, learning_skill])
    await db.flush()

    # 6. Match confirmado entre A y B
    match = Match(
        id=QA_MATCH_ID,
        member_a_id=QA_USER_A_ID,
        member_b_id=QA_USER_B_ID,
        status="confirmed",
    )
    db.add(match)
    await db.flush()

    # 7. Disponibilidad para A y B (Lunes a Domingo: 09:00 - 13:00 y 15:00 - 20:00)
    availabilities = []
    for day in range(7):
        for user_item in (learner, instructor):
            availabilities.append(
                UserAvailability(
                    user_id=user_item.id,
                    day_of_week=day,
                    start_time="09:00",
                    end_time="13:00",
                    modality="BOTH",
                    is_enabled=True,
                )
            )
            availabilities.append(
                UserAvailability(
                    user_id=user_item.id,
                    day_of_week=day,
                    start_time="15:00",
                    end_time="20:00",
                    modality="BOTH",
                    is_enabled=True,
                )
            )
    db.add_all(availabilities)

    # Agotar cupos en las semanas visibles del horizonte para mostrar y probar
    # inmediatamente el flujo pagado HU-42 desde session-options.
    for days_ahead in (0, 7, 14):
        reference = datetime.now(UTC) + timedelta(days=days_ahead)
        week_start = (
            local_week_bounds(reference, learner.timezone)[0]
            .astimezone(ZoneInfo(learner.timezone))
            .date()
        )
        db.add(
            WeeklySessionQuota(
                user_id=learner.id,
                week_start=week_start,
                used=2,
                version=1,
            )
        )

    # 8. Sesiones demostrativas para interacción visual inmediata en Frontend
    now_utc = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)

    # 8.1 Sesión PENDIENTE (propuesta por Usuario A, para que Usuario B pueda Aceptar/Rechazar/Reprogramar)
    pending_starts = now_utc + timedelta(days=2, hours=15)
    session_pending = ExchangeSession(
        id=_uuid.UUID("88888888-8888-4888-8888-888888888888"),
        match_id=match.id,
        teaching_skill_id=teaching_skill.id,
        created_by_id=learner.id,
        instructor_id=instructor.id,
        learner_id=learner.id,
        starts_at=pending_starts,
        ends_at=pending_starts + timedelta(minutes=60),
        timezone="America/La_Paz",
        modality="VIRTUAL",
        status="PENDING",
        is_free=True,
    )

    # 8.2 Sesión CONFIRMADA (aceptada, lista para probar Exportar a Google Calendar y .ics)
    accepted_starts = now_utc + timedelta(days=4, hours=16)
    session_accepted = ExchangeSession(
        id=_uuid.UUID("99999999-9999-4999-8999-999999999999"),
        match_id=match.id,
        teaching_skill_id=teaching_skill.id,
        created_by_id=learner.id,
        instructor_id=instructor.id,
        learner_id=learner.id,
        starts_at=accepted_starts,
        ends_at=accepted_starts + timedelta(minutes=60),
        timezone="America/La_Paz",
        modality="PRESENCIAL",
        status="ACCEPTED",
        is_free=True,
    )

    # 8.3 Sesión CANCELADA (para visualizar el historial de cancelaciones y motivos)
    cancelled_starts = now_utc + timedelta(days=6, hours=17)
    session_cancelled = ExchangeSession(
        id=_uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        match_id=match.id,
        teaching_skill_id=teaching_skill.id,
        created_by_id=learner.id,
        instructor_id=instructor.id,
        learner_id=learner.id,
        starts_at=cancelled_starts,
        ends_at=cancelled_starts + timedelta(minutes=60),
        timezone="America/La_Paz",
        modality="VIRTUAL",
        status="CANCELLED",
        is_free=True,
        cancellation_reason="Cancelación justificada con más de 24 horas de anticipación",
        cancelled_by_id=learner.id,
        cancelled_at=datetime.now(UTC),
        quota_restored=True,
    )

    db.add_all([session_pending, session_accepted, session_cancelled])
    await db.commit()

    # 9. Generar tokens JWT para pruebas locales (duración de 365 días para evitar expiración en QA)
    token_a = create_access_token(str(learner.id), UserRole.MEMBER.value, expires_delta=timedelta(days=365))
    token_b = create_access_token(str(instructor.id), UserRole.MEMBER.value, expires_delta=timedelta(days=365))
    token_c = create_access_token(str(outsider.id), UserRole.MEMBER.value, expires_delta=timedelta(days=365))

    return {
        "learner": {
            "id": str(learner.id),
            "email": learner.email,
            "full_name": learner.full_name,
            "token": token_a,
        },
        "instructor": {
            "id": str(instructor.id),
            "email": instructor.email,
            "full_name": instructor.full_name,
            "token": token_b,
        },
        "outsider": {
            "id": str(outsider.id),
            "email": outsider.email,
            "full_name": outsider.full_name,
            "token": token_c,
        },
        "match_id": str(match.id),
        "skill_id": str(skill.id),
        "teaching_skill_id": str(teaching_skill.id),
        "category_id": str(category.id),
    }


def print_browser_snippet(user_name: str, user_dict: dict[str, str]):
    storage_obj = {
        "state": {
            "user": {
                "id": user_dict["id"],
                "email": user_dict["email"],
                "fullName": user_dict["full_name"],
                "role": "MEMBER",
                "skillPointsBalance": 200 if user_name.startswith("Usuario A") else 10,
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
        f"localStorage.setItem('skillmatch-auth-storage', JSON.stringify({json.dumps(storage_obj)}));\n"
        "window.location.href = '/app/sessions';"
    )
    print(f"\n--- Snippet para iniciar sesión como {user_name} en Frontend (pegar en DevTools Console) ---")
    print(js_code)


async def main():
    assert_not_production()

    parser = argparse.ArgumentParser(description="Seed y Limpieza de datos QA para HU-38")
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Limpia exclusivamente los datos de prueba de HU-38 sin re-sembrar.",
    )
    args = parser.parse_args()

    async with AsyncSessionLocal() as session:
        if args.cleanup:
            print("[INFO] Ejecutando limpieza quirúrgica de datos de prueba HU-38...")
            stats = await cleanup_qa_data(session)
            print("[OK] Limpieza finalizada exitosamente:")
            for k, v in stats.items():
                if v:
                    print(f"  - {k}: {v} registros eliminados")
            if not any(stats.values()):
                print("  (No había registros de QA pendientes de eliminar)")
            return

        print("[INFO] Sembrando escenario de datos deterministas para HU-38...")
        data = await seed_qa_data(session)
        print("[OK] Datos sembrados con éxito en PostgreSQL:")
        print(f"  - Match ID: {data['match_id']}")
        print(f"  - Teaching Skill ID: {data['teaching_skill_id']}")
        print(f"  - Usuario A (Learner):    {data['learner']['id']} ({data['learner']['email']})")
        print(f"  - Usuario B (Instructor): {data['instructor']['id']} ({data['instructor']['email']})")
        print(f"  - Usuario C (Outsider):   {data['outsider']['id']} ({data['outsider']['email']})")

        print_browser_snippet("Usuario A (Learner / Proponente)", data["learner"])
        print_browser_snippet("Usuario B (Instructor / Contraparte)", data["instructor"])

        print("\n--- Ejemplo de consulta rápida vía cURL para opciones de sesión ---")
        print(
            f'curl -X GET "http://127.0.0.1:8000/api/matches/{data["match_id"]}/session-options" \\\n'
            f'  -H "Authorization: Bearer {data["learner"]["token"]}"'
        )

        print("\n--- Ejemplo de aislamiento 404 para tercero (Usuario C) ---")
        print(
            f'curl -i -X GET "http://127.0.0.1:8000/api/matches/{data["match_id"]}/session-options" \\\n'
            f'  -H "Authorization: Bearer {data["outsider"]["token"]}"'
        )


if __name__ == "__main__":
    asyncio.run(main())
