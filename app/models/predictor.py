from app.models.compatibility import validate
from app.models.feature_schema import validate_feature_order
from app.models.loader import load


def predict(entry: dict, settings, symbol: str, timeframe: str, features: dict) -> dict:
    validate(entry, settings, symbol, timeframe)
    expected = entry["feature_names"]
    validate_feature_order(features, expected)
    model = load(entry, settings)
    if model is None:
        close, open_ = float(features["close"]), float(features["open"])
        probability = max(.01, min(.99, .5 + (close - open_) / max(open_, .01) * 5))
    else:
        try:
            import pandas as pd
            output = model.predict_proba(pd.DataFrame([[features[x] for x in expected]], columns=expected))
            if getattr(output, "shape", None) != (1, 2): raise ValueError(f"unexpected probability output shape {getattr(output, 'shape', None)}")
            probability = float(output[0][1])
        except Exception as exc:
            from app.core.exceptions import ModelCompatibilityError
            raise ModelCompatibilityError(f"Model probability inference failed: {exc}") from exc
    return {"model_type": entry["model_type"], "model_version": entry["model_version"], "probability": probability, "margin": abs(probability - .5), "class_labels": entry["class_labels"]}
