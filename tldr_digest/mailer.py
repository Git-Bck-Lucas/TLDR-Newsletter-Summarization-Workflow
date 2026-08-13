"""Mailversand des fertigen HTML-Digests via Gmail SMTP (STARTTLS)."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from .config import Settings


def send(html: str, subject: str, settings: Settings) -> None:
    """Verschickt eine HTML-Mail an settings.mail_to.

    Wir setzen einen Plain-Text-Fallback plus den HTML-Body, damit die Mail auch in
    Clients ohne HTML-Ansicht lesbar bleibt.
    """
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_user
    msg["To"] = settings.mail_to
    msg.set_content(
        "Diese Mail enthält ein HTML-Digest. Bitte in einem HTML-fähigen Client öffnen."
    )
    msg.add_alternative(html, subtype="html")

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_app_password)
        server.send_message(msg)
