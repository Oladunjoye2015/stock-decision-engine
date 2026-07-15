import hashlib,json
from pathlib import Path

import joblib
import pandas as pd

from app.models.breakout_confidence import FEATURES,prepare_breakout_feature_frame


def load_ml_shadow(config_path:Path,registry_path:Path,artifact_dir:Path):
    config=json.loads(config_path.read_text())
    if config.get("execution_enabled") is not False or config.get("research_only") is not True or config.get("promotion_requires_new_review") is not True: raise ValueError("ML shadow must be research-only, execution-disabled, and review-gated")
    registry=json.loads(registry_path.read_text()); meta=next((m for m in registry["models"] if m.get("model_id")==config["model_id"]),None)
    if not meta: raise ValueError(f"Model not registered: {config['model_id']}")
    path=artifact_dir/meta["artifact"]; checksum=hashlib.sha256(path.read_bytes()).hexdigest()
    if checksum!=meta["sha256"]: raise ValueError("ML confidence artifact checksum mismatch")
    return config,meta,joblib.load(path)


def evaluate_ml_shadow(frame,cutoffs,config,meta,model):
    prepared=prepare_breakout_feature_frame(frame,cutoffs); boundary=pd.Timestamp(config["accept_signals_after_utc"]); candidates=prepared[prepared.candidate&(prepared.timestamp>boundary)].copy(); encoded=pd.get_dummies(candidates[["symbol"]+FEATURES],columns=["symbol"],dtype=float).reindex(columns=meta["feature_names"],fill_value=0)
    probabilities=model.predict_proba(encoded)[:,1] if len(encoded) else [] ; rows=[]
    for (_,row),probability in zip(candidates.iterrows(),probabilities):
        allowed=float(probability)>=config["probability_threshold"]; rows.append({"signal_id":f"{config['candidate_id']}:{row.symbol}:{pd.Timestamp(row.timestamp).isoformat()}","signal_timestamp":pd.Timestamp(row.timestamp).isoformat(),"planned_entry_timestamp":pd.Timestamp(row.next_timestamp).isoformat(),"symbol":row.symbol,"confidence":float(probability),"threshold":config["probability_threshold"],"decision":"allowed" if allowed else "rejected"})
    allowed=sum(r["decision"]=="allowed" for r in rows); return {"schema_version":1,"candidate_id":config["candidate_id"],"model_id":config["model_id"],"model_production_eligible":meta["training_metadata"].get("production_eligible",False),"research_only":True,"execution_enabled":False,"automatic_promotion_enabled":False,"threshold":config["probability_threshold"],"scored_candidates":len(rows),"allowed_candidates":allowed,"rejected_candidates":len(rows)-allowed,"minimum_sample_reached":len(rows)>=config["minimum_fresh_scored_candidates"],"comparison_required_against_unfiltered_shadow":True,"signals":rows}


def save_ml_shadow(state,path:Path): path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(state,indent=2)+"\n")
