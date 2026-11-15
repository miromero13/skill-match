import logging
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.user import User, UserRole
from app.models.catalog import Category, ChallengeType, Skill, SkillLevel, Rubric
from app.schemas.catalog import CANONICAL_LEVELS

logger = logging.getLogger("skillmatch.seed")


async def ensure_initial_catalog(db: AsyncSession) -> None:
    """
    Garantiza la existencia de las categorías y habilidades maestras canónicas
    para las tres áreas de validación con IA propia (Programación, Música, Fútbol).
    Es 100% idempotente.
    """
    # 1. Categorías canónicas
    canonical_categories = [
        {"name": "Programación y Software", "slug": "programacion-y-software", "description": "Desarrollo de software, algoritmos, frontend y backend."},
        {"name": "Música e Instrumentos", "slug": "musica-e-instrumentos", "description": "Ejecución instrumental, técnica armónica y rítmica."},
        {"name": "Deportes y Fútbol", "slug": "deportes-y-futbol", "description": "Técnica individual, control de balón y destreza deportiva."},
    ]

    cat_map = {}
    for cat_data in canonical_categories:
        res = await db.execute(select(Category).where(Category.slug == cat_data["slug"]))
        cat = res.scalar_one_or_none()
        if not cat:
            cat = Category(
                name=cat_data["name"],
                slug=cat_data["slug"],
                description=cat_data["description"],
                is_active=True,
            )
            db.add(cat)
            await db.flush()
            logger.info(f"Categoría canónica creada: {cat.name}")
        cat_map[cat.slug] = cat

    # 2. Tipos de Desafío
    challenge_data = [
        {"name": "Sandbox de Código AST", "code": "CODE_AST", "evaluation_modality": "sandbox", "description": "Ejecución aislada y análisis de árbol sintáctico abstracto."},
        {"name": "Espectrograma de Audio", "code": "AUDIO_SPECTRAL", "evaluation_modality": "audio", "description": "Análisis espectral de tono, afinación y ritmo con librosa."},
        {"name": "Visión por Computadora y Pose", "code": "VISION_POSE", "evaluation_modality": "video", "description": "Tracking de balón y puntos articulares con OpenCV y PyTorch."},
    ]

    ct_map = {}
    for ct in challenge_data:
        res = await db.execute(select(ChallengeType).where(ChallengeType.code == ct["code"]))
        item = res.scalar_one_or_none()
        if not item:
            item = ChallengeType(
                name=ct["name"],
                code=ct["code"],
                evaluation_modality=ct["evaluation_modality"],
                description=ct["description"],
                is_active=True,
            )
            db.add(item)
            await db.flush()
        ct_map[ct["code"]] = item

    # 3. Habilidades canónicas iniciales
    initial_skills = [
        {
            "name": "Python y FastAPI",
            "slug": "python-y-fastapi",
            "cat_slug": "programacion-y-software",
            "ct_code": "CODE_AST",
            "desc": "Construcción de APIs REST asíncronas de alto rendimiento y arquitectura limpia.",
        },
        {
            "name": "React y TypeScript",
            "slug": "react-y-typescript",
            "cat_slug": "programacion-y-software",
            "ct_code": "CODE_AST",
            "desc": "Desarrollo de interfaces reactivas con tipado estricto y gestión de estado.",
        },
        {
            "name": "Guitarra Acústica",
            "slug": "guitarra-acustica",
            "cat_slug": "musica-e-instrumentos",
            "ct_code": "AUDIO_SPECTRAL",
            "desc": "Técnica de digitación, acordes, ritmo y afinación de guitarra.",
        },
        {
            "name": "Piano y Teclado",
            "slug": "piano-y-teclado",
            "cat_slug": "musica-e-instrumentos",
            "ct_code": "AUDIO_SPECTRAL",
            "desc": "Lectura musical, armonía y ejecución en teclado.",
        },
        {
            "name": "Dominadas y Control de Balón",
            "slug": "dominadas-y-control-de-balon",
            "cat_slug": "deportes-y-futbol",
            "ct_code": "VISION_POSE",
            "desc": "Destreza motriz, repeticiones de dominadas y control orientado.",
        },
    ]

    for sk in initial_skills:
        res = await db.execute(select(Skill).where(Skill.slug == sk["slug"]))
        existing_skill = res.scalar_one_or_none()
        if not existing_skill:
            category = cat_map.get(sk["cat_slug"])
            challenge_type = ct_map.get(sk["ct_code"])
            if category:
                new_skill = Skill(
                    category_id=category.id,
                    challenge_type_id=challenge_type.id if challenge_type else None,
                    name=sk["name"],
                    slug=sk["slug"],
                    description=sk["desc"],
                    min_approval_threshold=80.0,
                    is_ready_to_publish=True,
                    is_active=True,
                )
                db.add(new_skill)
                await db.flush()

                # Crear escalera canónica de 5 niveles
                for lvl_num, lvl_name in CANONICAL_LEVELS.items():
                    skill_level = SkillLevel(
                        skill_id=new_skill.id,
                        level_number=lvl_num,
                        name=lvl_name,
                        description=f"Nivel {lvl_num}: {lvl_name}",
                    )
                    db.add(skill_level)
                    await db.flush()

                    rubric = Rubric(
                        skill_level_id=skill_level.id,
                        instructions=f"Evaluación práctica y teórica para {new_skill.name} Nivel {lvl_num}.",
                        min_score=70.0,
                        criteria=[
                            {"name": "Precisión y Ejecución Técnica", "weight": 50, "description": "Solvencia y exactitud del gesto técnico."},
                            {"name": "Fundamentos Teóricos", "weight": 50, "description": "Comprensión conceptual de los principios evaluados."},
                        ],
                    )
                    db.add(rubric)

                logger.info(f"Habilidad canónica aprovisionada: {new_skill.name}")

    await db.commit()

async def ensure_initial_admin(db: AsyncSession) -> None:
    """
    Garantiza la existencia del Administrador inicial del sistema.
    - Se ejecuta automáticamente durante el startup de la aplicación.
    - No utiliza datos ficticios o de prueba: las credenciales provienen
      estrictamente de las variables de entorno (.env): ADMIN_EMAIL, ADMIN_PASSWORD y ADMIN_FULL_NAME.
    - Es 100% idempotente: si el usuario ya existe, no realiza ninguna inserción duplicada.
    """
    email = settings.ADMIN_EMAIL.lower().strip()

    # 1. Verificar si el usuario administrador ya existe
    result = await db.execute(select(User).where(User.email == email))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        # Asegurar que conserve rol ADMIN y esté activo si fue creado previamente
        if existing_user.role != UserRole.ADMIN or not existing_user.is_active:
            existing_user.role = UserRole.ADMIN
            existing_user.is_active = True
            await db.commit()
            logger.info(f"Estado de cuenta para administrador {email} sincronizado.")
        return

    # 2. Crear el único administrador inicial autorizado
    hashed_pwd = get_password_hash(settings.ADMIN_PASSWORD.get_secret_value())
    admin_user = User(
        email=email,
        full_name=settings.ADMIN_FULL_NAME,
        hashed_password=hashed_pwd,
        role=UserRole.ADMIN,
        is_active=True,
        is_locked=False,
        failed_login_attempts=0,
        provider="institutional"
    )

    db.add(admin_user)
    try:
        await db.commit()
        logger.info(f"Administrador inicial provisionado exitosamente desde variables de entorno: {email}")
    except Exception as exc:
        await db.rollback()
        logger.error(f"Error al provisionar el administrador inicial: {exc}")
        raise
