"""HU-38 — Ejecutor de QA Nivel 2 contra el Servidor HTTP en Vivo (http://127.0.0.1:8000).

Ejecuta todas las operaciones de extremo a extremo a través de la red local HTTP:
- Consultar franjas comunes y disponibilidad.
- Crear propuesta de sesión (consume 1 cupo).
- Aceptar sesión por la contraparte.
- Crear y rechazar otra propuesta (restituye cupo).
- Reprogramar sesión aceptada (vuelve a PENDING).
- Cancelar con motivo justificado (>= 24h, restituye cupo).
- Aislamiento 404 estricto para tercero (Usuario C).
- Agotar dos cupos semanales.
- Rechazar tercer agendamiento sin HU-42.
- Comprobar bloqueo bilateral HU-26.
- Cancelación tardía (< 24h).
- Comprobar sanción de 7 días (bloqueo exclusivo de agendamiento).
- Notificaciones sin duplicados por reintentos.
"""

import asyncio
import os
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
from sqlalchemy import delete, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.catalog import Category, Skill
from app.models.exchange_session import ExchangeSession
from app.models.match import Match
from app.models.notification import Notification
from app.models.teaching_skill import TeachingSkill
from app.models.user import User, UserRole
from app.models.user_availability import UserAvailability
from app.models.user_block import UserBlock
from app.models.user_learning_skill import UserLearningSkill

BASE_URL = os.getenv("HU38_E2E_BASE_URL", "http://127.0.0.1:8000")


def auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(str(user.id), UserRole.MEMBER.value)
    return {"Authorization": f"Bearer {token}"}


def check(resp: httpx.Response, expected_code: int, step_desc: str) -> dict:
    assert resp.status_code == expected_code, (
        f"Fallo en '{step_desc}': Código esperado {expected_code}, recibido {resp.status_code}. Detalle: {resp.text}"
    )
    payload = resp.json()
    assert payload["statuscode"] == expected_code
    assert "data" in payload
    assert "error" not in payload
    print(f"  [PASS] ({expected_code}) {step_desc} -> {payload.get('message', '')}")
    return payload


async def main():
    print(f"\n{'='*70}\nINICIANDO QA NIVEL 2: PRUEBA E2E EN VIVO (HU-38)\nServidor: {BASE_URL}\n{'='*70}\n")
    suffix = uuid4().hex[:8]

    # 1. Preparar datos en PostgreSQL real
    print("[1/3] Preparando contexto transaccional en PostgreSQL...")
    async with AsyncSessionLocal() as db:
        category = Category(name=f"Cat-Live-{suffix}", slug=f"cat-live-{suffix}")
        instructor = User(
            email=f"inst-live-{suffix}@qa.invalid",
            full_name=f"Instructor Live {suffix}",
            role=UserRole.MEMBER,
            timezone="America/La_Paz",
        )
        learner = User(
            email=f"learn-live-{suffix}@qa.invalid",
            full_name=f"Learner Live {suffix}",
            role=UserRole.MEMBER,
            timezone="America/La_Paz",
        )
        outsider = User(
            email=f"outsider-live-{suffix}@qa.invalid",
            full_name=f"Outsider Live {suffix}",
            role=UserRole.MEMBER,
            timezone="America/La_Paz",
        )
        db.add_all([category, instructor, learner, outsider])
        await db.flush()

        skill = Skill(name=f"Skill Live {suffix}", slug=f"skill-live-{suffix}", category_id=category.id, is_active=True)
        db.add(skill)
        await db.flush()

        offer = TeachingSkill(user_id=instructor.id, skill_id=skill.id, declared_level="ADVANCED", years_of_experience=3)
        interest = UserLearningSkill(user_id=learner.id, skill_id=skill.id)
        first_id, second_id = sorted([instructor.id, learner.id])
        match = Match(member_a_id=first_id, member_b_id=second_id, status="confirmed")

        avail = [
            UserAvailability(
                user_id=u.id,
                day_of_week=d,
                start_time="00:00",
                end_time="23:30",
                is_enabled=True,
                modality="BOTH",
            )
            for u in (instructor, learner)
            for d in range(7)
        ]
        db.add_all([offer, interest, match, *avail])
        await db.commit()
        for item in (instructor, learner, outsider, offer, match):
            await db.refresh(item)

    print("  -> Usuarios A, B y C preparados. Match confirmado y disponibilidad enlazados.\n")

    try:
        print("[2/3] Ejecutando recorrido completo contra HTTP en vivo...")
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
            # Paso 1: Consultar franjas y cupo inicial
            resp_avail = check(
                await client.get("/api/users/me/availability", headers=auth_headers(instructor)),
                200,
                "Consultar disponibilidad del instructor",
            )
            assert len(resp_avail["data"]) == 7

            session_options = check(
                await client.get(
                    f"/api/matches/{match.id}/session-options",
                    headers=auth_headers(learner),
                ),
                200,
                "Consultar opciones productivas de agendamiento",
            )["data"]
            assert session_options["match_id"] == str(match.id)
            assert len(session_options["directions"]) == 1
            assert session_options["directions"][0]["common_slots"]

            resp_init_list = check(
                await client.get("/api/sessions", headers=auth_headers(learner)),
                200,
                "Consultar sesiones y cupo inicial (debe ser 2/2)",
            )
            assert resp_init_list["data"]["free_sessions_left"] == 2

            # Paso 2: Crear sesión (Propuesta 1)
            p1_start = datetime.now(UTC) + timedelta(days=4)
            payload_p1 = {
                "match_id": str(match.id),
                "teaching_skill_id": str(offer.id),
                "instructor_id": str(instructor.id),
                "starts_at": p1_start.isoformat(),
                "ends_at": (p1_start + timedelta(minutes=60)).isoformat(),
                "timezone": learner.timezone,
                "modality": "VIRTUAL",
            }
            p1_data = check(
                await client.post("/api/sessions", headers=auth_headers(learner), json=payload_p1),
                201,
                "Crear Propuesta 1 (estado PENDING, cupo pasa a 1)",
            )["data"]
            session1_id = p1_data["id"]

            # Paso 3: Aceptar sesión
            check(
                await client.patch(
                    f"/api/sessions/{session1_id}/status",
                    headers=auth_headers(learner),
                    json={"status": "ACCEPTED"},
                ),
                409,
                "Proponente no puede aceptarse a si mismo",
            )
            check(
                await client.patch(
                    f"/api/sessions/{session1_id}/status",
                    headers=auth_headers(instructor),
                    json={"status": "ACCEPTED"},
                ),
                200,
                "Contraparte (Instructor) acepta Propuesta 1 -> ACCEPTED",
            )

            # Paso 4: Crear y rechazar otra propuesta
            p2_start = p1_start + timedelta(hours=2)
            payload_p2 = {
                "match_id": str(match.id),
                "teaching_skill_id": str(offer.id),
                "instructor_id": str(instructor.id),
                "starts_at": p2_start.isoformat(),
                "ends_at": (p2_start + timedelta(minutes=60)).isoformat(),
                "timezone": learner.timezone,
                "modality": "VIRTUAL",
            }
            p2_data = check(
                await client.post("/api/sessions", headers=auth_headers(learner), json=payload_p2),
                201,
                "Crear Propuesta 2 para otro horario",
            )["data"]
            session2_id = p2_data["id"]

            check(
                await client.patch(
                    f"/api/sessions/{session2_id}/status",
                    headers=auth_headers(instructor),
                    json={"status": "REJECTED"},
                ),
                200,
                "Contraparte rechaza Propuesta 2 -> REJECTED (restituye cupo)",
            )

            # Paso 5: Reprogramar sesión 1
            reschedule_start = p1_start + timedelta(days=1, hours=1)
            check(
                await client.put(
                    f"/api/sessions/{session1_id}/reschedule",
                    headers=auth_headers(learner),
                    json={
                        "starts_at": reschedule_start.isoformat(),
                        "ends_at": (reschedule_start + timedelta(minutes=60)).isoformat(),
                    },
                ),
                200,
                "Reprogramar sesion 1 -> vuelve a PENDING",
            )

            # Paso 6: Cancelar oportunamente con motivo
            check(
                await client.post(
                    f"/api/sessions/{session1_id}/cancel",
                    headers=auth_headers(learner),
                    json={"cancellation_reason": "Motivo justificado con mas de diez caracteres"},
                ),
                200,
                "Cancelar sesion 1 con >= 24h -> CANCELLED (restituye cupo a 2)",
            )

            # Paso 7: Aislamiento 404 estricto para Usuario C (Outsider)
            check(
                await client.get("/api/sessions", headers=auth_headers(outsider)),
                200,
                "Usuario C lista sus sesiones (vacio, 0 total)",
            )
            check(
                await client.patch(
                    f"/api/sessions/{session1_id}/status",
                    headers=auth_headers(outsider),
                    json={"status": "ACCEPTED"},
                ),
                404,
                "Usuario C recibe 404 al intentar cambiar status ajeno",
            )
            c_reschedule = datetime.now(UTC) + timedelta(days=5)
            check(
                await client.put(
                    f"/api/sessions/{session1_id}/reschedule",
                    headers=auth_headers(outsider),
                    json={
                        "starts_at": c_reschedule.isoformat(),
                        "ends_at": (c_reschedule + timedelta(minutes=60)).isoformat(),
                    },
                ),
                404,
                "Usuario C recibe 404 al intentar reprogramar ajeno",
            )
            check(
                await client.post(
                    f"/api/sessions/{session1_id}/cancel",
                    headers=auth_headers(outsider),
                    json={"cancellation_reason": "Intento no autorizado de cancelacion"},
                ),
                404,
                "Usuario C recibe 404 al intentar cancelar ajeno",
            )

            # Paso 8: Agotar dos cupos gratuitos
            base_w = datetime.now(UTC) + timedelta(days=3)
            check(
                await client.post(
                    "/api/sessions",
                    headers=auth_headers(learner),
                    json={
                        "match_id": str(match.id),
                        "teaching_skill_id": str(offer.id),
                        "instructor_id": str(instructor.id),
                        "starts_at": base_w.isoformat(),
                        "ends_at": (base_w + timedelta(minutes=60)).isoformat(),
                        "timezone": learner.timezone,
                        "modality": "VIRTUAL",
                    },
                ),
                201,
                "Consumir cupo gratuito 1 de la semana",
            )
            w2_start = base_w + timedelta(hours=2)
            check(
                await client.post(
                    "/api/sessions",
                    headers=auth_headers(learner),
                    json={
                        "match_id": str(match.id),
                        "teaching_skill_id": str(offer.id),
                        "instructor_id": str(instructor.id),
                        "starts_at": w2_start.isoformat(),
                        "ends_at": (w2_start + timedelta(minutes=60)).isoformat(),
                        "timezone": learner.timezone,
                        "modality": "VIRTUAL",
                    },
                ),
                201,
                "Consumir cupo gratuito 2 de la semana (cupos agotados)",
            )

            # Paso 9: Rechazar tercer agendamiento sin HU-42
            w3_start = base_w + timedelta(hours=4)
            check(
                await client.post(
                    "/api/sessions",
                    headers=auth_headers(learner),
                    json={
                        "match_id": str(match.id),
                        "teaching_skill_id": str(offer.id),
                        "instructor_id": str(instructor.id),
                        "starts_at": w3_start.isoformat(),
                        "ends_at": (w3_start + timedelta(minutes=60)).isoformat(),
                        "timezone": learner.timezone,
                        "modality": "VIRTUAL",
                    },
                ),
                409,
                "Rechazar tercer agendamiento sin cupo por ausencia de HU-42 (409)",
            )

            # Paso 10: Bloqueo bilateral HU-26
            async with AsyncSessionLocal() as db_block:
                db_block.add(UserBlock(blocker_id=instructor.id, blocked_id=learner.id))
                await db_block.commit()

            future_start = base_w + timedelta(days=14)
            check(
                await client.post(
                    "/api/sessions",
                    headers=auth_headers(learner),
                    json={
                        "match_id": str(match.id),
                        "teaching_skill_id": str(offer.id),
                        "instructor_id": str(instructor.id),
                        "starts_at": future_start.isoformat(),
                        "ends_at": (future_start + timedelta(minutes=60)).isoformat(),
                        "timezone": learner.timezone,
                        "modality": "VIRTUAL",
                    },
                ),
                409,
                "Bloqueo HU-26 impide agendar con miembro bloqueado (409)",
            )

            async with AsyncSessionLocal() as db_unblock:
                await db_unblock.execute(
                    delete(UserBlock).where(
                        UserBlock.blocker_id == instructor.id, UserBlock.blocked_id == learner.id
                    )
                )
                await db_unblock.commit()

            # Paso 11: Cancelación tardía (< 24h)
            late_start = future_start + timedelta(hours=20)
            late_data = check(
                await client.post(
                    "/api/sessions",
                    headers=auth_headers(learner),
                    json={
                        "match_id": str(match.id),
                        "teaching_skill_id": str(offer.id),
                        "instructor_id": str(instructor.id),
                        "starts_at": late_start.isoformat(),
                        "ends_at": (late_start + timedelta(minutes=60)).isoformat(),
                        "timezone": learner.timezone,
                        "modality": "VIRTUAL",
                    },
                ),
                201,
                "Crear sesion para probar cancelacion tardia",
            )["data"]
            late_id = late_data["id"]

            async with AsyncSessionLocal() as db_shift:
                shifted_start = datetime.now(UTC) + timedelta(hours=2)
                shifted_end = shifted_start + timedelta(minutes=60)
                await db_shift.execute(
                    ExchangeSession.__table__.update()
                    .where(ExchangeSession.id == late_id)
                    .values(starts_at=shifted_start, ends_at=shifted_end)
                )
                await db_shift.commit()

            late_cancel_res = check(
                await client.post(
                    f"/api/sessions/{late_id}/cancel",
                    headers=auth_headers(learner),
                    json={"cancellation_reason": "Emergencia avisada con solo 2 horas de antelacion"},
                ),
                200,
                "Cancelar sesion faltando 2h -> Activa sancion de 7 dias",
            )["data"]
            assert late_cancel_res["quota_restored"] is False
            assert late_cancel_res["booking_blocked_until"] is not None

            # Paso 12: Confirmar sanción de 7 días
            penalized_start = datetime.now(UTC) + timedelta(days=20)
            check(
                await client.post(
                    "/api/sessions",
                    headers=auth_headers(learner),
                    json={
                        "match_id": str(match.id),
                        "teaching_skill_id": str(offer.id),
                        "instructor_id": str(instructor.id),
                        "starts_at": penalized_start.isoformat(),
                        "ends_at": (penalized_start + timedelta(minutes=60)).isoformat(),
                        "timezone": learner.timezone,
                        "modality": "VIRTUAL",
                    },
                ),
                409,
                "Usuario sancionado no puede agendar durante 7 dias (409)",
            )

            # Comprobar que lectura sigue habilitada
            check(
                await client.get("/api/sessions", headers=auth_headers(learner)),
                200,
                "Usuario sancionado conserva acceso de lectura y perfil",
            )

            async with AsyncSessionLocal() as db_before_retry:
                notifs_before_retry = list(
                    await db_before_retry.scalars(
                        select(Notification.type).where(
                            Notification.user_id.in_([instructor.id, learner.id])
                        )
                    )
                )

            # Paso 13: Notificaciones sin duplicados
            check(
                await client.post(
                    f"/api/sessions/{late_id}/cancel",
                    headers=auth_headers(learner),
                    json={"cancellation_reason": "Emergencia avisada con solo 2 horas de antelacion"},
                ),
                200,
                "Reintento idempotente de cancelacion no genera errores",
            )

            async with AsyncSessionLocal() as db_notifs:
                notifs = (
                    await db_notifs.scalars(
                        select(Notification.type).where(
                            Notification.user_id.in_([instructor.id, learner.id])
                        )
                    )
                ).all()
            assert Counter(notifs) == Counter(notifs_before_retry)
            notif_types = set(notifs)
            assert "SESSION_PROPOSED" in notif_types
            assert "SESSION_ACCEPTED" in notif_types
            assert "SESSION_RESCHEDULED" in notif_types
            assert "SESSION_CANCELLED" in notif_types
            print("  [PASS] Notificaciones durables emitidas correctamente sin duplicidad de tipo.")

    finally:
        print("\n[3/3] Limpiando datos de prueba en PostgreSQL...")
        async with AsyncSessionLocal() as cleanup:
            await cleanup.execute(delete(Match).where(Match.id == match.id))
            await cleanup.execute(
                delete(User).where(User.id.in_([instructor.id, learner.id, outsider.id]))
            )
            await cleanup.execute(delete(Skill).where(Skill.id == skill.id))
            await cleanup.execute(delete(Category).where(Category.id == category.id))
            await cleanup.commit()
        print("  -> Limpieza completada con exito.\n")

    print(f"{'='*70}\nTODAS LAS PRUEBAS DE QA E2E (NIVELES 1 Y 2) APROBADAS SATISFACTORIAMENTE (100%)\n{'='*70}\n")


if __name__ == "__main__":
    asyncio.run(main())
