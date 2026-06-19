import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from app.core.config import settings
from app.notifiers.base import AlertPayload, Notifier, NotificationResult


class EmailNotifier(Notifier):
    def __init__(self, recipients: list[str]) -> None:
        self.recipients = recipients

    async def send(self, alert: AlertPayload) -> NotificationResult:
        if not settings.smtp_host:
            return NotificationResult.fail("SMTP not configured")

        subject = f"[PulseMetrics] {alert.severity.upper()} - {alert.rule_name} ({alert.application_name})"
        body = self._build_body(alert)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from
        msg["To"] = ", ".join(self.recipients)
        msg.attach(MIMEText(body, "html"))

        try:
            await aiosmtplib.send(
                msg,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_user or None,
                password=settings.smtp_password or None,
                use_tls=settings.smtp_port == 465,
                start_tls=settings.smtp_port == 587,
            )
            return NotificationResult.ok()
        except Exception as exc:
            return NotificationResult.fail(str(exc))

    def _build_body(self, alert: AlertPayload) -> str:
        details = "".join(
            f"<tr><td><b>{k}</b></td><td>{v}</td></tr>" for k, v in alert.payload.items()
        )
        return f"""
        <html><body>
        <h2>🚨 Alert: {alert.rule_name}</h2>
        <p><b>Application:</b> {alert.application_name}</p>
        <p><b>Severity:</b> {alert.severity.upper()}</p>
        <p><b>Fired at:</b> {alert.fired_at}</p>
        <h3>Details</h3>
        <table border="1">{details}</table>
        {"<p><a href='" + alert.dashboard_url + "'>View in dashboard</a></p>" if alert.dashboard_url else ""}
        <hr><small>PulseMetrics</small>
        </body></html>
        """
