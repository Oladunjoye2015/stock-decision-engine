#!/usr/bin/env python3
import json,sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.database.engine import engine
from app.scanning.hourly_breakout import scan

if __name__=="__main__":
    try: print(json.dumps(scan(get_settings()),indent=2),flush=True)
    finally: engine.dispose()
    print("[hourly-scanner] completed; exiting",flush=True)
