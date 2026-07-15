import json
from pathlib import Path

from app.config import Settings
from app.core.exceptions import ModelCompatibilityError


class ModelRegistry:
    def __init__(self, settings: Settings): self.settings = settings

    def load(self) -> dict:
        path = self.settings.model_registry_path
        if not path.exists(): raise ModelCompatibilityError(f"Model registry not found: {path}")
        try: data = json.loads(path.read_text())
        except Exception as exc: raise ModelCompatibilityError(f"Invalid model registry: {exc}") from exc
        if data.get("schema_version") != 1: raise ModelCompatibilityError("Unsupported model registry schema")
        return data

    def resolve(self, symbol: str, timeframe: str) -> dict:
        for item in self.load().get("models", []):
            symbols = item.get("supported_symbols", ["*"])
            available = item.get("enabled", True) or (self.settings.app_env == "test" and item.get("development_only", False))
            if available and item.get("timeframe") == timeframe and ("*" in symbols or symbol in symbols):
                return item
        raise ModelCompatibilityError(f"No compatible model registered for {symbol} {timeframe}")
