import json
from pathlib import Path
import pytest
from app.models.breakout_ml_shadow import load_ml_shadow

def test_ml_shadow_refuses_execution_enabled_config(tmp_path):
    config=tmp_path/"config.json"; config.write_text(json.dumps({"execution_enabled":True,"research_only":True,"promotion_requires_new_review":True}))
    with pytest.raises(ValueError): load_ml_shadow(config,tmp_path/"registry.json",tmp_path)
