from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlencode
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CalendarExport:
    filename: str
    content_type: str
    ics_content: str
    google_calendar_url: str


def is_calendar_export_allowed(status: str) -> bool:
    return status == "ACCEPTED"


def _utc_stamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("La fecha del calendario debe incluir zona horaria.")
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _escape_ics(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def build_google_calendar_url(
    *,
    starts_at: datetime,
    ends_at: datetime,
    timezone: str,
    skill_name: str,
    counterpart_name: str,
    modality: str,
) -> str:
    query = urlencode(
        {
            "action": "TEMPLATE",
            "dates": f"{_utc_stamp(starts_at)}/{_utc_stamp(ends_at)}",
            "text": f"SkillMatch · {skill_name}",
            "details": (
                f"Sesión de intercambio con {counterpart_name}. "
                f"Modalidad: {'Virtual' if modality == 'VIRTUAL' else 'Presencial'}."
            ),
            "ctz": timezone,
        }
    )
    return f"https://calendar.google.com/calendar/render?{query}"


def build_ics_export(
    *,
    session_id: UUID,
    starts_at: datetime,
    ends_at: datetime,
    timezone: str,
    skill_name: str,
    counterpart_name: str,
    modality: str,
) -> CalendarExport:
    if ends_at <= starts_at:
        raise ValueError("El fin del evento debe ser posterior al inicio.")
    summary = _escape_ics(f"SkillMatch · {skill_name}")
    description = _escape_ics(
        f"Sesión de intercambio con {counterpart_name}. "
        f"Modalidad: {'Virtual' if modality == 'VIRTUAL' else 'Presencial'}."
    )
    lines = (
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//SkillMatch//Sesiones de intercambio//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{session_id}@skillmatch",
        f"DTSTAMP:{_utc_stamp(datetime.now(UTC))}",
        f"DTSTART:{_utc_stamp(starts_at)}",
        f"DTEND:{_utc_stamp(ends_at)}",
        f"SUMMARY:{summary}",
        f"DESCRIPTION:{description}",
        "STATUS:CONFIRMED",
        "END:VEVENT",
        "END:VCALENDAR",
    )
    return CalendarExport(
        filename=f"skillmatch-session-{session_id}.ics",
        content_type="text/calendar; charset=utf-8",
        ics_content="\r\n".join(lines) + "\r\n",
        google_calendar_url=build_google_calendar_url(
            starts_at=starts_at,
            ends_at=ends_at,
            timezone=timezone,
            skill_name=skill_name,
            counterpart_name=counterpart_name,
            modality=modality,
        ),
    )
