from app.config import Settings
from app.core.exceptions import ModelCompatibilityError


def load(entry: dict, settings: Settings):
    model_type = entry["model_type"]
    if model_type == "deterministic_baseline": return None
    if model_type == "sklearn_classifier":
        try:
            import joblib
            model = joblib.load(settings.model_artifact_dir / entry["artifact"])
            if not hasattr(model, "predict_proba"): raise TypeError("artifact lacks predict_proba")
            return model
        except Exception as exc: raise ModelCompatibilityError(f"Unable to load sklearn model: {exc}") from exc
    if model_type == "catboost_classifier":
        try:
            from catboost import CatBoostClassifier
            model = CatBoostClassifier()
            model.load_model(str(settings.model_artifact_dir / entry["artifact"]))
            return model
        except Exception as exc: raise ModelCompatibilityError(f"Unable to load CatBoost model: {exc}") from exc
    raise ModelCompatibilityError(f"Unsupported model type: {model_type}")
