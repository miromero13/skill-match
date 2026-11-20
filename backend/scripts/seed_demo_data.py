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
3. Usuarios demo (Instructor y Aprendiz) con billeteras y saldo de 100 SkillPoints.
4. Habilidades ofrecidas (TeachingSkill) y deseadas (UserLearningSkill).
5. Match mutuo precalculado (100% afinidad).
6. Sesión de intercambio (ExchangeSession) virtual aceptada con enlace de reunión.
7. Desafío de programación (Challenge) nivel 1 publicado con casos de prueba para el sandbox Docker.
8. Muestras de dataset de laboratorio (DatasetSample) enlazadas a las habilidades.

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
from app.db.seed import ensure_initial_admin, ensure_initial_catalog
from app.models.catalog import Category, ChallengeType, Skill, SkillLevel, Rubric
from app.models.dataset_sample import DatasetSample
from app.models.exchange_session import ExchangeSession
from app.models.match import Match
from app.models.programming import Challenge, ChallengeTestCase
from app.models.teaching_skill import TeachingSkill
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
    """Ejecuta el provisionamiento completo del ecosistema."""
    logger.info("=====================================================")
    logger.info("  SkillMatch — Provisionamiento de Datos E2E         ")
    logger.info("=====================================================")

    async with AsyncSessionLocal() as db:
        # 1. Asegurar Admin y Catálogo Canónico (3 categorías, 3 habilidades)
        await ensure_initial_admin(db)
        await ensure_initial_catalog(db)

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
        if not carlos_ts_res.scalar_one_or_none():
            db.add(
                TeachingSkill(
                    user_id=carlos.id,
                    skill_id=python_skill.id,
                    declared_level="ADVANCED",
                    years_of_experience=5,
                    description="Desarrollador backend senior con experiencia en Python, FastAPI y Docker.",
                    accepts_points=True,
                    hourly_points_rate=20,
                    status="VERIFICADA",
                )
            )
            logger.info("Oferta formativa agregada: Carlos -> Programación en Python.")

        # Sofía ofrece enseñar Dominadas con el balón
        sofia_ts_res = await db.execute(
            select(TeachingSkill).where(
                TeachingSkill.user_id == sofia.id,
                TeachingSkill.skill_id == football_skill.id,
            )
        )
        if not sofia_ts_res.scalar_one_or_none():
            db.add(
                TeachingSkill(
                    user_id=sofia.id,
                    skill_id=football_skill.id,
                    declared_level="ADVANCED",
                    years_of_experience=4,
                    description="Entrenadora técnica de fútbol juvenil especializada en destreza y control.",
                    accepts_points=True,
                    hourly_points_rate=15,
                    status="VERIFICADA",
                )
            )
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

        # 9. Sesión de Intercambio (ExchangeSession) para pruebas de chat y agendamiento
        now = datetime.now(timezone.utc)
        start_time = (now + timedelta(days=1)).replace(hour=15, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(minutes=60)

        sess_res = await db.execute(
            select(ExchangeSession).where(
                ExchangeSession.instructor_id == carlos.id,
                ExchangeSession.learner_id == sofia.id,
            )
        )
        existing_sess = sess_res.scalar_one_or_none()
        if not existing_sess:
            exchange_session = ExchangeSession(
                instructor_id=carlos.id,
                learner_id=sofia.id,
                skill_id=python_skill.id,
                starts_at=start_time,
                ends_at=end_time,
                modality="VIRTUAL",
                status="ACCEPTED",
                points_required=20,
                payment_state="RESERVED",
                meeting_url="https://meet.google.com/skm-demo-test",
            )
            db.add(exchange_session)
            await db.flush()
            logger.info("Sesión de intercambio de demostración agendada para mañana a las 15:00 UTC.")

        # 10. Desafío de programación para el Sandbox (Programming Challenge)
        if admin_user:
            chal_res = await db.execute(
                select(Challenge).where(
                    Challenge.skill_id == python_skill.id,
                    Challenge.level_number == 1,
                    Challenge.version == 1,
                )
            )
            challenge = chal_res.scalar_one_or_none()
            if not challenge:
                challenge = Challenge(
                    skill_id=python_skill.id,
                    challenge_type_id=python_skill.challenge_type_id,
                    level_number=1,
                    version=1,
                    title="Suma de Números Pares en una Lista",
                    statement=(
                        "Implementa la función `solve(numbers: list[int]) -> int` que recibe "
                        "una lista de números enteros y devuelve la suma total de todos los números "
                        "que sean estrictamente pares. Si no hay pares o la lista está vacía, devuelve 0."
                    ),
                    evaluation_modality="SANDBOX",
                    execution_profile="PYTHON_3_12",
                    starter_code=(
                        "def solve(numbers: list[int]) -> int:\n"
                        "    # Escribe tu solución aquí\n"
                        "    return sum(n for n in numbers if n % 2 == 0)\n"
                    ),
                    time_limit_ms=2000,
                    memory_limit_mb=128,
                    max_output_bytes=65536,
                    status="PUBLISHED",
                    created_by_id=admin_user.id,
                    published_at=datetime.now(timezone.utc),
                )
                db.add(challenge)
                await db.flush()

                # Casos de prueba
                test_cases = [
                    ("Caso público 1 (básico)", "[1, 2, 3, 4, 5, 6]", "6", "PUBLIC", 0),
                    ("Caso público 2 (sin pares)", "[1, 3, 5, 7]", "0", "PUBLIC", 1),
                    ("Caso oculto 1 (números grandes)", "[10, 21, 32, 43, 54]", "96", "HIDDEN", 2),
                    ("Caso oculto 2 (vacío)", "[]", "0", "HIDDEN", 3),
                    ("Caso oculto 3 (negativos pares)", "[-2, -4, 3, 5]", "-6", "HIDDEN", 4),
                ]
                for name, stdin_data, stdout, vis, idx in test_cases:
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
                logger.info("Desafío de programación Python Nivel 1 aprovisionado con 5 casos de prueba.")

        # 11. Muestras de Dataset de Laboratorio (DatasetSample)
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
    logger.info("Habilidades aprovisionadas:")
    logger.info("  - Programación en Python (Programación, CODE_AST)")
    logger.info("  - Tocar flauta (Música, AUDIO_SPECTRAL)")
    logger.info("  - Dominadas con el balón (Fútbol, VISION_POSE)")


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
