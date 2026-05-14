"""Telegram alert notifications for the NIDS.

Exposes a TelegramNotifier that sends a message to a configured chat whenever
the ensemble detects an intrusion above the confidence threshold.

Configuration is read from environment variables (via .env):
    TELEGRAM_BOT_TOKEN  — the bot token from @BotFather
    TELEGRAM_CHAT_ID    — the target chat / channel ID
    NOTIFY_CONFIDENCE_THRESHOLD — minimum confidence to trigger (default 0.75)

If the variables are not set, is_configured() returns False and send_alert()
is a no-op.  Network failures are logged as warnings, never raised.
"""

import logging
from datetime import datetime

import httpx

from backend.config import (
    NOTIFY_CONFIDENCE_THRESHOLD,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
)

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Sends formatted Telegram alerts on high-confidence intrusion detections."""

    def __init__(
        self,
        token: str = TELEGRAM_BOT_TOKEN,
        chat_id: str = TELEGRAM_CHAT_ID,
    ) -> None:
        """Initialise the notifier with bot credentials.

        Args:
            token:   Telegram Bot API token.
            chat_id: Target chat or channel ID.
        """
        self._token = token
        self._chat_id = chat_id
        self._api_url = f"https://api.telegram.org/bot{token}/sendMessage"

    def is_configured(self) -> bool:
        """Return True if both token and chat_id are non-empty strings."""
        return bool(self._token and self._chat_id)

    async def send_alert(self, alert_data: dict) -> None:
        """Send a Telegram notification for a detected intrusion.

        Skips silently if the notifier is not configured or if
        attack_confidence is below NOTIFY_CONFIDENCE_THRESHOLD.
        Any network error is logged as a warning — never raised.

        Args:
            alert_data: Dict with keys:
                attack_type       (str)   — e.g. "DDoS", "PortScan"
                attack_confidence (float) — 0.0–1.0
                source_ip         (str)
                protocol          (str)
                model_votes       (dict)  — {model_name: 0|1}
                timestamp         (datetime | str)
        """
        if not self.is_configured():
            return

        confidence = float(alert_data.get("attack_confidence", 0.0))
        if confidence < NOTIFY_CONFIDENCE_THRESHOLD:
            return

        message = self._format_message(alert_data)
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    self._api_url,
                    json={
                        "chat_id": self._chat_id,
                        "text": message,
                        "parse_mode": "Markdown",
                    },
                )
        except Exception as exc:
            logger.warning("Telegram notification failed: %s", exc)

    def _format_message(self, alert_data: dict) -> str:
        """Build the Markdown-formatted alert message body.

        Args:
            alert_data: Same dict as send_alert().

        Returns:
            Multi-line Markdown string ready for the Telegram Bot API.
        """
        confidence = float(alert_data.get("attack_confidence", 0.0))
        attack_type = alert_data.get("attack_type", "Unknown")
        source_ip = alert_data.get("source_ip", "unknown")
        protocol = str(alert_data.get("protocol", "unknown")).upper()
        votes = alert_data.get("model_votes", {})

        ts = alert_data.get("timestamp", datetime.utcnow())
        if hasattr(ts, "strftime"):
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
        else:
            ts_str = str(ts).replace("T", " ")[:19]

        def icon(key: str) -> str:
            return "✓" if votes.get(key, 0) == 1 else "✗"

        model_line = (
            f"IF{icon('isolation_forest')} "
            f"LOF{icon('lof')} "
            f"SVM{icon('svm')} "
            f"RF{icon('random_forest')}"
        )

        return (
            f"🚨 *INTRUSION DETECTED*\n"
            f"Type: `{attack_type}`\n"
            f"Confidence: `{confidence * 100:.0f}%`\n"
            f"Source IP: `{source_ip}`\n"
            f"Protocol: `{protocol}`\n"
            f"Models: `{model_line}`\n"
            f"Time: `{ts_str}`"
        )
