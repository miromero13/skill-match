import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.catalog import Skill
from app.models.exchange_session import ExchangeSession
from app.models.teaching_skill import TeachingSkill
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
4. **Reglas de la Comunidad y Disputas**:
   - Escrow: Al reservar con puntos, los SP quedan protegidos en custodia hasta que ambas partes confirmen la sesión.
   - KYC: Se requiere foto de documento y verificación facial biométrica para retiros y emisión de certificados.
   - Arbitraje: En caso de ausencia o incumplimiento del tutor, se puede abrir una disputa con evidencia.

REGLAS DE FORMATO Y TONO:
- Responde SIEMPRE en español en Markdown limpio y legible (usando negritas y listas breves).
- Sé directo y evita rodeos innecesarios.
- Cuando utilices una herramienta para obtener datos (saldo, sesiones, tutores), resume los hallazgos amigablemente.
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
            "¿Cuál es mi saldo actual?",
            "¿Cuándo es mi próxima sesión?",
            "Buscar tutores de Python",
            "¿Cómo funciona el Escrow?",
        ]

        if not api_key:
            # Fallback inteligente si no hay clave configurada
            reply_text = self._generate_local_fallback(user_message, user)
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
                    reply_text = await self._generate_offline_reply(db, user, user_message)
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
                reply_text = await self._generate_offline_reply(db, user, user_message)

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
        return "Aquí tienes la información solicitada."

    async def _generate_offline_reply(self, db: AsyncSession, user: User, msg: str) -> str:
        """Generador heurístico seguro cuando la API externa no está disponible temporalmente."""
        low = msg.lower()
        if any(w in low for w in ["saldo", "puntos", "cuanto tengo", "billetera", "sp"]):
            res = await self._tool_get_profile_summary(db, user)
            return self._format_tool_direct_summary("get_my_profile_summary", res)
        elif any(w in low for w in ["sesion", "sesiones", "clase", "agenda", "horario"]):
            res = await self._tool_get_upcoming_sessions(db, user)
            return self._format_tool_direct_summary("get_my_upcoming_sessions", res)
        elif any(w in low for w in ["escrow", "custodia"]):
            return (
                "**Sistema Escrow en SkillMatch:**\n"
                "Tus SkillPoints permanecen retenidos de forma segura durante la reserva y solo se liberan "
                "al instructor una vez completada y confirmada la clase."
            )
        return (
            "¡Hola! Soy tu asistente de SkillMatch. Puedo ayudarte a consultar tu saldo de SkillPoints, "
            "ver tus próximas sesiones agendadas, encontrar tutores o explicarte el funcionamiento de la plataforma."
        )

    def _generate_local_fallback(self, msg: str, user: User) -> str:
        return (
            f"¡Hola {user.full_name}! Estoy configurado en modo local. "
            "Puedo ayudarte a revisar tu saldo, sesiones y reglas de SkillMatch."
        )


assistant_service = AssistantService()
