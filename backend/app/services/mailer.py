"""Outbound email.

In production this sends via SMTP using :mod:`aiosmtplib`. In development or
tests (no ``RENO_SMTP_HOST`` configured) it logs the message and captures it
in :data:`SENT` for assertions.

We deliberately keep the API tiny — one ``send`` function — so the security
surface is small. Templates live inline; if they grow, factor out a
``jinja2``-backed renderer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SentEmail:
    to: str
    subject: str
    body: str


# Captured in-memory when SMTP is not configured. Tests inspect this list.
SENT: Final[list[SentEmail]] = []


async def send_email(to: str, subject: str, body: str) -> None:
    """Send (or capture) an email message.

    No HTML, no attachments in Phase 1 — keeps the surface minimal.
    """
    settings = get_settings()
    if not settings.smtp_host:
        SENT.append(SentEmail(to=to, subject=subject, body=body))
        logger.info("Email captured (no SMTP configured): to=%s subject=%s", to, subject)
        return

    from email.message import EmailMessage

    import aiosmtplib  # local import: only required in production paths

    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    await aiosmtplib.send(
        message,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user,
        password=(
            settings.smtp_password.get_secret_value()
            if settings.smtp_password is not None
            else None
        ),
        start_tls=True,
    )


def render_invitation(token: str, app_base_url: str) -> tuple[str, str]:
    """Return (subject, body) for an invitation email."""
    link = f"{app_base_url.rstrip('/')}/invite/{token}"
    subject = "Einladung zu Reno-Budget"
    body = (
        "Hallo\n\n"
        "Sie wurden zur Mitarbeit an Reno-Budget eingeladen.\n"
        f"Bitte folgen Sie diesem Link, um Ihr Konto einzurichten:\n\n  {link}\n\n"
        "Der Link ist 7 Tage gültig.\n\n"
        "Mit freundlichen Grüssen\nReno-Budget\n"
    )
    return subject, body


def render_password_reset(token: str, app_base_url: str) -> tuple[str, str]:
    """Return (subject, body) for a password-reset email."""
    link = f"{app_base_url.rstrip('/')}/passwort-zuruecksetzen/{token}"
    subject = "Passwort zurücksetzen — Reno-Budget"
    body = (
        "Hallo\n\n"
        "Sie haben angefordert, Ihr Passwort für Reno-Budget zurückzusetzen.\n"
        f"Bitte folgen Sie diesem Link, um ein neues Passwort zu vergeben:\n\n  {link}\n\n"
        "Der Link ist 1 Stunde gültig. Wenn Sie diese Anfrage nicht gestellt\n"
        "haben, können Sie diese E-Mail ignorieren.\n\n"
        "Mit freundlichen Grüssen\nReno-Budget\n"
    )
    return subject, body
