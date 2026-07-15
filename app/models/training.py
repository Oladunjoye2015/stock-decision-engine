import hashlib
import importlib.metadata
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier, VotingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, brier_score_loss, log_loss, precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


FEATURE_NAMES = ["body_pct", "range_pct", "close_vs_ema20", "ema20_vs_ema50", "rsi", "atr_pct", "vol_ratio", "ret1", "ret3", "hour_sin", "hour_cos"]


def _rsi(close: pd.Series, length: int = 14):
    delta = close.diff(); gain = delta.clip(lower=0).ewm(alpha=1/length, adjust=False).mean(); loss = (-delta.clip(upper=0)).ewm(alpha=1/length, adjust=False).mean()
    return 100 - 100 / (1 + gain / loss.replace(0, np.nan))


def build_training_frame(candles: pd.DataFrame, horizon_bars: int = 3, cost_bps: float = 10, minimum_move_bps: float = 5) -> pd.DataFrame:
    required = {"timestamp", "symbol", "open", "high", "low", "close", "volume"}
    missing = required - set(candles)
    if missing: raise ValueError(f"Candle data is missing columns: {sorted(missing)}")
    df = candles.copy(); df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True); df = df.sort_values(["symbol", "timestamp"]); groups = df.groupby("symbol", group_keys=False)
    df["ema20"] = groups["close"].transform(lambda x: x.ewm(span=20, adjust=False).mean()); df["ema50"] = groups["close"].transform(lambda x: x.ewm(span=50, adjust=False).mean())
    previous_close = groups["close"].shift(1); true_range = pd.concat([(df["high"]-df["low"]), (df["high"]-previous_close).abs(), (df["low"]-previous_close).abs()], axis=1).max(axis=1)
    df["atr"] = true_range.groupby(df["symbol"]).transform(lambda x: x.ewm(alpha=1/14, adjust=False).mean()); df["rsi"] = groups["close"].transform(_rsi)
    df["body_pct"] = (df["close"]-df["open"]) / df["open"]; df["range_pct"] = (df["high"]-df["low"]) / df["close"]; df["close_vs_ema20"] = (df["close"]-df["ema20"])/df["ema20"]; df["ema20_vs_ema50"] = (df["ema20"]-df["ema50"])/df["ema50"]; df["atr_pct"] = df["atr"]/df["close"]
    median_volume = groups["volume"].transform(lambda x: x.rolling(20, min_periods=5).median()); df["vol_ratio"] = df["volume"]/median_volume.replace(0, np.nan); df["ret1"] = groups["close"].pct_change(1); df["ret3"] = groups["close"].pct_change(3)
    hour = df["timestamp"].dt.hour + df["timestamp"].dt.minute/60; df["hour_sin"] = np.sin(2*np.pi*hour/24); df["hour_cos"] = np.cos(2*np.pi*hour/24)
    future_close = groups["close"].shift(-horizon_bars); df["future_return"] = future_close/df["close"]-1; threshold = (cost_bps+minimum_move_bps)/10_000; df["target"] = (df["future_return"] > threshold).astype(int)
    return df.dropna(subset=[*FEATURE_NAMES, "future_return"]).reset_index(drop=True)


def chronological_split(df: pd.DataFrame, train_fraction=.70, validation_fraction=.15):
    ordered = df.sort_values(["timestamp", "symbol"]); timestamps = np.array(sorted(ordered["timestamp"].unique())); train_index = int(len(timestamps)*train_fraction); validation_index = int(len(timestamps)*(train_fraction+validation_fraction))
    if train_index < 100 or validation_index-train_index < 30 or len(timestamps)-validation_index < 30: raise ValueError("Not enough unique timestamps for train/validation/test splits; collect more history")
    train_end, validation_end = timestamps[train_index], timestamps[validation_index]
    return ordered[ordered.timestamp < train_end], ordered[(ordered.timestamp >= train_end) & (ordered.timestamp < validation_end)], ordered[ordered.timestamp >= validation_end]


def candidates(random_state=42):
    models = {
        "logistic": make_pipeline(SimpleImputer(), StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced", random_state=random_state)),
        "random_forest": make_pipeline(SimpleImputer(), RandomForestClassifier(n_estimators=300, min_samples_leaf=10, max_features="sqrt", class_weight="balanced_subsample", n_jobs=-1, random_state=random_state)),
        "hist_gradient_boosting": make_pipeline(SimpleImputer(), HistGradientBoostingClassifier(max_iter=250, learning_rate=.05, max_leaf_nodes=15, l2_regularization=1, random_state=random_state)),
    }
    try:
        from catboost import CatBoostClassifier
        models["catboost"] = CatBoostClassifier(iterations=350, depth=6, learning_rate=.04, loss_function="Logloss", verbose=False, random_seed=random_state, allow_writing_files=False)
    except ImportError: pass
    return models


def metrics(model, x, y, future_return=None, threshold=.55, cost_bps=10):
    probabilities = model.predict_proba(x)[:, 1]; predicted = probabilities >= threshold
    result = {"log_loss": log_loss(y, probabilities, labels=[0, 1]), "brier": brier_score_loss(y, probabilities), "balanced_accuracy": balanced_accuracy_score(y, predicted), "precision": precision_score(y, predicted, zero_division=0), "roc_auc": roc_auc_score(y, probabilities) if len(np.unique(y)) == 2 else None, "signals": int(predicted.sum())}
    if future_return is not None: result["mean_net_signal_return"] = float((future_return[predicted] - cost_bps/10_000).mean()) if predicted.any() else 0
    return result


def train_and_select(candles: pd.DataFrame, artifact_dir: Path, registry_path: Path, model_id: str = "ensemble-h1-v1", min_ensemble_logloss_improvement=.002, cost_bps=10):
    frame = build_training_frame(candles, cost_bps=cost_bps); train, validation, test = chronological_split(frame); x_train, y_train = train[FEATURE_NAMES], train["target"]; x_val, y_val = validation[FEATURE_NAMES], validation["target"]
    fitted, validation_metrics = {}, {}
    for name, model in candidates().items(): model.fit(x_train, y_train); fitted[name] = model; validation_metrics[name] = metrics(model, x_val, y_val, validation["future_return"], cost_bps=cost_bps)
    ranked = sorted(fitted, key=lambda name: validation_metrics[name]["log_loss"]); best_name = ranked[0]; selected_name = best_name; selected = fitted[best_name]
    if len(ranked) >= 2:
        ensemble_names = ranked[:min(4, len(ranked))]; weights = [1/max(validation_metrics[name]["log_loss"], 1e-6) for name in ensemble_names]
        ensemble = VotingClassifier([(name, candidates()[name]) for name in ensemble_names], voting="soft", weights=weights, flatten_transform=True); ensemble.fit(x_train, y_train); ensemble_result = metrics(ensemble, x_val, y_val, validation["future_return"], cost_bps=cost_bps); validation_metrics["soft_voting_ensemble"] = ensemble_result
        best_result = validation_metrics[best_name]
        if best_result["log_loss"]-ensemble_result["log_loss"] >= min_ensemble_logloss_improvement and ensemble_result["balanced_accuracy"] >= best_result["balanced_accuracy"]-.01: selected_name, selected = "soft_voting_ensemble", ensemble
    combined = pd.concat([train, validation]); selected.fit(combined[FEATURE_NAMES], combined["target"]); test_result = metrics(selected, test[FEATURE_NAMES], test["target"], test["future_return"], cost_bps=cost_bps)
    artifact_dir.mkdir(parents=True, exist_ok=True); artifact_path = artifact_dir / f"{model_id}.joblib"; joblib.dump(selected, artifact_path); checksum = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    dependencies = {name: importlib.metadata.version(name) for name in ("numpy", "pandas", "scikit-learn", "joblib")}
    if selected_name == "catboost" or (selected_name == "soft_voting_ensemble" and "catboost" in ensemble_names): dependencies["catboost"] = importlib.metadata.version("catboost")
    production_eligible = bool(test_result["signals"] >= 100 and test_result["mean_net_signal_return"] > 0 and test_result["balanced_accuracy"] >= .51 and (test_result["roc_auc"] or 0) >= .52)
    metadata = {"model_id": model_id, "model_type": "sklearn_classifier", "model_version": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"), "artifact": artifact_path.name, "sha256": checksum, "timeframe": "60Min", "supported_symbols": sorted(frame["symbol"].unique().tolist()), "feature_names": FEATURE_NAMES, "preprocessing": {"implemented_inside_artifact": True}, "probability_method": "predict_proba", "class_labels": [0, 1], "dependency_versions": dependencies, "training_metadata": {"selected_candidate": selected_name, "rows": len(frame), "train_rows": len(train), "validation_rows": len(validation), "test_rows": len(test), "validation_metrics": validation_metrics, "final_test_metrics": test_result, "cost_bps": cost_bps, "label_horizon_bars": 3, "selection_rule": "ensemble only when validation log-loss improves by configured minimum without material balanced-accuracy loss", "production_eligibility_rule": "at least 100 test signals, positive mean net signal return, balanced accuracy >= 0.51, ROC AUC >= 0.52", "production_eligible": production_eligible, "trained_at_utc": datetime.now(timezone.utc).isoformat()}, "enabled": production_eligible}
    registry = json.loads(registry_path.read_text()) if registry_path.exists() else {"schema_version": 1, "models": []}
    for item in registry.get("models", []):
        if item.get("timeframe") == "60Min": item["enabled"] = False
    registry["models"] = [item for item in registry.get("models", []) if item.get("model_id") != model_id] + [metadata]
    registry_path.write_text(json.dumps(registry, indent=2)+"\n"); (artifact_dir/f"{model_id}.metadata.json").write_text(json.dumps(metadata, indent=2)+"\n")
    return metadata
