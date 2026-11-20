import logging
import uuid
from datetime import datetime, timezone
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
    Es 100% idempotente y mantiene compatibilidad con registros previos.
    """
    # 1. Categorías canónicas fijas del sistema (estrictamente 3)
    canonical_categories = [
        {
            "name": "Programación",
            "slug": "programacion",
            "description": "Desarrollo de software, algoritmos, arquitectura limpia, frontend y backend.",
        },
        {
            "name": "Música",
            "slug": "musica",
            "description": "Ejecución instrumental, técnica armónica, acústica espectral y ritmo.",
        },
        {
            "name": "Fútbol",
            "slug": "futbol",
            "description": "Técnica individual, control y dominadas de balón, y destreza deportiva.",
        },
    ]

    # Migración/compatibilidad: si existía "deporte", sincronizar nombre a "Fútbol" y slug a "futbol"
    res_deporte = await db.execute(select(Category).where(Category.slug == "deporte"))
    cat_deporte = res_deporte.scalar_one_or_none()
    if cat_deporte:
        cat_deporte.name = "Fútbol"
        cat_deporte.slug = "futbol"
        cat_deporte.description = "Técnica individual, control y dominadas de balón, y destreza deportiva."
        await db.flush()
        logger.info("Categoría 'deporte' migrada a 'futbol'.")

    cat_map: dict[str, Category] = {}
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
        else:
            cat.name = cat_data["name"]
            cat.description = cat_data["description"]
            cat.is_active = True
            await db.flush()
        cat_map[cat.slug] = cat

    # 2. Tipos de Desafío (Modalidades de Evaluación con IA)
    challenge_data = [
        {
            "name": "Sandbox de Código AST",
            "code": "CODE_AST",
            "evaluation_modality": "sandbox",
            "description": "Ejecución aislada y análisis de árbol sintáctico abstracto con Docker y Pytest.",
        },
        {
            "name": "Espectrograma de Audio",
            "code": "AUDIO_SPECTRAL",
            "evaluation_modality": "audio",
            "description": "Análisis espectral de tono, afinación y ritmo con librosa y PyTorch.",
        },
        {
            "name": "Visión por Computadora y Pose",
            "code": "VISION_POSE",
            "evaluation_modality": "video",
            "description": "Tracking de balón y puntos articulares con OpenCV y PyTorch.",
        },
    ]

    ct_map: dict[str, ChallengeType] = {}
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
            logger.info(f"Tipo de desafío creado: {item.name}")
        ct_map[ct["code"]] = item

    # 3. Habilidades canónicas principales con rúbricas especializadas por nivel
    initial_skills = [
        {
            "name": "Dominadas con el balón",
            "slug": "dominadas-con-el-balon",
            "cat_slug": "futbol",
            "ct_code": "VISION_POSE",
            "desc": "Técnica individual, repeticiones consecutivas de dominadas y control de balón evaluado por visión por computadora y tracking de pose.",
            "rubrics": {
                1: {
                    "instructions": "Realizar al menos 5 dominadas consecutivas con el pie dominante manteniendo la postura erguida.",
                    "criteria": [
                        {"name": "Repeticiones y Control de Rebote", "weight": 60, "description": "Mantener el balón en el aire sin tocar el piso durante al menos 5 toques."},
                        {"name": "Equilibrio y Postura Corporal", "weight": 40, "description": "Centro de gravedad estable y flexión adecuada de rodilla."},
                    ],
                },
                2: {
                    "instructions": "Realizar al menos 10 dominadas alternando pie derecho e izquierdo a una altura constante.",
                    "criteria": [
                        {"name": "Alternancia de Perfiles", "weight": 50, "description": "Toques equilibrados entre pie derecho e izquierdo."},
                        {"name": "Regularidad de Altura", "weight": 50, "description": "Balón elevado entre cintura y pecho sin dispersión lateral excesiva."},
                    ],
                },
                3: {
                    "instructions": "Realizar al menos 20 dominadas combinando pies y muslos con control continuo.",
                    "criteria": [
                        {"name": "Variedad de Superficies de Contacto", "weight": 50, "description": "Uso coordinado de empeines y muslos en la secuencia."},
                        {"name": "Amortiguación y Suavidad", "weight": 50, "description": "Impacto suave que no desplace el balón fuera del radio de control."},
                    ],
                },
                4: {
                    "instructions": "Realizar al menos 35 dominadas con control orientado y cambios de ritmo en espacio reducido.",
                    "criteria": [
                        {"name": "Control Espacial y Frecuencia", "weight": 50, "description": "Mantenerse dentro de la zona de visión sin desplazamientos erráticos."},
                        {"name": "Consistencia de Cadencia", "weight": 50, "description": "Ritmo constante de golpeo sin pérdida de contacto visual."},
                    ],
                },
                5: {
                    "instructions": "Secuencia libre de 50+ toques con inclusión de gestos avanzados y demostración técnica pedagógica.",
                    "criteria": [
                        {"name": "Maestría Técnica y Variabilidad", "weight": 60, "description": "Control absoluto, variedad de superficies y maniobra fluida."},
                        {"name": "Estabilidad y Precisión Articular", "weight": 40, "description": "Postura biomecánicamente óptima y control gravitatorio perfecto."},
                    ],
                },
            },
        },
        {
            "name": "Tocar flauta",
            "slug": "tocar-flauta",
            "cat_slug": "musica",
            "ct_code": "AUDIO_SPECTRAL",
            "desc": "Técnica de embocadura, digitación, afinación y ejecución melódica evaluada mediante análisis espectrográfico de audio.",
            "rubrics": {
                1: {
                    "instructions": "Ejecutar notas fundamentales (Sol, La, Si / G4, A4, B4) manteniendo el sonido continuo durante 3 segundos.",
                    "criteria": [
                        {"name": "Claridad y Estabilidad Sonora", "weight": 60, "description": "Sonido limpio sin soplido excesivo ni quiebre de tono."},
                        {"name": "Afinación Fundamental (Pitch)", "weight": 40, "description": "Frecuencia fundamental dentro del rango de tolerancia en Hz."},
                    ],
                },
                2: {
                    "instructions": "Interpretar la escala diatónica de Do Mayor completa (C4 a C5) ascendente y descendente.",
                    "criteria": [
                        {"name": "Precisión Interválica y Afinación", "weight": 50, "description": "Entonación precisa de cada grado de la escala a 440 Hz."},
                        {"name": "Digitación y Transición entre Notas", "weight": 50, "description": "Cierre hermético de orificios sin armónicos indeseados."},
                    ],
                },
                3: {
                    "instructions": "Interpretar un ejercicio melódico con articulaciones diferenciadas (staccato y legato) a tempo constante.",
                    "criteria": [
                        {"name": "Ataque y Articulación", "weight": 50, "description": "Ataque claro de lengua para staccato y flujo continuo para legato."},
                        {"name": "Mantenimiento del Pulso Rítmico", "weight": 50, "description": "Estabilidad temporal según metrónomo."},
                    ],
                },
                4: {
                    "instructions": "Interpretar una pieza musical completa aplicando dinámicas de volumen (piano y forte) y fraseo.",
                    "criteria": [
                        {"name": "Rango Dinámico y Expresión", "weight": 50, "description": "Diferenciación contrastada de dinámicas sin perder afinación."},
                        {"name": "Respiración y Fraseo Musical", "weight": 50, "description": "Tomas de aire musicales en los compases adecuados."},
                    ],
                },
                5: {
                    "instructions": "Interpretación de obra de dificultad técnica alta con digitaciones de registro agudo, trinos y control de vibrato.",
                    "criteria": [
                        {"name": "Virtuosismo y Registro Agudo", "weight": 60, "description": "Emisión controlada en octava superior y ornamentaciones fluidas."},
                        {"name": "Calidad Tímbrica y Expresividad Pedagógica", "weight": 40, "description": "Timbre redondo y capacidad de corrección de postura acústica."},
                    ],
                },
            },
        },
        {
            "name": "Programación en Python",
            "slug": "programacion-en-python",
            "cat_slug": "programacion",
            "ct_code": "CODE_AST",
            "desc": "Desarrollo de algoritmos, lógica computacional y resolución de problemas evaluados en sandbox aislado Docker con Pytest y análisis de AST.",
            "rubrics": {
                1: {
                    "instructions": "Implementar scripts que utilicen tipos primitivos, condicionales if/else y bucles for/while cumpliendo los tests.",
                    "criteria": [
                        {"name": "Correctitud Funcional (Test Cases)", "weight": 60, "description": "Aprobación del 100% de los casos de prueba unitarios en el sandbox."},
                        {"name": "Buenas Prácticas y Estilo PEP 8", "weight": 40, "description": "Nomenclatura clara, indentación limpia y sin código muerto."},
                    ],
                },
                2: {
                    "instructions": "Construir funciones modulares tipadas con colecciones (listas, diccionarios, sets) y manejo de excepciones.",
                    "criteria": [
                        {"name": "Modularidad y Tipado Estático", "weight": 50, "description": "Type hints de Python y separación clara de funciones puras."},
                        {"name": "Manejo Seguro de Excepciones", "weight": 50, "description": "Control de KeyError, IndexError y validaciones preventivas."},
                    ],
                },
                3: {
                    "instructions": "Diseñar clases orientadas a objetos, herencia y algoritmos con complejidad temporal < O(n²).",
                    "criteria": [
                        {"name": "Diseño Orientado a Objetos (OOP)", "weight": 50, "description": "Encapsulamiento, métodos de instancia y dunder methods (__str__, __eq__)."},
                        {"name": "Eficiencia Algorítmica y AST", "weight": 50, "description": "Baja complejidad ciclomática (< 10) y uso óptimo de estructuras de datos."},
                    ],
                },
                4: {
                    "instructions": "Implementar generadores, decoradores personalizados y programación asíncrona con asyncio.",
                    "criteria": [
                        {"name": "Concurrencia Asíncrona (async/await)", "weight": 50, "description": "Uso correcto de event loop, tasks y context managers."},
                        {"name": "Metaprogramación y Decoradores", "weight": 50, "description": "Implementación de wrappers con functools.wraps y validaciones."},
                    ],
                },
                5: {
                    "instructions": "Arquitectura limpia de software, APIs REST asíncronas con FastAPI y diseño de librerías mantenibles.",
                    "criteria": [
                        {"name": "Arquitectura y Patrones de Diseño", "weight": 60, "description": "Inversión de dependencias, repositorios y desacoplamiento estructural."},
                        {"name": "Optimización y Profiling", "weight": 40, "description": "Gestión de memoria, análisis de árbol sintáctico y testing exhaustivo."},
                    ],
                },
            },
        },
    ]

    for sk in initial_skills:
        res = await db.execute(select(Skill).where(Skill.slug == sk["slug"]))
        existing_skill = res.scalar_one_or_none()
        category = cat_map.get(sk["cat_slug"])
        challenge_type = ct_map.get(sk["ct_code"])

        if not category:
            continue

        if not existing_skill:
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
            target_skill = new_skill
            logger.info(f"Habilidad canónica creada: {new_skill.name}")
        else:
            target_skill = existing_skill
            target_skill.name = sk["name"]
            target_skill.category_id = category.id
            if challenge_type:
                target_skill.challenge_type_id = challenge_type.id
            target_skill.description = sk["desc"]
            target_skill.is_ready_to_publish = True
            target_skill.is_active = True
            await db.flush()

        # Asegurar escalera canónica de 5 niveles y rúbricas
        custom_rubrics = sk.get("rubrics", {})
        for lvl_num, lvl_name in CANONICAL_LEVELS.items():
            lvl_res = await db.execute(
                select(SkillLevel).where(
                    SkillLevel.skill_id == target_skill.id,
                    SkillLevel.level_number == lvl_num,
                )
            )
            skill_level = lvl_res.scalar_one_or_none()
            if not skill_level:
                skill_level = SkillLevel(
                    skill_id=target_skill.id,
                    level_number=lvl_num,
                    name=lvl_name,
                    description=f"Nivel {lvl_num}: {lvl_name}",
                )
                db.add(skill_level)
                await db.flush()

            # Rúbrica asociada
            rubric_res = await db.execute(
                select(Rubric).where(Rubric.skill_level_id == skill_level.id)
            )
            rubric = rubric_res.scalar_one_or_none()
            rubric_data = custom_rubrics.get(lvl_num)

            default_criteria = [
                {"name": "Precisión y Ejecución Técnica", "weight": 50, "description": "Solvencia y exactitud del gesto técnico."},
                {"name": "Fundamentos Teóricos", "weight": 50, "description": "Comprensión conceptual de los principios evaluados."},
            ]

            instructions = (
                rubric_data["instructions"]
                if rubric_data
                else f"Evaluación práctica y teórica para {target_skill.name} Nivel {lvl_num}."
            )
            criteria = rubric_data["criteria"] if rubric_data else default_criteria

            if not rubric:
                rubric = Rubric(
                    skill_level_id=skill_level.id,
                    instructions=instructions,
                    min_score=70.0,
                    criteria=criteria,
                )
                db.add(rubric)
            else:
                rubric.instructions = instructions
                rubric.criteria = criteria
                rubric.min_score = 70.0

    await db.commit()
    logger.info("Aprovisionamiento de catálogo canónico finalizado con éxito.")


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
        provider="institutional",
    )

    db.add(admin_user)
    try:
        await db.commit()
        logger.info(f"Administrador inicial provisionado exitosamente desde variables de entorno: {email}")
    except Exception as exc:
        await db.rollback()
        logger.error(f"Error al provisionar el administrador inicial: {exc}")
        raise


async def main() -> None:
    """Ejecutor independiente del seeder de base de datos."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        logger.info("Iniciando seed de catálogo y administrador...")
        await ensure_initial_admin(session)
        await ensure_initial_catalog(session)
        logger.info("Seed ejecutado exitosamente.")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
