"""
SkillMatch — Seeder Integral de Datos de Demostración y Producción
==================================================================
Aprovisiona de forma determinista e idempotente:
1. Catálogo canónico con las 3 categorías solicitadas:
   - Programación
   - Música
   - Fútbol
2. Las 3 habilidades principales con sus escaleras de 5 niveles y rúbricas:
   - Dominadas con el balón (Fútbol, VISION_POSE)
   - Tocar flauta (Música, AUDIO_SPECTRAL)
   - Programación en Python (Programación, CODE_AST)
3. Banco de preguntas teóricas (TheoryQuestion) publicadas con opciones y criterios para IA.
4. Usuarios demo (Instructor y Aprendiz) con billeteras y saldo de 100 SkillPoints.
5. Habilidades ofrecidas (TeachingSkill) y deseadas (UserLearningSkill).
6. Match mutuo precalculado (100% afinidad).
7. Sesión de intercambio virtual futura (ACCEPTED) y sesión previa (COMPLETED).
8. Reseña bilateral de intercambio (SessionReview) con 5 estrellas y feedback detallado.
9. Notificaciones activas en bandeja (Notification) de matches, sesiones y puntos.
10. Caso de disputa/queja (Complaint) para probar la moderación en el panel administrativo.
11. Desafíos de programación (Challenge) para niveles 1, 2 y 3 con casos de prueba para el sandbox Docker.
12. Muestras de dataset de laboratorio (DatasetSample) enlazadas a las habilidades.

Uso:
    python scripts/seed_demo_data.py
    python scripts/seed_demo_data.py --cleanup
"""

import argparse
import asyncio
import hashlib
import logging
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Agregar raíz de backend al sys.path
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import delete, select
from app.core.config import settings
from app.core.security import get_password_hash
from app.db.session import AsyncSessionLocal
from app.db.seed import ensure_initial_admin, ensure_initial_catalog, ensure_initial_theory_questions
from app.models.catalog import Category, ChallengeType, Skill, SkillLevel, Rubric
from app.models.complaint import Complaint, ComplaintReason, ComplaintStatus
from app.models.dataset_sample import DatasetSample
from app.models.exchange_session import ExchangeSession
from app.models.match import Match
from app.models.notification import Notification, NotificationType
from app.models.programming import Challenge, ChallengeTestCase
from app.models.session_review import SessionReview
from app.models.teaching_skill import TeachingSkill
from app.models.theory_question import TheoryQuestion
from app.models.user import User, UserRole
from app.models.user_learning_skill import UrgencyLevel, UserLearningSkill
from app.models.wallet import Wallet

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("skillmatch.seed_demo")

# Identificadores fijos para idempotencia y soporte de QA
DEMO_INSTRUCTOR_EMAIL = "carlos.instructor@skillmatch.com"
DEMO_LEARNER_EMAIL = "sofia.aprendiz@skillmatch.com"


async def clean_demo_data() -> None:
    """Elimina quirúrgicamente solo los datos de demostración creados."""
    logger.info("Iniciando limpieza controlada de datos de demostración...")
    async with AsyncSessionLocal() as db:
        # 1. Obtener IDs de usuarios demo
        user_res = await db.execute(
            select(User).where(
                User.email.in_([DEMO_INSTRUCTOR_EMAIL, DEMO_LEARNER_EMAIL])
            )
        )
        demo_users = user_res.scalars().all()
        user_ids = [u.id for u in demo_users]

        if user_ids:
            # Eliminar reseñas
            await db.execute(
                delete(SessionReview).where(
                    (SessionReview.reviewer_id.in_(user_ids))
                    | (SessionReview.reviewed_id.in_(user_ids))
                )
            )
            # Eliminar quejas
            await db.execute(
                delete(Complaint).where(Complaint.user_id.in_(user_ids))
            )
            # Eliminar notificaciones
            await db.execute(
                delete(Notification).where(Notification.recipient_id.in_(user_ids))
            )
            # Eliminar sesiones de intercambio donde participen
            await db.execute(
                delete(ExchangeSession).where(
                    (ExchangeSession.instructor_id.in_(user_ids))
                    | (ExchangeSession.learner_id.in_(user_ids))
                )
            )
            # Eliminar matches
            await db.execute(
                delete(Match).where(
                    (Match.member_a_id.in_(user_ids))
                    | (Match.member_b_id.in_(user_ids))
                )
            )
            # Eliminar habilidades de enseñanza
            await db.execute(
                delete(TeachingSkill).where(TeachingSkill.user_id.in_(user_ids))
            )
            # Eliminar habilidades de aprendizaje
            await db.execute(
                delete(UserLearningSkill).where(
                    UserLearningSkill.user_id.in_(user_ids)
                )
            )
            # Eliminar billeteras
            await db.execute(
                delete(Wallet).where(Wallet.user_id.in_(user_ids))
            )
            # Eliminar usuarios
            await db.execute(
                delete(User).where(User.id.in_(user_ids))
            )

        await db.commit()
        logger.info("Limpieza completada exitosamente.")


async def seed_all_demo() -> None:
    """Ejecuta el provisionamiento completo del ecosistema con preguntas, desafíos, reseñas y métricas."""
    logger.info("=====================================================")
    logger.info("  SkillMatch — Provisionamiento Completo E2E         ")
    logger.info("=====================================================")

    async with AsyncSessionLocal() as db:
        # 1. Asegurar Admin, Catálogo Canónico y Banco de Preguntas Teóricas
        await ensure_initial_admin(db)
        await ensure_initial_catalog(db)
        await ensure_initial_theory_questions(db)

        # 2. Recuperar categorías y habilidades
        skills_res = await db.execute(
            select(Skill).where(
                Skill.slug.in_([
                    "programacion-en-python",
                    "tocar-flauta",
                    "dominadas-con-el-balon",
                ])
            )
        )
        skills = {s.slug: s for s in skills_res.scalars().all()}
        python_skill = skills.get("programacion-en-python")
        flute_skill = skills.get("tocar-flauta")
        football_skill = skills.get("dominadas-con-el-balon")

        if not python_skill or not flute_skill or not football_skill:
            logger.error("No se encontraron las habilidades canónicas esperadas en la base de datos.")
            return

        # 3. Obtener el usuario administrador (para vincular retos del sandbox)
        admin_res = await db.execute(
            select(User).where(User.email == settings.ADMIN_EMAIL.lower().strip())
        )
        admin_user = admin_res.scalar_one_or_none()

        # 4. Crear o sincronizar usuarios MEMBER demo
        demo_pwd_hash = get_password_hash("SkillMatchDemo2026!")

        # Carlos (Instructor Python, desea aprender Dominadas)
        carlos_res = await db.execute(
            select(User).where(User.email == DEMO_INSTRUCTOR_EMAIL)
        )
        carlos = carlos_res.scalar_one_or_none()
        if not carlos:
            carlos = User(
                email=DEMO_INSTRUCTOR_EMAIL,
                full_name="Carlos Mendoza (Instructor)",
                hashed_password=demo_pwd_hash,
                role=UserRole.MEMBER,
                is_active=True,
                is_locked=False,
                provider="google",
            )
            db.add(carlos)
            await db.flush()
            logger.info(f"Usuario demo creado: {carlos.email}")

        # Sofía (Instructora Dominadas, desea aprender Python)
        sofia_res = await db.execute(
            select(User).where(User.email == DEMO_LEARNER_EMAIL)
        )
        sofia = sofia_res.scalar_one_or_none()
        if not sofia:
            sofia = User(
                email=DEMO_LEARNER_EMAIL,
                full_name="Sofía Paredes (Aprendiz)",
                hashed_password=demo_pwd_hash,
                role=UserRole.MEMBER,
                is_active=True,
                is_locked=False,
                provider="google",
            )
            db.add(sofia)
            await db.flush()
            logger.info(f"Usuario demo creado: {sofia.email}")

        # 5. Billeteras con saldo inicial de 100 SkillPoints
        for u in [carlos, sofia]:
            w_res = await db.execute(select(Wallet).where(Wallet.user_id == u.id))
            wallet = w_res.scalar_one_or_none()
            if not wallet:
                wallet = Wallet(
                    user_id=u.id,
                    balance=100,
                    escrow_balance=0,
                )
                db.add(wallet)
                logger.info(f"Billetera creada para {u.email} con 100 SkillPoints.")
            else:
                if wallet.balance < 50:
                    wallet.balance = 100
                logger.info(f"Billetera verificada para {u.email}: {wallet.balance} SP.")
        await db.flush()

        # 6. Oferta de habilidades (TeachingSkill)
        # Carlos ofrece enseñar Programación en Python
        carlos_ts_res = await db.execute(
            select(TeachingSkill).where(
                TeachingSkill.user_id == carlos.id,
                TeachingSkill.skill_id == python_skill.id,
            )
        )
        carlos_ts = carlos_ts_res.scalar_one_or_none()
        if not carlos_ts:
            carlos_ts = TeachingSkill(
                user_id=carlos.id,
                skill_id=python_skill.id,
                declared_level="ADVANCED",
                years_of_experience=5,
                description="Desarrollador backend senior con experiencia en Python, FastAPI y Docker.",
                accepts_points=True,
                hourly_points_rate=20,
                status="VERIFICADA",
            )
            db.add(carlos_ts)
            logger.info("Oferta formativa agregada: Carlos -> Programación en Python.")

        # Sofía ofrece enseñar Dominadas con el balón
        sofia_ts_res = await db.execute(
            select(TeachingSkill).where(
                TeachingSkill.user_id == sofia.id,
                TeachingSkill.skill_id == football_skill.id,
            )
        )
        sofia_ts = sofia_ts_res.scalar_one_or_none()
        if not sofia_ts:
            sofia_ts = TeachingSkill(
                user_id=sofia.id,
                skill_id=football_skill.id,
                declared_level="ADVANCED",
                years_of_experience=4,
                description="Entrenadora técnica de fútbol juvenil especializada en destreza y control.",
                accepts_points=True,
                hourly_points_rate=15,
                status="VERIFICADA",
            )
            db.add(sofia_ts)
            logger.info("Oferta formativa agregada: Sofía -> Dominadas con el balón.")

        await db.flush()

        # 7. Demanda de aprendizaje (UserLearningSkill)
        # Carlos desea aprender Dominadas con el balón
        carlos_ls_res = await db.execute(
            select(UserLearningSkill).where(
                UserLearningSkill.user_id == carlos.id,
                UserLearningSkill.skill_id == football_skill.id,
            )
        )
        if not carlos_ls_res.scalar_one_or_none():
            db.add(
                UserLearningSkill(
                    user_id=carlos.id,
                    skill_id=football_skill.id,
                    current_level=1,
                    target_level=3,
                    urgency=UrgencyLevel.HIGH,
                    notes="Quiero mejorar mi coordinación física y control del balón los fines de semana.",
                )
            )
            logger.info("Interés de aprendizaje: Carlos -> Dominadas con el balón.")

        # Sofía desea aprender Programación en Python
        sofia_ls_res = await db.execute(
            select(UserLearningSkill).where(
                UserLearningSkill.user_id == sofia.id,
                UserLearningSkill.skill_id == python_skill.id,
            )
        )
        if not sofia_ls_res.scalar_one_or_none():
            db.add(
                UserLearningSkill(
                    user_id=sofia.id,
                    skill_id=python_skill.id,
                    current_level=1,
                    target_level=4,
                    urgency=UrgencyLevel.HIGH,
                    notes="Quiero aprender a automatizar reportes de entrenamiento con Python.",
                )
            )
            logger.info("Interés de aprendizaje: Sofía -> Programación en Python.")

        await db.flush()

        # 8. Emparejamiento / Match directo
        member_a_id = min(carlos.id, sofia.id)
        member_b_id = max(carlos.id, sofia.id)
        match_res = await db.execute(
            select(Match).where(
                Match.member_a_id == member_a_id,
                Match.member_b_id == member_b_id,
            )
        )
        match_obj = match_res.scalar_one_or_none()
        if not match_obj:
            match_obj = Match(
                member_a_id=member_a_id,
                member_b_id=member_b_id,
                status="accepted",
            )
            db.add(match_obj)
            await db.flush()
            logger.info("Match bilateral creado y aceptado entre Carlos y Sofía (100% afinidad).")

        # 9. Sesiones de Intercambio (Futura aceptada y Previa completada)
        now = datetime.now(timezone.utc)

        # 9.1 Sesión futura aceptada para pruebas de sala de chat e iCal
        future_start = (now + timedelta(days=1)).replace(hour=15, minute=0, second=0, microsecond=0)
        future_end = future_start + timedelta(minutes=60)

        future_sess_res = await db.execute(
            select(ExchangeSession).where(
                ExchangeSession.instructor_id == carlos.id,
                ExchangeSession.learner_id == sofia.id,
                ExchangeSession.status == "ACCEPTED",
            )
        )
        if not future_sess_res.scalar_one_or_none():
            db.add(
                ExchangeSession(
                    match_id=match_obj.id,
                    teaching_skill_id=carlos_ts.id,
                    created_by_id=sofia.id,
                    instructor_id=carlos.id,
                    learner_id=sofia.id,
                    starts_at=future_start,
                    ends_at=future_end,
                    timezone="UTC",
                    modality="VIRTUAL",
                    status="ACCEPTED",
                    is_free=False,
                    points_required=20,
                    payment_state="RESERVED",
                )
            )
            logger.info("Sesión futura aceptada agendada para mañana a las 15:00 UTC.")

        # 9.2 Sesión previa completada con reseña de 5 estrellas
        past_start = (now - timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0)
        past_end = past_start + timedelta(minutes=50)

        past_sess_res = await db.execute(
            select(ExchangeSession).where(
                ExchangeSession.instructor_id == carlos.id,
                ExchangeSession.learner_id == sofia.id,
                ExchangeSession.status == "COMPLETED",
            )
        )
        past_session = past_sess_res.scalar_one_or_none()
        if not past_session:
            past_session = ExchangeSession(
                match_id=match_obj.id,
                teaching_skill_id=carlos_ts.id,
                created_by_id=sofia.id,
                instructor_id=carlos.id,
                learner_id=sofia.id,
                starts_at=past_start,
                ends_at=past_end,
                timezone="UTC",
                actual_minutes=50,
                modality="VIRTUAL",
                status="COMPLETED",
                is_free=False,
                points_required=20,
                payment_state="RELEASED",
                completed_at=past_end,
            )
            db.add(past_session)
            await db.flush()
            logger.info("Sesión histórica completada aprovisionada con éxito.")

        # 10. Reseña bilateral de intercambio (SessionReview)
        review_res = await db.execute(
            select(SessionReview).where(
                SessionReview.session_id == past_session.id,
                SessionReview.reviewer_id == sofia.id,
            )
        )
        if not review_res.scalar_one_or_none():
            db.add(
                SessionReview(
                    session_id=past_session.id,
                    reviewer_id=sofia.id,
                    reviewed_id=carlos.id,
                    rating_punctuality=5,
                    rating_pedagogy=5,
                    rating_domain=5,
                    overall_rating=5.0,
                    comment="Excelente sesión. Carlos explicó la recursión y decoradores en Python con mucha claridad y ejemplos prácticos.",
                    role_in_session="LEARNER",
                )
            )
            logger.info("Reseña 5 estrellas creada de Sofía hacia Carlos.")

        # 11. Notificaciones en bandeja (Notification)
        notif_samples = [
            (carlos.id, NotificationType.MATCH_CONFIRMED.value, "¡Nuevo Match Confirmado!", "Tienes un nuevo match de intercambio de habilidades con Sofía Paredes.", False),
            (carlos.id, NotificationType.SESSION_ACCEPTED.value, "Sesión Confirmada: Programación en Python", "Tu sesión virtual de intercambio con Sofía ha sido confirmada.", True),
            (carlos.id, NotificationType.POINTS_RECEIVED.value, "SkillPoints Acreditados", "Has recibido 20 SkillPoints por completar exitosamente una sesión formativa.", False),
            (sofia.id, NotificationType.MATCH_CONFIRMED.value, "¡Nuevo Match Confirmado!", "Tienes un nuevo match de intercambio de habilidades con Carlos Mendoza.", False),
            (sofia.id, NotificationType.SESSION_ACCEPTED.value, "Sesión Programada", "Tu sesión de Programación en Python está agendada para mañana a las 15:00 UTC.", False),
        ]
        for user_id, ntype, title, message, is_read in notif_samples:
            existing_notif = await db.execute(
                select(Notification).where(
                    Notification.user_id == user_id,
                    Notification.title == title,
                )
            )
            if not existing_notif.scalar_one_or_none():
                db.add(
                    Notification(
                        id=uuid.uuid4(),
                        user_id=user_id,
                        event_id=uuid.uuid4(),
                        type=ntype,
                        title=title,
                        message=message,
                        read_at=datetime.now(timezone.utc) if is_read else None,
                    )
                )
        logger.info("Notificaciones de bienvenida y actividad sincronizadas.")

        # 12. Caso de Disputa / Queja para Moderación en Panel Admin (Complaint)
        complaint_res = await db.execute(
            select(Complaint).where(Complaint.user_id == sofia.id)
        )
        if not complaint_res.scalar_one_or_none():
            db.add(
                Complaint(
                    user_id=sofia.id,
                    session_id=past_session.id,
                    reason=ComplaintReason.QUALITY_ISSUE.value,
                    title="Audio intermitente en primeros minutos de sesión",
                    description="El audio de la videollamada presentó intermitencias técnicas breves durante los primeros 5 minutos de la sesión.",
                    status=ComplaintStatus.RESOLVED.value,
                    points_compensated=5,
                )
            )
            logger.info("Caso de queja resuelto registrado para visualización en panel admin.")

        # 13. Desafíos de programación para Sandbox (Programming Challenges)
        if admin_user:
            challenges_to_seed = [
                {
                    "level": 1,
                    "title": "Suma de Números Pares en una Lista",
                    "statement": (
                        "Implementa la función `solve(numbers: list[int]) -> int` que recibe "
                        "una lista de números enteros y devuelve la suma total de todos los números "
                        "que sean estrictamente pares. Si no hay pares o la lista está vacía, devuelve 0."
                    ),
                    "starter": (
                        "def solve(numbers: list[int]) -> int:\n"
                        "    # Escribe tu solución aquí\n"
                        "    return sum(n for n in numbers if n % 2 == 0)\n"
                    ),
                    "tests": [
                        ("Caso público 1 (básico)", "[1, 2, 3, 4, 5, 6]", "6", "PUBLIC", 0),
                        ("Caso público 2 (sin pares)", "[1, 3, 5, 7]", "0", "PUBLIC", 1),
                        ("Caso oculto 1 (números grandes)", "[10, 21, 32, 43, 54]", "96", "HIDDEN", 2),
                        ("Caso oculto 2 (vacío)", "[]", "0", "HIDDEN", 3),
                        ("Caso oculto 3 (negativos pares)", "[-2, -4, 3, 5]", "-6", "HIDDEN", 4),
                    ],
                },
                {
                    "level": 2,
                    "title": "Inversión de Palabras en una Frase",
                    "statement": (
                        "Implementa la función `solve(sentence: str) -> str` que reciba una cadena "
                        "de texto y devuelva las palabras en orden inverso, normalizando los espacios intermedios."
                    ),
                    "starter": (
                        "def solve(sentence: str) -> str:\n"
                        "    # Escribe tu solución aquí\n"
                        "    return ' '.join(sentence.split()[::-1])\n"
                    ),
                    "tests": [
                        ("Caso público 1", "'hola mundo'", "mundo hola", "PUBLIC", 0),
                        ("Caso público 2", "'python es genial'", "genial es python", "PUBLIC", 1),
                        ("Caso oculto 1 (espacios múltiples)", "'  muchos   espacios   aqui  '", "aqui espacios muchos", "HIDDEN", 2),
                        ("Caso oculto 2 (una palabra)", "'palabra'", "palabra", "HIDDEN", 3),
                    ],
                },
                {
                    "level": 3,
                    "title": "Validación de Paréntesis y Corchetes Balanceados",
                    "statement": (
                        "Implementa la función `solve(s: str) -> bool` que verifique si una secuencia "
                        "de caracteres formada por '()[]{}' está correctamente balanceada y anidada."
                    ),
                    "starter": (
                        "def solve(s: str) -> bool:\n"
                        "    stack = []\n"
                        "    pairs = {')': '(', '}': '{', ']': '['}\n"
                        "    for ch in s:\n"
                        "        if ch in '({[':\n"
                        "            stack.append(ch)\n"
                        "        elif ch in pairs:\n"
                        "            if not stack or stack.pop() != pairs[ch]:\n"
                        "                return False\n"
                        "    return len(stack) == 0\n"
                    ),
                    "tests": [
                        ("Caso público 1", "'()[]{}'", "True", "PUBLIC", 0),
                        ("Caso público 2", "'([)]'", "False", "PUBLIC", 1),
                        ("Caso oculto 1", "'{[]}'", "True", "HIDDEN", 2),
                        ("Caso oculto 2", "'((('", "False", "HIDDEN", 3),
                        ("Caso oculto 3", "''", "True", "HIDDEN", 4),
                    ],
                },
            ]

            for c_data in challenges_to_seed:
                chal_res = await db.execute(
                    select(Challenge).where(
                        Challenge.skill_id == python_skill.id,
                        Challenge.level_number == c_data["level"],
                        Challenge.version == 1,
                    )
                )
                challenge = chal_res.scalar_one_or_none()
                if not challenge:
                    challenge = Challenge(
                        skill_id=python_skill.id,
                        challenge_type_id=python_skill.challenge_type_id,
                        level_number=c_data["level"],
                        version=1,
                        title=c_data["title"],
                        statement=c_data["statement"],
                        evaluation_modality="SANDBOX",
                        execution_profile="PYTHON_3_12",
                        starter_code=c_data["starter"],
                        time_limit_ms=2000,
                        memory_limit_mb=128,
                        max_output_bytes=65536,
                        status="PUBLISHED",
                        created_by_id=admin_user.id,
                        published_at=datetime.now(timezone.utc),
                    )
                    db.add(challenge)
                    await db.flush()

                    for name, stdin_data, stdout, vis, idx in c_data["tests"]:
                        db.add(
                            ChallengeTestCase(
                                challenge_id=challenge.id,
                                name=name,
                                stdin_data=stdin_data,
                                expected_stdout=stdout,
                                visibility=vis,
                                order_index=idx,
                            )
                        )
                    logger.info(f"Desafío de programación Python Nivel {c_data['level']} aprovisionado.")

        # 14. Muestras de Dataset de Laboratorio (DatasetSample)
        storage_samples = [
            {
                "discipline": "futbol",
                "challenge": "Dominadas con el balón",
                "file_format": "mp4",
                "file_size": 2048000,
                "path": "datasets/futbol/dd325c36-ee15-46b4-86dd-b82c6eb9107a.mp4",
                "skill": football_skill,
                "role": "REFERENCE",
                "touch_count": 12,
            },
            {
                "discipline": "musica",
                "challenge": "Tocar flauta",
                "file_format": "wav",
                "file_size": 1024000,
                "path": "datasets/musica/6d074e54-65e1-4f75-8d49-1276da4f09ed.wav",
                "skill": flute_skill,
                "role": "REFERENCE",
                "touch_count": None,
            },
            {
                "discipline": "programacion",
                "challenge": "Programación en Python",
                "file_format": "py",
                "file_size": 4096,
                "path": "datasets/programacion/1ace7c6a-b541-4e55-9535-2bc582e75e9c.py",
                "skill": python_skill,
                "role": "REFERENCE",
                "touch_count": None,
            },
        ]

        for s_data in storage_samples:
            existing_ds_res = await db.execute(
                select(DatasetSample).where(
                    DatasetSample.storage_path == s_data["path"]
                )
            )
            if not existing_ds_res.scalar_one_or_none():
                sample_hash = hashlib.sha256(s_data["path"].encode()).hexdigest()
                db.add(
                    DatasetSample(
                        discipline=s_data["discipline"],
                        challenge=s_data["challenge"],
                        hardware_info="standard-device",
                        signed_consent=True,
                        file_format=s_data["file_format"],
                        file_size_bytes=s_data["file_size"],
                        file_hash_sha256=sample_hash,
                        storage_path=s_data["path"],
                        uploaded_by_id=admin_user.id if admin_user else None,
                        level_label="Nivel 1",
                        manual_touch_count=s_data["touch_count"],
                        sample_role=s_data["role"],
                        skill_id=s_data["skill"].id,
                    )
                )
                logger.info(f"Muestra de laboratorio registrada: {s_data['challenge']}.")

        await db.commit()

    logger.info("=====================================================")
    logger.info("  ¡Aprovisionamiento completado con éxito al 100%!   ")
    logger.info("=====================================================")
    logger.info("Usuarios creados:")
    logger.info(f"  - Instructor: {DEMO_INSTRUCTOR_EMAIL} (100 SP)")
    logger.info(f"  - Aprendiz:   {DEMO_LEARNER_EMAIL} (100 SP)")
    logger.info("Banco de preguntas:")
    logger.info("  - 15 preguntas teóricas distribuidas en Programación, Música y Fútbol")
    logger.info("Desafíos de Sandbox:")
    logger.info("  - 3 Retos de programación Python (Nivel 1, 2 y 3) con Pytest")
    logger.info("Interacciones comunitarias:")
    logger.info("  - Match 100% afinidad entre Carlos y Sofía")
    logger.info("  - 1 Sesión futura aceptada + 1 Sesión histórica completada")
    logger.info("  - 1 Reseña de 5 estrellas con feedback detallado")
    logger.info("  - 5 Notificaciones activas en bandeja")
    logger.info("  - 1 Caso de queja/moderación para el panel de administración")


async def main() -> None:
    parser = argparse.ArgumentParser(description="SkillMatch Demo Data Seeder")
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Elimina solo los datos de demostración creados sin tocar datos del sistema.",
    )
    args = parser.parse_args()

    if args.cleanup:
        await clean_demo_data()
    else:
        await seed_all_demo()


if __name__ == "__main__":
    asyncio.run(main())
