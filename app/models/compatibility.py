import hashlib
import importlib.metadata
from pathlib import Path

from app.config import Settings
from app.core.exceptions import ModelCompatibilityError


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""): digest.update(chunk)
    return digest.hexdigest()


def validate(entry: dict, settings: Settings, symbol: str, timeframe: str) -> dict:
    required = {"model_id", "model_type", "model_version", "timeframe", "feature_names", "class_labels", "probability_method", "preprocessing", "dependency_versions"}
    missing = required - entry.keys()
    if missing: raise ModelCompatibilityError(f"Registry metadata missing: {sorted(missing)}")
    if entry["timeframe"] != timeframe: raise ModelCompatibilityError("Model timeframe mismatch")
    if entry.get("development_only") and settings.app_env != "test": raise ModelCompatibilityError("No verified trained production model is registered")
    if timeframe != settings.primary_signal_timeframe: raise ModelCompatibilityError("Only the primary-timeframe model can generate decisions")
    symbols = entry.get("supported_symbols", ["*"])
    if "*" not in symbols and symbol not in symbols: raise ModelCompatibilityError("Unsupported symbol")
    if entry["probability_method"] != "predict_proba": raise ModelCompatibilityError("Probability output is unavailable")
    if entry["class_labels"] != [0, 1]: raise ModelCompatibilityError("Class ordering must be [0, 1]")
    artifact = entry.get("artifact")
    if artifact:
        path = settings.model_artifact_dir / artifact
        if not path.is_file(): raise ModelCompatibilityError(f"Artifact not found: {path}")
        if not entry.get("sha256") or sha256(path) != entry["sha256"]: raise ModelCompatibilityError("Artifact checksum mismatch")
    for package, expected in entry.get("dependency_versions", {}).items():
        try: actual = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError as exc: raise ModelCompatibilityError(f"Missing dependency: {package}") from exc
        if expected and actual != expected: raise ModelCompatibilityError(f"Dependency mismatch for {package}: expected {expected}, got {actual}")
    return {"compatible": True, "artifact": artifact}
