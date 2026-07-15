import hmac

from fastapi import Depends, Header, HTTPException, status

from app.config import Settings, get_settings


def authenticate_webhook(
    x_webhook_passphrase: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.webhook_passphrase:
        if settings.app_env == "production":
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Webhook authentication is not configured")
        return
    if not x_webhook_passphrase or not hmac.compare_digest(x_webhook_passphrase, settings.webhook_passphrase):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid webhook passphrase")
