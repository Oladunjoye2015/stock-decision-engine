from __future__ import annotations

from urllib.parse import urlparse

import httpx

from app.core.exceptions import SignalStackNotConfiguredError
from app.execution.signalstack_schemas import SignalStackWebhookPayload


class SignalStackTestTransport:
    """Transport restricted to an explicitly configured SignalStack test webhook."""

    def __init__(self, settings, client: httpx.Client | None = None):
        self.settings = settings
        self.client = client

    def readiness(self) -> dict:
        url = self.settings.signalstack_webhook_url.strip()
        parsed = urlparse(url)
        checks = {
            "webhook_configured": bool(url),
            "webhook_type_test": self.settings.signalstack_webhook_type == "test",
            "test_transport_enabled": self.settings.signalstack_test_transport_enabled,
            "live_execution_disabled": not self.settings.signalstack_live_execution_allowed,
            "https_url": parsed.scheme == "https" and bool(parsed.netloc),
        }
        failed = [name for name, passed in checks.items() if not passed]
        return {"ready": not failed, "checks": checks, "failed": failed}

    def send(self, payload: SignalStackWebhookPayload) -> dict:
        state = self.readiness()
        if not state["ready"]:
            raise SignalStackNotConfiguredError("SignalStack test transport refused: " + ", ".join(state["failed"]))
        owns_client = self.client is None
        client = self.client or httpx.Client(timeout=10)
        try:
            response = client.post(self.settings.signalstack_webhook_url, json=payload.model_dump())
            response.raise_for_status()
            return {"sent": True, "test_only": True, "status_code": response.status_code,
                    "payload": payload.model_dump(), "response_received": True}
        finally:
            if owns_client:
                client.close()
