from app.core.exceptions import ModelCompatibilityError


def validate_feature_order(features: dict, expected: list[str]) -> None:
    if list(features) != expected:
        raise ModelCompatibilityError("Feature names/order do not match the registered schema")
    if any(features[name] is None for name in expected):
        missing = [name for name in expected if features[name] is None]
        raise ModelCompatibilityError(f"Required model features are missing: {missing}")

