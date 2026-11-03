import smtplib
from email.message import EmailMessage
from ..core.config import get_settings


class EmailNotConfigured(Exception):
    pass


class EmailDeliveryError(Exception):
    pass


def send_password_reset_email(*, recipient: str, reset_url: str) -> None:
    settings = get_settings()
    if not all((settings.smtp_host, settings.smtp_username, settings.smtp_password, settings.smtp_from_email)):
        raise EmailNotConfigured("SMTP is not configured")
    message = EmailMessage()
    message["Subject"] = "Reset your RETUNORI password"
    message["From"] = settings.smtp_from_email
    message["To"] = recipient
    message.set_content(
        "Use the secure link below to reset your RETUNORI password. "
        "The link expires in 30 minutes and can only be used once.\n\n"
        f"{reset_url}\n\nIf you did not request this, you can ignore this email."
    )
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            if settings.smtp_use_tls:
                server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException) as error:
        raise EmailDeliveryError("Password reset email could not be delivered") from error
