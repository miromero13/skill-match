"""Pure HU-38 reminder-email policy and deterministic templates."""

from dataclasses import dataclass
from datetime import datetime
from html import escape
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_MONTHS_ES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


@dataclass(frozen=True, slots=True)
class ReminderEmailContent:
    recipient_email: str
    subject: str
    text_body: str
    html_body: str
    message_id: str


def reminder_email_message_id(event_id: UUID) -> str:
    """Return a stable RFC 5322 identity for retries of the same domain event."""
    return f"<session-reminder-{event_id}@skillmatch>"


def is_email_delivery_enabled(
    *,
    email_enabled: bool,
    preference_enabled: bool,
    has_credentials: bool,
) -> bool:
    return email_enabled and preference_enabled and has_credentials


def _local_datetime(starts_at: datetime, timezone: str) -> datetime:
    if starts_at.tzinfo is None or starts_at.utcoffset() is None:
        raise ValueError("starts_at debe incluir zona horaria")
    try:
        return starts_at.astimezone(ZoneInfo(timezone))
    except ZoneInfoNotFoundError as exc:
        raise ValueError("Timezone IANA no reconocida") from exc


def build_session_reminder_email(
    *,
    event_id: UUID,
    threshold: str,
    recipient_name: str,
    recipient_email: str,
    counterpart_name: str,
    skill_name: str,
    starts_at: datetime,
    timezone: str,
    modality: str,
    sessions_url: str,
) -> ReminderEmailContent:
    """Build text and HTML alternatives without provider or database I/O."""
    if threshold not in {"24H", "1H"}:
        raise ValueError("Umbral de recordatorio no soportado")
    local_start = _local_datetime(starts_at, timezone)
    label = "24 horas" if threshold == "24H" else "1 hora"
    date_label = (
        f"{local_start.day} de {_MONTHS_ES[local_start.month - 1]} "
        f"de {local_start.year}"
    )
    time_label = local_start.strftime("%H:%M")
    subject = f"Tu sesión de SkillMatch comienza en {label}"
    text_body = (
        f"Hola, {recipient_name}:\n\n"
        f"Tu sesión de {skill_name} con {counterpart_name} comienza en {label}.\n\n"
        f"Fecha: {date_label}\n"
        f"Hora: {time_label}\n"
        f"Zona horaria: {timezone}\n"
        f"Modalidad: {modality}\n\n"
        f"Revisa tu sesión: {sessions_url}\n\n"
        "Puedes administrar este canal desde tus preferencias de notificaciones."
    )
    safe = {
        "recipient": escape(recipient_name),
        "skill": escape(skill_name),
        "counterpart": escape(counterpart_name),
        "label": escape(label),
        "date": escape(date_label),
        "time": escape(time_label),
        "timezone": escape(timezone),
        "modality": escape(modality),
        "url": escape(sessions_url, quote=True),
    }
    html_body = f"""<!doctype html>
<html lang="es">
  <body>
    <p>Hola, {safe['recipient']}:</p>
    <p>Tu sesión de <strong>{safe['skill']}</strong> con {safe['counterpart']} comienza en {safe['label']}.</p>
    <ul>
      <li>Fecha: {safe['date']}</li>
      <li>Hora: {safe['time']}</li>
      <li>Zona horaria: {safe['timezone']}</li>
      <li>Modalidad: {safe['modality']}</li>
    </ul>
    <p><a href="{safe['url']}">Revisar mi sesión en SkillMatch</a></p>
    <p>Puedes administrar este canal desde tus preferencias de notificaciones.</p>
  </body>
</html>"""
    return ReminderEmailContent(
        recipient_email=recipient_email.strip().lower(),
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        message_id=reminder_email_message_id(event_id),
    )
