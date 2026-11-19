"""Test-first contracts for HU-38 transactional reminder email."""

import smtplib
from datetime import UTC, datetime
from uuid import uuid4

import pytest


def test_email_content_uses_recipient_timezone_and_threshold() -> None:
    from app.services.session_email_service import build_session_reminder_email

    message = build_session_reminder_email(
        event_id=uuid4(),
        threshold="24H",
        recipient_name="Antonio Peñaranda",
        recipient_email="antonio@example.com",
        counterpart_name="María Rossi",
        skill_name="Python Backend",
        starts_at=datetime(2026, 12, 2, 1, 30, tzinfo=UTC),
        timezone="America/La_Paz",
        modality="VIRTUAL",
        sessions_url="http://localhost:5173/app/sessions",
    )

    assert message.subject == "Tu sesión de SkillMatch comienza en 24 horas"
    assert "1 de diciembre de 2026" in message.text_body
    assert "21:30" in message.text_body
    assert "America/La_Paz" in message.text_body
    assert "Python Backend" in message.text_body
    assert "María Rossi" in message.text_body


def test_email_html_escapes_profile_content_and_has_plain_text_alternative() -> None:
    from app.services.session_email_service import build_session_reminder_email

    message = build_session_reminder_email(
        event_id=uuid4(),
        threshold="1H",
        recipient_name="<Antonio>",
        recipient_email="antonio@example.com",
        counterpart_name="Ana & María",
        skill_name='<script>alert("x")</script>',
        starts_at=datetime(2026, 12, 2, 1, 30, tzinfo=UTC),
        timezone="America/La_Paz",
        modality="PRESENCIAL",
        sessions_url="https://skillmatch.example/app/sessions",
    )

    assert message.subject == "Tu sesión de SkillMatch comienza en 1 hora"
    assert "<script>" not in message.html_body
    assert "&lt;script&gt;" in message.html_body
    assert "Ana &amp; María" in message.html_body
    assert "<script>" in message.text_body


def test_email_message_id_is_stable_and_changes_after_reschedule() -> None:
    from app.services.session_email_service import reminder_email_message_id

    event_id = uuid4()
    other_event_id = uuid4()

    assert reminder_email_message_id(event_id) == reminder_email_message_id(event_id)
    assert reminder_email_message_id(event_id) != reminder_email_message_id(other_event_id)
    assert reminder_email_message_id(event_id).endswith("@skillmatch>")


@pytest.mark.parametrize(
    ("email_enabled", "preference_enabled", "has_credentials", "expected"),
    [
        (True, True, True, True),
        (False, True, True, False),
        (True, False, True, False),
        (True, True, False, False),
    ],
)
def test_email_eligibility_requires_feature_preference_and_credentials(
    email_enabled: bool,
    preference_enabled: bool,
    has_credentials: bool,
    expected: bool,
) -> None:
    from app.services.session_email_service import is_email_delivery_enabled

    assert is_email_delivery_enabled(
        email_enabled=email_enabled,
        preference_enabled=preference_enabled,
        has_credentials=has_credentials,
    ) is expected


def test_smtp_error_classification_separates_retryable_and_permanent() -> None:
    from app.services.email_service import SMTPFailureKind, classify_smtp_failure

    assert classify_smtp_failure(smtplib.SMTPResponseException(421, b"temporary")) is SMTPFailureKind.TRANSIENT
    assert classify_smtp_failure(smtplib.SMTPResponseException(550, b"rejected")) is SMTPFailureKind.PERMANENT
    assert classify_smtp_failure(TimeoutError()) is SMTPFailureKind.TRANSIENT
    assert classify_smtp_failure(smtplib.SMTPAuthenticationError(535, b"bad credentials")) is SMTPFailureKind.CONFIGURATION


def test_smtp_message_preserves_deterministic_message_id_and_alternatives() -> None:
    from app.services.email_service import build_mime_message
    from app.services.session_email_service import build_session_reminder_email

    content = build_session_reminder_email(
        event_id=uuid4(),
        threshold="1H",
        recipient_name="Antonio",
        recipient_email="antonio@example.com",
        counterpart_name="María",
        skill_name="Guitarra",
        starts_at=datetime(2026, 12, 2, 1, 30, tzinfo=UTC),
        timezone="America/La_Paz",
        modality="VIRTUAL",
        sessions_url="https://skillmatch.example/app/sessions",
    )
    message = build_mime_message(
        content,
        from_address="sender@example.com",
        from_name="SkillMatch",
        reply_to="reply@example.com",
    )

    assert message["To"] == "antonio@example.com"
    assert message["From"] == "SkillMatch <sender@example.com>"
    assert message["Reply-To"] == "reply@example.com"
    assert message["Message-ID"] == content.message_id
    assert message.is_multipart()
    assert {part.get_content_type() for part in message.walk()} >= {"text/plain", "text/html"}
