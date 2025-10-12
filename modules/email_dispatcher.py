import logging
import smtplib
from email.message import EmailMessage
from typing import Iterable, Optional, Sequence

from config import Config

logger = logging.getLogger(__name__)


class EmailDispatcher:
    """SMTP-based email sender with graceful fallback to dry-run logging."""

    def __init__(self, config: Optional[Config] = None) -> None:
        self.config = config or Config()
        self.host = self.config.EMAIL_SMTP_HOST
        self.port = self.config.EMAIL_SMTP_PORT
        self.username = self.config.EMAIL_SMTP_USERNAME
        self.password = self.config.EMAIL_SMTP_PASSWORD
        self.from_address = self.config.EMAIL_FROM_ADDRESS or self.config.FOLLOWUP_SENDER_EMAIL
        self.use_tls = self.config.EMAIL_USE_TLS

    def is_configured(self) -> bool:
        return bool(self.host and self.port and self.username and self.password and self.from_address)

    def send_email(
        self,
        to_address: str,
        subject: str,
        body: str,
        cc: Optional[Sequence[str]] = None,
        bcc: Optional[Sequence[str]] = None,
    ) -> bool:
        if not self.is_configured():
            logger.info("EmailDispatcher misconfigured; printing email instead of sending.")
            self._log_email(to_address, subject, body, cc, bcc)
            return False

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.from_address
        message["To"] = to_address
        if cc:
            message["Cc"] = ", ".join(cc)
        message.set_content(body)

        recipients = [to_address]
        recipients.extend(cc or [])
        recipients.extend(bcc or [])

        try:
            with smtplib.SMTP(self.host, self.port, timeout=30) as smtp:
                if self.use_tls:
                    smtp.starttls()
                smtp.login(self.username, self.password)
                smtp.send_message(message, to_addrs=list(self._unique(recipients)))
            logger.info("Sent email to %s", to_address)
            return True
        except Exception as exc:
            logger.error("Failed to send email to %s: %s", to_address, exc)
            self._log_email(to_address, subject, body, cc, bcc)
            return False

    def _log_email(
        self,
        to_address: str,
        subject: str,
        body: str,
        cc: Optional[Sequence[str]],
        bcc: Optional[Sequence[str]],
    ) -> None:
        logger.info("EMAIL (dry run) To=%s Cc=%s Bcc=%s", to_address, cc, bcc)
        logger.info("Subject: %s", subject)
        logger.info("Body:\n%s", body)

    @staticmethod
    def _unique(addresses: Iterable[str]) -> Iterable[str]:
        seen = set()
        for value in addresses:
            if not value:
                continue
            normalized = value.strip().lower()
            if normalized and normalized not in seen:
                seen.add(normalized)
                yield value

