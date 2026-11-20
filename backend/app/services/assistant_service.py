import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.catalog import Category, Skill, SkillLevel, Rubric
from app.schemas.catalog import CANONICAL_LEVELS
from app.models.exchange_session import ExchangeSession
from app.models.teaching_skill import TeachingSkill
from app.models.user_learning_skill import UserLearningSkill, UrgencyLevel
from app.models.user import User
from app.schemas.assistant import ChatActionPayload, ChatHistoryItem, ChatMessageResponse
from app.services.wallet_service import wallet_service

logger = logging.getLogger("skillmatch.assistant")

SYSTEM_INSTRUCTION = """Eres el Asistente Virtual y Copiloto Inteligente de SkillMatch, la plataforma de intercambio de habilidades con economía de SkillPoints (SP) y validación de conocimientos por IA.

Tu misión es asistir al usuario de forma clara, empática, concisa y ejecutiva:
1. **Perfil y Billetera**: Informar sobre su saldo de SkillPoints (disponible, en custodia/escrow y equivalente en USD) y estado KYC.
   - Recordatorio: 10 SP = $1.00 USD. Retiro mínimo de 100 SP ($10 USD). Comisión de retiro: 15%.
2. **Sesiones y Calendario**: Consultar sus próximas clases de intercambio agendadas y recordarle las políticas de puntualidad y cancelación (mínimo 2 horas antes para evitar penalizaciones).
3. **Búsqueda de Mentores y Habilidades**: Recomendar tutores activos según el tema que el usuario desee aprender.
4. **Creación y Publicación de Habilidades (Capacidad de Acción Inteligente)**:
   - Si el usuario te pide crear, agregar, publicar u ofrecer una habilidad para enseñar (ej. "quiero enseñar Python", "crea mi habilidad de ajedrez", "agrega que enseño piano"), DEBES invocar la herramienta `create_my_teaching_skill` extrayendo el nombre, nivel (BEGINNER, INTERMEDIATE, ADVANCED, EXPERT), años de experiencia y tarifa en puntos.
   - Si el usuario te pide registrar una habilidad que desea aprender (ej. "quiero aprender a tocar flauta", "agrega que quiero aprender dominadas"), DEBES invocar la herramienta `create_my_learning_skill`.
5. **Reglas de la Comunidad y Disputas**:
   - Escrow: Al reservar con puntos, los SP quedan protegidos en custodia hasta que ambas partes confirmen la sesión.
   - KYC: Se requiere foto de documento y verificación facial biométrica para retiros y emisión de certificados.
   - Arbitraje: En caso de ausencia o incumplimiento del tutor, se puede abrir una disputa con evidencia.

REGLAS DE FORMATO Y TONO:
- Responde SIEMPRE en español en Markdown limpio y legible (usando negritas y listas breves).
- Sé directo y confirma claramente cuando hayas creado o actualizado una habilidad en su perfil.
- Cuando utilices una herramienta para obtener datos o crear habilidades, resume la confirmación amigablemente.
"""

GEMINI_TOOLS = [
    {
        "functionDeclarations": [
            {
                "name": "get_my_profile_summary",
                "description": "Obtiene el resumen del perfil del usuario autenticado: nombre, balance de SkillPoints (disponible, escrow, total, USD), reputación y estado de verificación de identidad KYC.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {},
                },
            },
            {
                "name": "get_my_upcoming_sessions",
                "description": "Obtiene las sesiones de intercambio agendadas o pendientes del usuario (como aprendiz o como instructor), con fechas, modalidad y estado.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {},
                },
            },
            {
                "name": "search_instructors_and_skills",
                "description": "Busca tutores e instructores en la plataforma según una habilidad o palabra clave (ej. 'programacion', 'python', 'guitarra', 'ingles').",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "query": {
                            "type": "STRING",
                            "description": "Nombre de la habilidad o tema que el usuario desea aprender.",
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "get_platform_help_and_rules",
                "description": "Consulta las reglas oficiales, políticas de economía, sistema Escrow, comisiones de retiro, cancelaciones y verificación KYC de SkillMatch.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "topic": {
                            "type": "STRING",
                            "description": "Tema a consultar: 'escrow', 'billetera', 'cancelacion', 'kyc', 'evaluaciones', 'general'.",
                        },
                    },
                    "required": ["topic"],
                },
            },
            {
                "name": "create_my_teaching_skill",
                "description": "Crea, registra o publica una habilidad que el usuario autenticado ofrece enseñar en la plataforma como instructor. Extrae el nombre de la habilidad, nivel de dominio, años de experiencia y tarifa por hora.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "skill_name": {
                            "type": "STRING",
                            "description": "Nombre de la habilidad a enseñar (ej. 'Programación en Python', 'Tocar flauta', 'Dominadas con el balón', 'Ajedrez').",
                        },
                        "declared_level": {
                            "type": "STRING",
                            "description": "Nivel declarado: 'BEGINNER', 'INTERMEDIATE', 'ADVANCED' o 'EXPERT' (por defecto 'INTERMEDIATE').",
                        },
                        "years_of_experience": {
                            "type": "INTEGER",
                            "description": "Años de experiencia práctica (por defecto 2).",
                        },
                        "accepts_points": {
                            "type": "BOOLEAN",
                            "description": "Si acepta SkillPoints por hora (por defecto true).",
                        },
                        "hourly_points_rate": {
                            "type": "INTEGER",
                            "description": "Tarifa por hora en SkillPoints (por defecto 20).",
                        },
                        "description": {
                            "type": "STRING",
                            "description": "Breve descripción de su experiencia o propuesta pedagógica.",
                        },
                    },
                    "required": ["skill_name"],
                },
            },
            {
                "name": "create_my_learning_skill",
                "description": "Registra una habilidad o tema que el usuario desea aprender como aprendiz (demanda formativa).",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "skill_name": {
                            "type": "STRING",
                            "description": "Nombre de la habilidad que desea aprender.",
                        },
                        "current_level": {
                            "type": "INTEGER",
                            "description": "Nivel de partida del usuario del 1 al 5 (por defecto 1).",
                        },
                        "target_level": {
                            "type": "INTEGER",
                            "description": "Nivel objetivo deseado del 1 al 5 (por defecto 3).",
                        },
                        "urgency": {
                            "type": "STRING",
                            "description": "Nivel de urgencia: 'LOW', 'MEDIUM' o 'HIGH'.",
                        },
                        "notes": {
                            "type": "STRING",
                            "description": "Motivación o notas personales de aprendizaje.",
                        },
                    },
                    "required": ["skill_name"],
                },
            },
        ],
    }
]


class AssistantService:
    def __init__(self) -> None:
        # Memoria conversacional en proceso por usuario: user_id -> List[Dict[str, Any]]
        self._conversations: dict[str, list[dict[str, Any]]] = {}
        # Historial formateado para el frontend: user_id -> List[ChatHistoryItem]
        self._history_items: dict[str, list[ChatHistoryItem]] = {}

    def get_history(self, user_id: str) -> list[ChatHistoryItem]:
        """Retorna el historial de mensajes de la sesión del usuario."""
        return self._history_items.get(user_id, [])

    def clear_history(self, user_id: str) -> None:
        """Limpia el historial de la conversación del usuario."""
        self._conversations.pop(user_id, None)
        self._history_items.pop(user_id, None)

    async def execute_tool(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        db: AsyncSession,
        user: User,
    ) -> dict[str, Any]:
        """Ejecuta una herramienta de dominio y devuelve el resultado para Gemini."""
        if tool_name == "get_my_profile_summary":
            return await self._tool_get_profile_summary(db, user)
        elif tool_name == "get_my_upcoming_sessions":
            return await self._tool_get_upcoming_sessions(db, user)
        elif tool_name == "search_instructors_and_skills":
            query = tool_args.get("query", "")
            return await self._tool_search_instructors(db, query)
        elif tool_name == "get_platform_help_and_rules":
            topic = tool_args.get("topic", "general")
            return self._tool_get_platform_faq(topic)
        elif tool_name == "create_my_teaching_skill":
            return await self._tool_create_teaching_skill(
                db,
                user,
                skill_name=tool_args.get("skill_name", ""),
                declared_level=tool_args.get("declared_level", "INTERMEDIATE"),
                years_of_experience=tool_args.get("years_of_experience", 2),
                accepts_points=tool_args.get("accepts_points", True),
                hourly_points_rate=tool_args.get("hourly_points_rate", 20),
                description=tool_args.get("description", ""),
            )
        elif tool_name == "create_my_learning_skill":
            return await self._tool_create_learning_skill(
                db,
                user,
                skill_name=tool_args.get("skill_name", ""),
                current_level=tool_args.get("current_level", 1),
                target_level=tool_args.get("target_level", 3),
                urgency=tool_args.get("urgency", "MEDIUM"),
                notes=tool_args.get("notes", ""),
            )
        else:
            return {"error": f"Herramienta desconocida: {tool_name}"}

    async def _tool_get_profile_summary(self, db: AsyncSession, user: User) -> dict[str, Any]:
        wallet = await wallet_service.get_or_create_wallet(db, user.id)
        points_per_usd = settings.WALLET_POINTS_PER_USD or 10
        total_points = wallet.balance + wallet.escrow_balance
        usd_val = round(total_points / points_per_usd, 2)

        is_verified = getattr(user, "identity_status", "UNVERIFIED") == "VERIFIED"
        role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
        return {
            "user_id": str(user.id),
            "full_name": user.full_name,
            "role": role_val,
            "is_verified_kyc": is_verified,
            "reputation_score": getattr(user, "reputation_score", 5.0),
            "wallet": {
                "available_points": wallet.balance,
                "escrow_points": wallet.escrow_balance,
                "total_points": total_points,
                "usd_equivalent": usd_val,
                "points_per_usd": points_per_usd,
            },
        }

    async def _tool_get_upcoming_sessions(self, db: AsyncSession, user: User) -> dict[str, Any]:
        stmt = (
            select(ExchangeSession)
            .where(
                or_(
                    ExchangeSession.instructor_id == user.id,
                    ExchangeSession.learner_id == user.id,
                ),
                ExchangeSession.status.in_(["PENDING", "ACCEPTED"]),
            )
            .order_by(ExchangeSession.starts_at.asc())
            .limit(5)
        )
        result = await db.scalars(stmt)
        sessions = result.all()

        session_list = []
        for s in sessions:
            is_instructor = s.instructor_id == user.id
            counterpart_id = s.learner_id if is_instructor else s.instructor_id
            counterpart = await db.get(User, counterpart_id)
            session_list.append({
                "session_id": str(s.id),
                "role_in_session": "Instructor" if is_instructor else "Aprendiz",
                "counterpart_name": counterpart.full_name if counterpart else "Compañero SkillMatch",
                "starts_at": s.starts_at.isoformat(),
                "ends_at": s.ends_at.isoformat(),
                "modality": s.modality,
                "status": s.status,
                "points_required": s.points_required or 0,
            })

        return {"count": len(session_list), "sessions": session_list}

    async def _tool_search_instructors(self, db: AsyncSession, query: str) -> dict[str, Any]:
        search_term = f"%{query.strip()}%"
        stmt = (
            select(TeachingSkill, Skill, User)
            .join(Skill, TeachingSkill.skill_id == Skill.id)
            .join(User, TeachingSkill.user_id == User.id)
            .where(
                or_(
                    Skill.name.ilike(search_term),
                    TeachingSkill.description.ilike(search_term),
                ),
                User.is_active == True,
            )
            .limit(5)
        )
        result = await db.execute(stmt)
        rows = result.all()

        instructors = []
        for ts, skill, tutor in rows:
            instructors.append({
                "instructor_id": str(tutor.id),
                "instructor_name": tutor.full_name,
                "skill_name": skill.name,
                "level": ts.declared_level,
                "experience_years": ts.years_of_experience,
                "accepts_points": ts.accepts_points,
                "hourly_rate_sp": ts.hourly_points_rate if ts.accepts_points else None,
                "reputation": getattr(tutor, "reputation_score", 5.0),
            })

        return {"query": query, "found": len(instructors), "instructors": instructors}

    def _tool_get_platform_faq(self, topic: str) -> dict[str, Any]:
        t = topic.lower()
        if "escrow" in t or "custodia" in t:
            return {
                "topic": "Sistema Escrow",
                "explanation": (
                    "El sistema Escrow protege tus SkillPoints. Cuando agendas una sesión con puntos, "
                    "los SP se retienen en una cuenta segura y no se transfieren al instructor hasta que "
                    "la sesión concluya con éxito y sea confirmada."
                ),
            }
        elif "puntos" in t or "wallet" in t or "billetera" in t or "retiro" in t:
            return {
                "topic": "Economía y Billetera",
                "rules": [
                    "Conversión estándar: 10 SkillPoints (SP) = $1.00 USD.",
                    "Retiro mínimo: 100 SP ($10.00 USD) hacia tu cuenta bancaria o PayPal.",
                    "Comisión institucional: 15% sobre los retiros de saldo para mantenimiento de la plataforma.",
                    "Recargas: Puedes comprar paquetes de SP con tarjeta o pasarela de pagos.",
                ],
            }
        elif "cancel" in t:
            return {
                "topic": "Política de Cancelación",
                "explanation": (
                    "Puedes cancelar una sesión programada con al menos 2 horas de anticipación sin penalización. "
                    "Si cancelas con menos de 2 horas o no te presentas, se aplicará una deducción de reputación "
                    "y los puntos en custodia se gestionarán según la política de inasistencia."
                ),
            }
        elif "kyc" in t or "verif" in t:
            return {
                "topic": "Verificación KYC",
                "explanation": (
                    "Para garantizar la seguridad de la comunidad, la verificación de identidad (KYC) "
                    "requiere una fotografía de tu documento de identidad y una selfie biométrica con detección "
                    "de vida. Es obligatoria para solicitar retiros de fondos y certificar habilidades oficiales."
                ),
            }
        else:
            return {
                "topic": "Acerca de SkillMatch",
                "explanation": (
                    "SkillMatch es la plataforma colaborativa líder para intercambiar habilidades, conectar con tutores "
                    "validados por IA y aprender a tu propio ritmo con economía de puntos y sesiones personalizadas."
                ),
            }

    async def _tool_create_teaching_skill(
        self,
        db: AsyncSession,
        user: User,
        skill_name: str,
        declared_level: str = "INTERMEDIATE",
        years_of_experience: int = 2,
        accepts_points: bool = True,
        hourly_points_rate: int = 20,
        description: str = "",
    ) -> dict[str, Any]:
        level_clean = declared_level.upper().strip() if declared_level else "INTERMEDIATE"
        if level_clean not in ["BEGINNER", "INTERMEDIATE", "ADVANCED", "EXPERT"]:
            level_clean = "INTERMEDIATE"

        years = max(0, min(50, int(years_of_experience or 2)))
        rate = max(1, min(500, int(hourly_points_rate or 20))) if accepts_points else None

        clean_name = " ".join(skill_name.strip().split())
        if not clean_name:
            clean_name = "Habilidad General"

        # 1. Buscar o crear la habilidad en el catálogo
        skill_stmt = select(Skill).where(
            or_(
                Skill.name.ilike(f"%{clean_name}%"),
                Skill.slug == clean_name.lower().replace(" ", "-"),
            )
        )
        res = await db.execute(skill_stmt)
        skill = res.scalar_one_or_none()

        if not skill:
            cat_stmt = select(Category).where(Category.is_active.is_(True)).order_by(Category.created_at.asc())
            cats = (await db.scalars(cat_stmt)).all()
            category = None
            name_lower = clean_name.lower()
            for c in cats:
                if c.slug in name_lower or c.name.lower() in name_lower:
                    category = c
                    break
            if not category and cats:
                category = cats[0]

            if not category:
                category = Category(
                    name="General",
                    slug="general",
                    description="Habilidades generales de la comunidad",
                    is_active=True,
                )
                db.add(category)
                await db.flush()

            clean_slug = clean_name.lower().replace(" ", "-")
            slug_cand = clean_slug
            idx = 2
            while await db.scalar(select(Skill).where(Skill.slug == slug_cand)):
                slug_cand = f"{clean_slug}-{idx}"
                idx += 1

            skill = Skill(
                category_id=category.id,
                name=clean_name.title(),
                slug=slug_cand,
                description=description or f"Enseñanza y mentoría en {clean_name.title()}.",
                min_approval_threshold=80.0,
                is_ready_to_publish=True,
                is_active=True,
            )
            db.add(skill)
            await db.flush()

            for lvl_num, lvl_name in CANONICAL_LEVELS.items():
                sl = SkillLevel(
                    skill_id=skill.id,
                    level_number=lvl_num,
                    name=lvl_name,
                    description=f"Nivel {lvl_num}: {lvl_name}",
                )
                db.add(sl)
                await db.flush()
                db.add(
                    Rubric(
                        skill_level_id=sl.id,
                        instructions=f"Evaluación práctica y teórica para {skill.name} Nivel {lvl_num}.",
                        min_score=70.0,
                        criteria=[
                            {"name": "Precisión y Ejecución Técnica", "weight": 50, "description": "Solvencia técnica."},
                            {"name": "Fundamentos Teóricos", "weight": 50, "description": "Comprensión conceptual."},
                        ],
                    )
                )
            await db.flush()

        # 2. Crear o actualizar TeachingSkill del usuario
        ts_stmt = select(TeachingSkill).where(
            TeachingSkill.user_id == user.id,
            TeachingSkill.skill_id == skill.id,
        )
        ts = (await db.execute(ts_stmt)).scalar_one_or_none()
        action_verb = "actualizada" if ts else "creada"

        if ts:
            ts.declared_level = level_clean
            ts.years_of_experience = years
            ts.accepts_points = accepts_points
            ts.hourly_points_rate = rate
            if description:
                ts.description = description
            ts.status = "VERIFICADA"
        else:
            ts = TeachingSkill(
                user_id=user.id,
                skill_id=skill.id,
                declared_level=level_clean,
                years_of_experience=years,
                description=description or f"Instructor de {skill.name}. Clases personalizadas paso a paso.",
                accepts_points=accepts_points,
                hourly_points_rate=rate,
                status="VERIFICADA",
            )
            db.add(ts)

        await db.commit()

        return {
            "success": True,
            "action": action_verb,
            "skill_id": str(skill.id),
            "skill_name": skill.name,
            "level": level_clean,
            "experience_years": years,
            "accepts_points": accepts_points,
            "hourly_points_rate": rate or 0,
            "description": ts.description,
            "message": f"¡Habilidad '{skill.name}' {action_verb} exitosamente en tu perfil!",
        }

    async def _tool_create_learning_skill(
        self,
        db: AsyncSession,
        user: User,
        skill_name: str,
        current_level: int = 1,
        target_level: int = 3,
        urgency: str = "MEDIUM",
        notes: str = "",
    ) -> dict[str, Any]:
        curr = max(1, min(5, int(current_level or 1)))
        targ = max(curr, min(5, int(target_level or 3)))
        urg = urgency.upper().strip() if urgency else "MEDIUM"
        if urg not in ["LOW", "MEDIUM", "HIGH"]:
            urg = "MEDIUM"

        clean_name = " ".join(skill_name.strip().split())
        if not clean_name:
            clean_name = "Habilidad de Interés"

        skill_stmt = select(Skill).where(
            or_(
                Skill.name.ilike(f"%{clean_name}%"),
                Skill.slug == clean_name.lower().replace(" ", "-"),
            )
        )
        skill = (await db.execute(skill_stmt)).scalar_one_or_none()
        if not skill:
            cat = (await db.scalars(select(Category).where(Category.is_active.is_(True)).limit(1))).first()
            if not cat:
                cat = Category(name="General", slug="general", is_active=True)
                db.add(cat)
                await db.flush()

            clean_slug = clean_name.lower().replace(" ", "-")
            skill = Skill(
                category_id=cat.id,
                name=clean_name.title(),
                slug=clean_slug,
                description=f"Habilidad {clean_name.title()}",
                is_ready_to_publish=True,
                is_active=True,
            )
            db.add(skill)
            await db.flush()

        ls_stmt = select(UserLearningSkill).where(
            UserLearningSkill.user_id == user.id,
            UserLearningSkill.skill_id == skill.id,
        )
        ls = (await db.execute(ls_stmt)).scalar_one_or_none()
        action_verb = "actualizado" if ls else "registrado"

        if ls:
            ls.current_level = curr
            ls.target_level = targ
            ls.urgency = UrgencyLevel(urg)
            if notes:
                ls.notes = notes
        else:
            ls = UserLearningSkill(
                user_id=user.id,
                skill_id=skill.id,
                current_level=curr,
                target_level=targ,
                urgency=UrgencyLevel(urg),
                notes=notes or f"Interés de aprendizaje en {skill.name}.",
            )
            db.add(ls)

        await db.commit()

        return {
            "success": True,
            "action": action_verb,
            "skill_id": str(skill.id),
            "skill_name": skill.name,
            "current_level": curr,
            "target_level": targ,
            "urgency": urg,
            "notes": ls.notes,
            "message": f"¡Interés de aprendizaje para '{skill.name}' {action_verb} exitosamente!",
        }

    async def send_message(
        self,
        db: AsyncSession,
        user: User,
        user_message: str,
    ) -> ChatMessageResponse:
        """Procesa un mensaje del usuario llamando a Gemini con soporte de Tool Calling."""
        user_key = str(user.id)
        if user_key not in self._conversations:
            self._conversations[user_key] = []
        if user_key not in self._history_items:
            self._history_items[user_key] = []

        history = self._conversations[user_key]

        # Agregar mensaje del usuario a la memoria
        user_part = {"role": "user", "parts": [{"text": user_message}]}
        history.append(user_part)

        # Registrar en items del frontend
        user_item_id = str(uuid4())
        self._history_items[user_key].append(
            ChatHistoryItem(
                id=user_item_id,
                role="user",
                content=user_message,
                timestamp=datetime.now(UTC),
            )
        )

        # Preparar llamada a Gemini
        api_key_secret = settings.GEMINI_API_KEY
        api_key = api_key_secret.get_secret_value() if api_key_secret else None
        model_name = settings.ASSISTANT_GEMINI_MODEL or "gemini-3.1-flash-lite"

        action_payload: ChatActionPayload | None = None
        suggested_prompts: list[str] = [
            "Quiero enseñar Programación en Python",
            "Quiero aprender Dominadas con el balón",
            "¿Cuál es mi saldo actual?",
            "¿Cuándo es mi próxima sesión?",
        ]

        if not api_key:
            # Fallback inteligente local si no hay clave configurada
            reply_text, action_payload = await self._generate_offline_reply(db, user, user_message)
        else:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            try:
                # Mantener solo las últimas 10 interacciones para no saturar el contexto
                trimmed_history = history[-10:]

                payload = {
                    "systemInstruction": {
                        "parts": [{"text": SYSTEM_INSTRUCTION}],
                    },
                    "contents": trimmed_history,
                    "tools": GEMINI_TOOLS,
                }

                transport = httpx.AsyncHTTPTransport(local_address="0.0.0.0")
                async with httpx.AsyncClient(transport=transport, timeout=25.0) as client:
                    resp = await client.post(url, json=payload)

                if resp.status_code != 200:
                    logger.warning(
                        f"Gemini API returned status {resp.status_code}: {resp.text}"
                    )
                    reply_text, action_payload = await self._generate_offline_reply(db, user, user_message)
                else:
                    data = resp.json()
                    candidate = data.get("candidates", [{}])[0]
                    content = candidate.get("content", {})
                    parts = content.get("parts", [])

                    # Verificar si el modelo solicitó una llamada a función (tool call)
                    function_call = None
                    for p in parts:
                        if "functionCall" in p:
                            function_call = p["functionCall"]
                            break

                    if function_call:
                        tool_name = function_call.get("name", "")
                        tool_args = function_call.get("args", {})
                        logger.info(f"Gemini solicitó tool: {tool_name} con args: {tool_args}")

                        # Ejecutar la tool localmente
                        tool_result = await self.execute_tool(tool_name, tool_args, db, user)

                        # Crear action_payload para el frontend según la herramienta invocada
                        action_payload = self._create_action_for_tool(tool_name, tool_result)

                        # Enviar respuesta de la tool de vuelta a Gemini para respuesta final en lenguaje natural
                        history.append(content)  # Preserva thoughtSignature del modelo
                        tool_response_part = {
                            "role": "user",
                            "parts": [
                                {
                                    "functionResponse": {
                                        "name": tool_name,
                                        "response": tool_result,
                                    }
                                }
                            ],
                        }
                        history.append(tool_response_part)

                        payload2 = {
                            "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
                            "contents": history[-10:],
                            "tools": GEMINI_TOOLS,
                        }

                        transport2 = httpx.AsyncHTTPTransport(local_address="0.0.0.0")
                        async with httpx.AsyncClient(transport=transport2, timeout=25.0) as client2:
                            resp2 = await client2.post(url, json=payload2)

                        if resp2.status_code == 200:
                            data2 = resp2.json()
                            parts2 = data2.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                            reply_text = "".join(p.get("text", "") for p in parts2 if "text" in p)
                        else:
                            reply_text = self._format_tool_direct_summary(tool_name, tool_result)
                    else:
                        reply_text = "".join(p.get("text", "") for p in parts if "text" in p)
                        if not reply_text:
                            reply_text = "Disculpa, ¿podrías reformular tu consulta sobre SkillMatch?"

            except Exception as exc:  # noqa: BLE001
                logger.error(f"Error comunicando con Gemini API: {exc}")
                reply_text, action_payload = await self._generate_offline_reply(db, user, user_message)

        # Agregar respuesta del asistente a la memoria
        history.append({"role": "model", "parts": [{"text": reply_text}]})

        assistant_item_id = str(uuid4())
        self._history_items[user_key].append(
            ChatHistoryItem(
                id=assistant_item_id,
                role="assistant",
                content=reply_text,
                timestamp=datetime.now(UTC),
                action=action_payload,
            )
        )

        return ChatMessageResponse(
            reply=reply_text,
            action=action_payload,
            suggested_prompts=suggested_prompts,
        )

    def _create_action_for_tool(self, tool_name: str, tool_result: dict[str, Any]) -> ChatActionPayload | None:
        """Convierte los datos de la tool en un componente interactivo para el frontend."""
        if tool_name == "get_my_profile_summary":
            wallet = tool_result.get("wallet", {})
            return ChatActionPayload(
                type="wallet_topup",
                data={
                    "available_points": wallet.get("available_points", 0),
                    "usd_equivalent": wallet.get("usd_equivalent", 0.0),
                    "is_verified": tool_result.get("is_verified_kyc", False),
                },
            )
        elif tool_name == "search_instructors_and_skills":
            instructors = tool_result.get("instructors", [])
            if instructors:
                return ChatActionPayload(
                    type="instructor_card",
                    data={"instructors": instructors[:3]},
                )
        elif tool_name == "get_my_upcoming_sessions":
            sessions = tool_result.get("sessions", [])
            if sessions:
                return ChatActionPayload(
                    type="sessions_list",
                    data={"sessions": sessions},
                )
        elif tool_name == "create_my_teaching_skill":
            return ChatActionPayload(
                type="skill_created",
                data=tool_result,
            )
        elif tool_name == "create_my_learning_skill":
            return ChatActionPayload(
                type="learning_skill_created",
                data=tool_result,
            )
        elif tool_name == "get_platform_help_and_rules":
            return ChatActionPayload(
                type="faq_info",
                data=tool_result,
            )
        return None

    def _format_tool_direct_summary(self, tool_name: str, data: dict[str, Any]) -> str:
        """Formatea los resultados de una herramienta cuando Gemini no completa la segunda vuelta."""
        if tool_name == "get_my_profile_summary":
            w = data.get("wallet", {})
            return (
                f"**Resumen de tu cuenta:**\n"
                f"- **Saldo disponible:** {w.get('available_points', 0)} SP (${w.get('usd_equivalent', 0.0)} USD)\n"
                f"- **Puntos en custodia Escrow:** {w.get('escrow_points', 0)} SP\n"
                f"- **Verificación KYC:** {'Completada ✅' if data.get('is_verified_kyc') else 'Pendiente ⏳'}\n"
            )
        elif tool_name == "get_my_upcoming_sessions":
            sessions = data.get("sessions", [])
            if not sessions:
                return "No tienes sesiones agendadas pendientes en este momento. ¡Anímate a buscar una habilidad y agendar tu primera clase!"
            lines = ["**Tus próximas sesiones:**"]
            for s in sessions:
                lines.append(f"- **{s.get('counterpart_name')}** ({s.get('role_in_session')}) - Modalidad {s.get('modality')}, Estado: {s.get('status')}")
            return "\n".join(lines)
        elif tool_name == "search_instructors_and_skills":
            inst = data.get("instructors", [])
            if not inst:
                return f"No encontré tutores activos con el término '{data.get('query')}'. Prueba buscando 'Programación', 'Inglés' o 'Música'."
            lines = [f"**Tutores encontrados para '{data.get('query')}':**"]
            for t in inst:
                rate = f"{t.get('hourly_rate_sp')} SP/h" if t.get('accepts_points') else "Solo intercambio"
                lines.append(f"- **{t.get('instructor_name')}** ({t.get('level')}): {rate}")
            return "\n".join(lines)
        elif tool_name == "create_my_teaching_skill":
            rate_txt = f"{data.get('hourly_points_rate')} SP/h" if data.get('accepts_points') else "Solo intercambio"
            return (
                f"✅ **¡Habilidad de enseñanza registrada con éxito!**\n\n"
                f"- **Habilidad:** {data.get('skill_name')}\n"
                f"- **Nivel:** {data.get('level')}\n"
                f"- **Experiencia:** {data.get('experience_years')} años\n"
                f"- **Tarifa:** {rate_txt}\n"
                f"- **Estado:** Verificada y activa en tu perfil.\n\n"
                f"¡Excelente! Otros miembros de la comunidad ya pueden encontrarte en la búsqueda y enviarte solicitudes de intercambio."
            )
        elif tool_name == "create_my_learning_skill":
            return (
                f"🎯 **¡Interés de aprendizaje registrado con éxito!**\n\n"
                f"- **Habilidad:** {data.get('skill_name')}\n"
                f"- **Nivel actual:** Nivel {data.get('current_level')}\n"
                f"- **Nivel objetivo:** Nivel {data.get('target_level')}\n"
                f"- **Urgencia:** {data.get('urgency')}\n\n"
                f"¡Listo! Nuestro sistema de emparejamiento te recomendará los instructores más afines y las opciones de intercambio recíproco."
            )
        return "Aquí tienes la información solicitada."

    async def _generate_offline_reply(
        self, db: AsyncSession, user: User, msg: str
    ) -> tuple[str, ChatActionPayload | None]:
        """Generador heurístico seguro cuando la API externa no está disponible temporalmente."""
        low = msg.lower()
        import re

        # Detección de creación de habilidad para enseñar
        if any(w in low for w in ["enseñar", "ofrezco enseñar", "crea mi habilidad", "crear mi habilidad", "agregar habilidad", "agrega habilidad"]):
            level = "INTERMEDIATE"
            if "principiante" in low or "beginner" in low or "básico" in low or "basico" in low:
                level = "BEGINNER"
            elif "avanzado" in low or "advanced" in low:
                level = "ADVANCED"
            elif "experto" in low or "expert" in low:
                level = "EXPERT"

            rate = 20
            rate_match = re.search(r"(\d+)\s*(sp|puntos|pts)", low)
            if rate_match:
                rate = int(rate_match.group(1))

            years = 2
            years_match = re.search(r"(\d+)\s*(años|anos|año|ano)", low)
            if years_match:
                years = int(years_match.group(1))

            skill_name = "Programación en Python"
            if "python" in low:
                skill_name = "Programación en Python"
            elif "flauta" in low:
                skill_name = "Tocar flauta"
            elif "dominada" in low or "balon" in low or "balón" in low or "futbol" in low or "fútbol" in low:
                skill_name = "Dominadas con el balón"
            elif "guitarra" in low:
                skill_name = "Guitarra acústica"
            elif "ajedrez" in low:
                skill_name = "Ajedrez estratégico"
            else:
                m = re.search(r"(?:enseñar|habilidad de|habilidad)\s+([^,.\n]+)", msg, re.IGNORECASE)
                if m:
                    cand = m.group(1).strip()
                    for stop_word in ["nivel", "cobrando", "por", "con", "de"]:
                        if f" {stop_word} " in f" {cand.lower()} ":
                            cand = cand.lower().split(f" {stop_word} ")[0].strip()
                    if cand:
                        skill_name = cand.title()

            res = await self._tool_create_teaching_skill(
                db,
                user,
                skill_name=skill_name,
                declared_level=level,
                years_of_experience=years,
                accepts_points=True,
                hourly_points_rate=rate,
                description=f"Clases de {skill_name} personalizadas.",
            )
            return (
                self._format_tool_direct_summary("create_my_teaching_skill", res),
                self._create_action_for_tool("create_my_teaching_skill", res),
            )

        # Detección de interés de aprendizaje
        if any(w in low for w in ["aprender", "deseo aprender", "quiero aprender", "interes en aprender", "interés en aprender"]):
            skill_name = "Dominadas con el balón"
            if "python" in low or "programar" in low or "programacion" in low or "programación" in low:
                skill_name = "Programación en Python"
            elif "flauta" in low:
                skill_name = "Tocar flauta"
            elif "dominada" in low or "balon" in low or "balón" in low or "futbol" in low or "fútbol" in low:
                skill_name = "Dominadas con el balón"
            elif "guitarra" in low:
                skill_name = "Guitarra acústica"
            elif "ajedrez" in low:
                skill_name = "Ajedrez estratégico"
            else:
                m = re.search(r"(?:aprender a|aprender)\s+([^,.\n]+)", msg, re.IGNORECASE)
                if m:
                    cand = m.group(1).strip()
                    for stop_word in ["desde", "nivel", "urgente", "con", "en"]:
                        if f" {stop_word} " in f" {cand.lower()} ":
                            cand = cand.lower().split(f" {stop_word} ")[0].strip()
                    if cand:
                        skill_name = cand.title()

            res = await self._tool_create_learning_skill(
                db,
                user,
                skill_name=skill_name,
                current_level=1,
                target_level=3,
                urgency="HIGH" if ("urgente" in low or "rapido" in low) else "MEDIUM",
                notes=f"Interés de aprendizaje en {skill_name}.",
            )
            return (
                self._format_tool_direct_summary("create_my_learning_skill", res),
                self._create_action_for_tool("create_my_learning_skill", res),
            )

        # Saldo y billetera
        if any(w in low for w in ["saldo", "puntos", "cuanto tengo", "cuánto tengo", "billetera", "sp"]):
            res = await self._tool_get_profile_summary(db, user)
            return (
                self._format_tool_direct_summary("get_my_profile_summary", res),
                self._create_action_for_tool("get_my_profile_summary", res),
            )

        # Sesiones agendadas
        if any(w in low for w in ["sesion", "sesiones", "sesión", "clase", "agenda", "horario"]):
            res = await self._tool_get_upcoming_sessions(db, user)
            return (
                self._format_tool_direct_summary("get_my_upcoming_sessions", res),
                self._create_action_for_tool("get_my_upcoming_sessions", res),
            )

        # Buscar tutores
        if any(w in low for w in ["tutor", "tutores", "profesor", "instructor", "buscar", "encontrar"]):
            topic = "Programación"
            for t in ["python", "musica", "música", "flauta", "futbol", "fútbol", "dominadas"]:
                if t in low:
                    topic = t
                    break
            res = await self._tool_search_instructors(db, topic=topic)
            return (
                self._format_tool_direct_summary("search_instructors_and_skills", res),
                self._create_action_for_tool("search_instructors_and_skills", res),
            )

        # Escrow y reglas
        if any(w in low for w in ["escrow", "custodia"]):
            text = (
                "🛡️ **Sistema Escrow en SkillMatch:**\n\n"
                "Tus SkillPoints permanecen retenidos de forma segura durante la reserva y solo se liberan "
                "al instructor una vez completada y confirmada la clase mutuamente."
            )
            return text, None

        default_reply = (
            "¡Hola! Soy tu Copiloto Inteligente de SkillMatch 🤖✨\n\n"
            "Puedo ayudarte con acciones directas en la plataforma:\n"
            "- 🎓 **Crear una habilidad para enseñar:** *'Quiero enseñar Programación en Python nivel Avanzado cobrando 25 puntos'*\n"
            "- 🎯 **Registrar qué quieres aprender:** *'Quiero aprender Dominadas con el balón'* o *'Quiero aprender a tocar flauta'*\n"
            "- 💰 **Consultar tu saldo:** *'¿Cuál es mi saldo actual?'*\n"
            "- 📅 **Ver tus clases:** *'¿Cuándo es mi próxima sesión?'*\n"
            "- 🔍 **Buscar tutores:** *'Buscar tutores de Música'*"
        )
        return default_reply, None

    def _generate_local_fallback(self, msg: str, user: User) -> str:
        return (
            f"¡Hola {user.full_name}! Estoy configurado en modo local. "
            "Puedo ayudarte a revisar tu saldo, sesiones y reglas de SkillMatch."
        )


assistant_service = AssistantService()
