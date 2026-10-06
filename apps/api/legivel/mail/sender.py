import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from legivel.config import Settings

logger = logging.getLogger("legivel.mail")
TIMEOUT_SECONDS = 15


class MailError(RuntimeError):
    pass


@dataclass(frozen=True)
class OutgoingMail:
    to: str
    subject: str
    text: str
    html: str


class Mailer:
    def __init__(self, settings: Settings):
        self._settings = settings

    @property
    def configured(self) -> bool:
        return self._settings.smtp_configured

    def build(self, mail: OutgoingMail, sender_name: str) -> EmailMessage:
        message = EmailMessage()
        message["From"] = formataddr((sender_name, self._settings.smtp_from))
        message["To"] = mail.to
        message["Subject"] = mail.subject
        message["Message-ID"] = make_msgid(domain=self._settings.smtp_from.split("@")[-1] or None)
        message.set_content(mail.text)
        message.add_alternative(mail.html, subtype="html")
        return message

    def send(self, mail: OutgoingMail, sender_name: str) -> None:
        if not self.configured:
            raise MailError("SMTP não configurado")
        settings = self._settings
        message = self.build(mail, sender_name)
        try:
            if settings.smtp_security == "ssl":
                client = smtplib.SMTP_SSL(
                    settings.smtp_host, settings.smtp_port, timeout=TIMEOUT_SECONDS, context=ssl.create_default_context()
                )
            else:
                client = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=TIMEOUT_SECONDS)
            with client:
                if settings.smtp_security == "starttls":
                    client.starttls(context=ssl.create_default_context())
                if settings.smtp_user:
                    client.login(settings.smtp_user, settings.smtp_password)
                client.send_message(message)
        except (OSError, smtplib.SMTPException) as error:
            logger.warning("Falha ao enviar e-mail: %s", type(error).__name__)
            raise MailError(f"Falha ao enviar e-mail: {error}") from error
