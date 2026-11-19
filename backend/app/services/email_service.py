"""Provider-neutral SMTP transport for transactional email."""

import asyncio
import smtplib
import ssl
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import formataddr
from enum import StrEnum

from app.services.session_email_service import ReminderEmailContent


class SMTPFailureKind(StrEnum):
    TRANSIENT = "TRANSIENT"
    PERMANENT = "PERMANENT"
    CONFIGURATION = "CONFIGURATION"


def classify_smtp_failure(exc: BaseException) -> SMTPFailureKind:
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return SMTPFailureKind.CONFIGURATION
    if isinstance(exc, smtplib.SMTPResponseException):
        return SMTPFailureKind.TRANSIENT if 400 <= exc.smtp_code < 500 else SMTPFailureKind.PERMANENT
    if isinstance(exc, (TimeoutError, ConnectionError, OSError, smtplib.SMTPServerDisconnected)):
        return SMTPFailureKind.TRANSIENT
    return SMTPFailureKind.PERMANENT


def build_mime_message(
    content: ReminderEmailContent,
    *,
    from_address: str,
    from_name: str,
    reply_to: str | None,
) -> EmailMessage:
    message = EmailMessage(policy=SMTP)
    message["Subject"] = content.subject
    message["From"] = formataddr((from_name, from_address))
    message["To"] = content.recipient_email
    if reply_to:
        message["Reply-To"] = reply_to
    message["Message-ID"] = content.message_id
    message.set_content(content.text_body)
    message.add_alternative(content.html_body, subtype="html")
    return message


class SMTPEmailSender:
    """Blocking stdlib SMTP wrapped in a worker thread for async callers."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        starttls: bool,
        timeout_seconds: int,
        from_address: str,
        from_name: str,
        reply_to: str | None,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._starttls = starttls
        self._timeout_seconds = timeout_seconds
        self._from_address = from_address
        self._from_name = from_name
        self._reply_to = reply_to

    async def send(self, content: ReminderEmailContent) -> None:
        message = build_mime_message(
            content,
            from_address=self._from_address,
            from_name=self._from_name,
            reply_to=self._reply_to,
        )
        await asyncio.to_thread(self._send_sync, message)

    def _send_sync(self, message: EmailMessage) -> None:
        with smtplib.SMTP(self._host, self._port, timeout=self._timeout_seconds) as client:
            client.ehlo()
            if self._starttls:
                client.starttls(context=ssl.create_default_context())
                client.ehlo()
            client.login(self._username, self._password)
            client.send_message(message)
