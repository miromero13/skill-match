"""HU-38 — Prueba E2E Transaccional Integral contra PostgreSQL Real.

Cubre los dos niveles solicitados:
1. Preparación de datos transaccionales reales en PostgreSQL:
   - Usuario A (Instructor)
   - Usuario B (Aprendiz)
   - Usuario C (Tercero / Outsider)
   - Match confirmado entre A y B
   - Oferta de habilidad (TeachingSkill) de A e interés (UserLearningSkill) de B
   - Disponibilidad compatible (UserAvailability) para ambos
   - Límite inicial de dos cupos gratuitos
2. Recorrido exhaustivo de las operaciones:
   - Consultar franjas y disponibilidad
   - Crear sesión y verificar reserva de cupo (1 restante)
   - Aceptar propuesta por la contraparte
   - Crear y rechazar otra propuesta verificando restitución de cupo
   - Reprogramar sesión aceptada (vuelve a PENDING)
   - Cancelar oportunamente con motivo justificado (>=24h) y restituir cupo
   - Comprobar aislamiento y ofuscación 404 estricta para el usuario C
   - Agotar los dos cupos semanales gratuitos
   - Reservar el tercer agendamiento pagado mediante escrow HU-42
   - Comprobar restricción por bloqueo bilateral HU-26
   - Provocar una cancelación tardía (<24h)
   - Confirmar la sanción de 7 días (BookingRestriction) que impide agendar sin bloquear la cuenta
   - Verificar emisión durable de notificaciones sin duplicados por reintentos
"""

from collections import Counter
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
import pytest
from sqlalchemy import delete, select

from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.main import create_application
from app.models.catalog import Category, Skill
from app.models.exchange_session import BookingRestriction, ExchangeSession, WeeklySessionQuota
from app.models.match import Match
from app.models.notification import Notification
from app.models.teaching_skill import TeachingSkill
from app.models.user import User, UserRole
from app.models.user_availability import UserAvailability
from app.models.user_block import UserBlock
from app.models.user_learning_skill import UserLearningSkill
from app.models.wallet import Wallet
from app.services.exchange_session_policy import local_week_bounds


def future_start(*, days: int) -> datetime:
    """Return a stable daytime slot inside the all-day QA availability."""
    return (datetime.now(UTC) + timedelta(days=days)).replace(
        hour=12, minute=0, second=0, microsecond=0
    )


def auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(str(user.id), UserRole.MEMBER.value)
    return {"Authorization": f"Bearer {token}"}


def check_envelope(response: httpx.Response, expected_status: int) -> dict:
    assert response.status_code == expected_status, (
        f"Status esperado {expected_status}, recibido {response.status_code}: {response.text}"
    )
    payload = response.json()
    assert payload["statuscode"] == expected_status
    assert isinstance(payload["message"], str) and payload["message"].strip()
    assert "data" in payload
    assert "error" not in payload
    return payload


async def free_sessions_for(user: User, starts_at: datetime) -> int:
    week_start = local_week_bounds(starts_at, user.timezone)[0].astimezone(
        ZoneInfo(user.timezone)
    ).date()
    async with AsyncSessionLocal() as db:
        quota = await db.scalar(
            select(WeeklySessionQuota).where(
                WeeklySessionQuota.user_id == user.id,
                WeeklySessionQuota.week_start == week_start,
            )
        )
        return 2 - (quota.used if quota else 0)


@asynccontextmanager
async def seeded_qa_context():
    """Genera y aísla usuarios y catálogo en PostgreSQL real, con limpieza garantizada."""
    suffix = uuid4().hex[:12]
    async with AsyncSessionLocal() as db:
        category = Category(
            name=f"Cat-QA-{suffix}",
            slug=f"cat-qa-{suffix}",
            description="Categoría para QA HU-38",
        )
        user_a = User(
            email=f"instructor-{suffix}@qa.invalid",
            full_name=f"Instructor QA {suffix}",
            role=UserRole.MEMBER,
            timezone="America/La_Paz",
        )
        user_b = User(
            email=f"learner-{suffix}@qa.invalid",
            full_name=f"Learner QA {suffix}",
            role=UserRole.MEMBER,
            timezone="America/La_Paz",
        )
        user_c = User(
            email=f"outsider-{suffix}@qa.invalid",
            full_name=f"Outsider QA {suffix}",
            role=UserRole.MEMBER,
            timezone="America/La_Paz",
        )
        db.add_all([category, user_a, user_b, user_c])
        await db.flush()

        skill = Skill(
            name=f"Skill QA {suffix}",
            slug=f"skill-qa-{suffix}",
            category_id=category.id,
            is_active=True,
        )
        db.add(skill)
        await db.flush()

        teaching_offer = TeachingSkill(
            user_id=user_a.id,
            skill_id=skill.id,
            declared_level="ADVANCED",
            years_of_experience=4,
            accepts_points=True,
            hourly_points_rate=40,
        )
        learning_interest = UserLearningSkill(
            user_id=user_b.id,
            skill_id=skill.id,
        )

        member_first, member_second = sorted([user_a.id, user_b.id])
        match = Match(
            member_a_id=member_first,
            member_b_id=member_second,
            status="confirmed",
        )

        # Disponibilidad compatible para ambos (toda la semana 00:00 - 23:30)
        availability_slots = [
            UserAvailability(
                user_id=u.id,
                day_of_week=d,
                start_time="00:00",
                end_time="23:30",
                is_enabled=True,
                modality="BOTH",
            )
            for u in (user_a, user_b)
            for d in range(7)
        ]

        db.add_all([
            teaching_offer,
            learning_interest,
            match,
            Wallet(user_id=user_b.id, balance=200),
            Wallet(user_id=user_a.id, balance=0),
            *availability_slots,
        ])
        await db.commit()

        for item in (category, skill, teaching_offer, user_a, user_b, user_c, match):
            await db.refresh(item)

        ctx = {
            "category": category,
            "skill": skill,
            "offer": teaching_offer,
            "instructor": user_a,
            "learner": user_b,
            "outsider": user_c,
            "match": match,
        }

    try:
        yield ctx
    finally:
        async with AsyncSessionLocal() as cleanup:
            # Elimina en cascada
            await cleanup.execute(delete(Match).where(Match.id == match.id))
            await cleanup.execute(
                delete(User).where(User.id.in_([user_a.id, user_b.id, user_c.id]))
            )
            await cleanup.execute(delete(Skill).where(Skill.id == skill.id))
            await cleanup.execute(delete(Category).where(Category.id == category.id))
            await cleanup.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_hu38_full_e2e_qa_lifecycle():
    """Ejecuta el ciclo de vida completo de QA para HU-38."""
    async with seeded_qa_context() as ctx:
        app = create_application()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            instructor = ctx["instructor"]
            learner = ctx["learner"]
            outsider = ctx["outsider"]
            match = ctx["match"]
            offer = ctx["offer"]

            # ------------------------------------------------------------------
            # 1. Consultar franjas y disponibilidad
            # ------------------------------------------------------------------
            resp_avail_a = check_envelope(
                await client.get("/api/users/me/availability", headers=auth_headers(instructor)),
                200,
            )
            assert len(resp_avail_a["data"]) == 7, "Instructor debe tener 7 franjas configuradas"

            resp_avail_b = check_envelope(
                await client.get("/api/users/me/availability", headers=auth_headers(learner)),
                200,
            )
            assert len(resp_avail_b["data"]) == 7, "Learner debe tener 7 franjas configuradas"

            session_options = check_envelope(
                await client.get(
                    f"/api/matches/{match.id}/session-options",
                    headers=auth_headers(learner),
                ),
                200,
            )["data"]
            assert session_options["match_id"] == str(match.id)
            assert len(session_options["directions"]) == 1
            assert session_options["directions"][0]["common_slots"]

            # Comprobar cupo inicial del aprendiz: 2 cupos libres
            init_list = check_envelope(
                await client.get("/api/sessions", headers=auth_headers(learner)),
                200,
            )
            assert init_list["data"]["free_sessions_left"] == 2
            assert init_list["count"] == 0

            # ------------------------------------------------------------------
            # 2. Crear sesión (Propuesta 1)
            # ------------------------------------------------------------------
            start_p1 = future_start(days=4)
            payload_p1 = {
                "match_id": str(match.id),
                "teaching_skill_id": str(offer.id),
                "instructor_id": str(instructor.id),
                "starts_at": start_p1.isoformat(),
                "ends_at": (start_p1 + timedelta(minutes=60)).isoformat(),
                "timezone": learner.timezone,
                "modality": "VIRTUAL",
            }

            p1_created = check_envelope(
                await client.post("/api/sessions", headers=auth_headers(learner), json=payload_p1),
                201,
            )["data"]
            assert p1_created["status"] == "PENDING"
            assert p1_created["is_free"] is True
            session1_id = p1_created["id"]

            # Verificar que consumió 1 cupo
            list_after_p1 = check_envelope(
                await client.get("/api/sessions", headers=auth_headers(learner)),
                200,
            )
            assert await free_sessions_for(learner, start_p1) == 1
            assert list_after_p1["count"] == 1

            # ------------------------------------------------------------------
            # 3. Aceptar Propuesta 1 (solo la contraparte: Instructor)
            # ------------------------------------------------------------------
            # El proponente (learner) no puede aceptarse a sí mismo
            self_accept = check_envelope(
                await client.patch(
                    f"/api/sessions/{session1_id}/status",
                    headers=auth_headers(learner),
                    json={"status": "ACCEPTED"},
                ),
                409,
            )
            assert "contraparte" in self_accept["message"].lower()

            p1_accepted = check_envelope(
                await client.patch(
                    f"/api/sessions/{session1_id}/status",
                    headers=auth_headers(instructor),
                    json={"status": "ACCEPTED"},
                ),
                200,
            )["data"]
            assert p1_accepted["status"] == "ACCEPTED"

            # ------------------------------------------------------------------
            # 4. Crear y Rechazar otra propuesta (Propuesta 2)
            # ------------------------------------------------------------------
            start_p2 = start_p1 + timedelta(hours=2)
            payload_p2 = {
                "match_id": str(match.id),
                "teaching_skill_id": str(offer.id),
                "instructor_id": str(instructor.id),
                "starts_at": start_p2.isoformat(),
                "ends_at": (start_p2 + timedelta(minutes=60)).isoformat(),
                "timezone": learner.timezone,
                "modality": "VIRTUAL",
            }
            p2_created = check_envelope(
                await client.post("/api/sessions", headers=auth_headers(learner), json=payload_p2),
                201,
            )["data"]
            session2_id = p2_created["id"]

            # Contraparte rechaza
            p2_rejected = check_envelope(
                await client.patch(
                    f"/api/sessions/{session2_id}/status",
                    headers=auth_headers(instructor),
                    json={"status": "REJECTED"},
                ),
                200,
            )["data"]
            assert p2_rejected["status"] == "REJECTED"

            # Al rechazar, el cupo de P2 se restituye: free_sessions_left sigue en 1 (por P1)
            check_envelope(
                await client.get("/api/sessions", headers=auth_headers(learner)),
                200,
            )
            assert await free_sessions_for(learner, start_p1) == 1

            # ------------------------------------------------------------------
            # 5. Reprogramar Sesión 1
            # ------------------------------------------------------------------
            reschedule_start = start_p1 + timedelta(days=1, hours=1)
            p1_rescheduled = check_envelope(
                await client.put(
                    f"/api/sessions/{session1_id}/reschedule",
                    headers=auth_headers(learner),
                    json={
                        "starts_at": reschedule_start.isoformat(),
                        "ends_at": (reschedule_start + timedelta(minutes=60)).isoformat(),
                    },
                ),
                200,
            )["data"]
            # Regla ratificada: al reprogramar fecha/hora, vuelve a PENDING
            assert p1_rescheduled["status"] == "PENDING"

            # ------------------------------------------------------------------
            # 6. Cancelar con motivo justificado (Oportuna >= 24h)
            # ------------------------------------------------------------------
            # Rechazar motivos vacíos o < 10 caracteres
            check_envelope(
                await client.post(
                    f"/api/sessions/{session1_id}/cancel",
                    headers=auth_headers(learner),
                    json={"cancellation_reason": "corto"},
                ),
                422,
            )

            p1_cancelled = check_envelope(
                await client.post(
                    f"/api/sessions/{session1_id}/cancel",
                    headers=auth_headers(learner),
                    json={"cancellation_reason": "Imprevisto médico debidamente justificado"},
                ),
                200,
            )["data"]
            assert p1_cancelled["status"] == "CANCELLED"
            assert p1_cancelled["quota_restored"] is True
            assert p1_cancelled["booking_blocked_until"] is None

            # Cupo de P1 restituido: volvemos a tener 2 cupos disponibles
            check_envelope(
                await client.get("/api/sessions", headers=auth_headers(learner)),
                200,
            )
            assert await free_sessions_for(learner, start_p1) == 2

            # ------------------------------------------------------------------
            # 7. Comprobar aislamiento y ofuscación 404 para el usuario C (Outsider)
            # ------------------------------------------------------------------
            # C no puede consultar la sesión ajena
            c_list = check_envelope(
                await client.get("/api/sessions", headers=auth_headers(outsider)),
                200,
            )
            assert c_list["count"] == 0
            assert len(c_list["data"]["items"]) == 0

            # C recibe 404 estricto al intentar mutar recursos de A y B
            check_envelope(
                await client.patch(
                    f"/api/sessions/{session1_id}/status",
                    headers=auth_headers(outsider),
                    json={"status": "ACCEPTED"},
                ),
                404,
            )
            c_reschedule_start = future_start(days=5)
            check_envelope(
                await client.put(
                    f"/api/sessions/{session1_id}/reschedule",
                    headers=auth_headers(outsider),
                    json={
                        "starts_at": c_reschedule_start.isoformat(),
                        "ends_at": (c_reschedule_start + timedelta(minutes=60)).isoformat(),
                    },
                ),
                404,
            )
            check_envelope(
                await client.post(
                    f"/api/sessions/{session1_id}/cancel",
                    headers=auth_headers(outsider),
                    json={"cancellation_reason": "Intento no autorizado de cancelacion"},
                ),
                404,
            )
            # C tampoco puede crear sesiones sobre el match ajeno
            check_envelope(
                await client.post(
                    "/api/sessions",
                    headers=auth_headers(outsider),
                    json=payload_p1,
                ),
                404,
            )

            # ------------------------------------------------------------------
            # 8. Agotar dos cupos gratuitos
            # ------------------------------------------------------------------
            base_week = future_start(days=3)
            # Sesión 1 de la cuota
            slot1_start = base_week
            check_envelope(
                await client.post(
                    "/api/sessions",
                    headers=auth_headers(learner),
                    json={
                        "match_id": str(match.id),
                        "teaching_skill_id": str(offer.id),
                        "instructor_id": str(instructor.id),
                        "starts_at": slot1_start.isoformat(),
                        "ends_at": (slot1_start + timedelta(minutes=60)).isoformat(),
                        "timezone": learner.timezone,
                        "modality": "VIRTUAL",
                    },
                ),
                201,
            )
            # Sesión 2 de la cuota (mismo aprendiz, misma semana)
            slot2_start = slot1_start + timedelta(hours=2)
            check_envelope(
                await client.post(
                    "/api/sessions",
                    headers=auth_headers(learner),
                    json={
                        "match_id": str(match.id),
                        "teaching_skill_id": str(offer.id),
                        "instructor_id": str(instructor.id),
                        "starts_at": slot2_start.isoformat(),
                        "ends_at": (slot2_start + timedelta(minutes=60)).isoformat(),
                        "timezone": learner.timezone,
                        "modality": "VIRTUAL",
                    },
                ),
                201,
            )

            # Cupos agotados: free_sessions_left == 0
            check_envelope(
                await client.get("/api/sessions", headers=auth_headers(learner)),
                200,
            )
            assert await free_sessions_for(learner, slot1_start) == 0

            # ------------------------------------------------------------------
            # 9. Reservar el tercer agendamiento con SkillPoints (HU-42)
            # ------------------------------------------------------------------
            slot3_start = slot1_start + timedelta(hours=4)
            slot3_resp = check_envelope(
                await client.post(
                    "/api/sessions",
                    headers=auth_headers(learner),
                    json={
                        "match_id": str(match.id),
                        "teaching_skill_id": str(offer.id),
                        "instructor_id": str(instructor.id),
                        "starts_at": slot3_start.isoformat(),
                        "ends_at": (slot3_start + timedelta(minutes=60)).isoformat(),
                        "timezone": learner.timezone,
                        "modality": "VIRTUAL",
                        "payment_method": "POINTS",
                    },
                ),
                201,
            )
            assert slot3_resp["data"]["is_free"] is False
            assert slot3_resp["data"]["points_required"] == 40
            assert slot3_resp["data"]["payment_state"] == "RESERVED"
            async with AsyncSessionLocal() as paid_db:
                learner_wallet = await paid_db.get(Wallet, learner.id)
                assert learner_wallet is not None
                assert learner_wallet.balance == 160
                assert learner_wallet.escrow_balance == 40

            # ------------------------------------------------------------------
            # 10. Comprobar bloqueo bilateral HU-26
            # ------------------------------------------------------------------
            # Agregamos bloqueo de usuario entre A y B
            async with AsyncSessionLocal() as db_block:
                block_entry = UserBlock(
                    blocker_id=instructor.id,
                    blocked_id=learner.id,
                )
                db_block.add(block_entry)
                await db_block.commit()

            # Intentar agendar en otra semana libre debe ser rechazado por HU-26
            future_week_start = base_week + timedelta(days=14)
            blocked_hu26_resp = check_envelope(
                await client.post(
                    "/api/sessions",
                    headers=auth_headers(learner),
                    json={
                        "match_id": str(match.id),
                        "teaching_skill_id": str(offer.id),
                        "instructor_id": str(instructor.id),
                        "starts_at": future_week_start.isoformat(),
                        "ends_at": (future_week_start + timedelta(minutes=60)).isoformat(),
                        "timezone": learner.timezone,
                        "modality": "VIRTUAL",
                    },
                ),
                409,
            )
            assert "miembro" in blocked_hu26_resp["message"].lower()

            # Levantamos el bloqueo para continuar con las pruebas de cancelación tardía
            async with AsyncSessionLocal() as db_unblock:
                await db_unblock.execute(
                    delete(UserBlock).where(
                        UserBlock.blocker_id == instructor.id,
                        UserBlock.blocked_id == learner.id,
                    )
                )
                await db_unblock.commit()

            # ------------------------------------------------------------------
            # 11. Provocar una cancelación tardía (< 24h)
            # ------------------------------------------------------------------
            # Agendamos en semana futura para tener cupos
            late_session_start = future_week_start + timedelta(hours=20)
            created_for_late = check_envelope(
                await client.post(
                    "/api/sessions",
                    headers=auth_headers(learner),
                    json={
                        "match_id": str(match.id),
                        "teaching_skill_id": str(offer.id),
                        "instructor_id": str(instructor.id),
                        "starts_at": late_session_start.isoformat(),
                        "ends_at": (late_session_start + timedelta(minutes=60)).isoformat(),
                        "timezone": learner.timezone,
                        "modality": "VIRTUAL",
                    },
                ),
                201,
            )["data"]
            late_session_id = created_for_late["id"]

            # Simulamos que la sesión inicia en 2 horas (cancelación tardía sobre la hora)
            async with AsyncSessionLocal() as db_shift:
                shifted_start = datetime.now(UTC) + timedelta(hours=2)
                shifted_end = shifted_start + timedelta(minutes=60)
                await db_shift.execute(
                    ExchangeSession.__table__.update()
                    .where(ExchangeSession.id == late_session_id)
                    .values(starts_at=shifted_start, ends_at=shifted_end)
                )
                await db_shift.commit()

            # El aprendiz cancela faltando 2 horas (< 24h)
            late_cancel_resp = check_envelope(
                await client.post(
                    f"/api/sessions/{late_session_id}/cancel",
                    headers=auth_headers(learner),
                    json={"cancellation_reason": "Emergencia avisada con dos horas de antelacion"},
                ),
                200,
            )["data"]
            assert late_cancel_resp["status"] == "CANCELLED"
            assert late_cancel_resp["quota_restored"] is False
            assert late_cancel_resp["booking_blocked_until"] is not None

            # ------------------------------------------------------------------
            # 12. Confirmar la sanción de siete días
            # ------------------------------------------------------------------
            # Comprobar en PostgreSQL la tabla booking_restrictions
            async with AsyncSessionLocal() as db_check:
                restriction = (
                    await db_check.execute(
                        select(BookingRestriction).where(
                            BookingRestriction.user_id == learner.id,
                            BookingRestriction.ends_at > datetime.now(UTC),
                        )
                    )
                ).scalar_one_or_none()
                assert restriction is not None
                # La sanción debe ser de aproximadamente 7 días
                remaining_penalty = restriction.ends_at - datetime.now(UTC)
                assert remaining_penalty.total_seconds() > 6 * 86400

            # El aprendiz sancionado intenta crear una nueva sesión -> Debe ser rechazado
            penalized_start = future_start(days=20)
            penalized_attempt = check_envelope(
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
            )
            assert "bloqueado" in penalized_attempt["message"].lower() or "agendar" in penalized_attempt["message"].lower()

            # Sin embargo, el aprendiz aún puede consultar sus sesiones (no está bloqueado del sistema)
            penalized_read = check_envelope(
                await client.get("/api/sessions", headers=auth_headers(learner)),
                200,
            )
            assert penalized_read["statuscode"] == 200

            # ------------------------------------------------------------------
            # 13. Verificar emisión de notificaciones sin duplicados
            # ------------------------------------------------------------------
            async with AsyncSessionLocal() as db_before_retry:
                notifications_before_retry = list(
                    await db_before_retry.scalars(
                        select(Notification.type).where(
                            Notification.user_id.in_([instructor.id, learner.id])
                        )
                    )
                )

            # Reintentamos la cancelación resuelta para comprobar idempotencia
            check_envelope(
                await client.post(
                    f"/api/sessions/{late_session_id}/cancel",
                    headers=auth_headers(learner),
                    json={"cancellation_reason": "Emergencia avisada con dos horas de antelacion"},
                ),
                200,
            )

            # Consultamos las notificaciones durables registradas en PostgreSQL
            async with AsyncSessionLocal() as db_notifs:
                notifications = (
                    await db_notifs.scalars(
                        select(Notification.type).where(
                            Notification.user_id.in_([instructor.id, learner.id])
                        )
                    )
                ).all()

            assert Counter(notifications) == Counter(notifications_before_retry)
            notif_types = set(notifications)
            assert "SESSION_PROPOSED" in notif_types
            assert "SESSION_ACCEPTED" in notif_types
            assert "SESSION_RESCHEDULED" in notif_types
            assert "SESSION_CANCELLED" in notif_types
