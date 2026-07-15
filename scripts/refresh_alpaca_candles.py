#!/usr/bin/env python3
"""Incrementally refresh local research candles from Alpaca market data only."""
import argparse,json,os,sys,time
from pathlib import Path

import httpx
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

SYMBOLS=("AAPL","AMD","AMZN","AVGO","BABA","GOOG","META","MSFT","NVDA","QQQ","SPY","TSLA")
TIMEFRAMES={
    "15Min":{"output":Path("data/candles_15min.csv"),"overlap":pd.to_timedelta(5,unit="D"),"bootstrap":"2022-01-01","adjustment":"raw","regular":True},
    "1Hour":{"output":Path("data/candles_60min.csv"),"overlap":pd.to_timedelta(10,unit="D"),"bootstrap":"2022-01-01","adjustment":"raw","regular":True},
    "1Day":{"output":Path("data/candles_1day.csv"),"overlap":pd.to_timedelta(45,unit="D"),"bootstrap":"2018-01-01","adjustment":"split","regular":False},
}


def load_env(path=Path(".env")):
    if not path.exists(): return
    for line in path.read_text().splitlines():
        line=line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        key,value=line.split("=",1); key=key.strip(); value=value.strip().strip('"').strip("'")
        if not os.environ.get(key): os.environ[key]=value


def credentials():
    key=(os.getenv("ALPACA_API_KEY") or os.getenv("APCA_API_KEY_ID") or "").strip(); secret=(os.getenv("ALPACA_API_SECRET") or os.getenv("APCA_API_SECRET_KEY") or "").strip()
    if not key or not secret: raise RuntimeError("Missing ALPACA_API_KEY or ALPACA_API_SECRET in .env")
    return key,secret


def validate_bars(frame,regular_hours):
    if frame.empty: return frame
    x=frame.copy(); x["timestamp"]=pd.to_datetime(x.timestamp,utc=True,errors="coerce")
    for c in ("open","high","low","close","volume"): x[c]=pd.to_numeric(x[c],errors="coerce")
    x=x.dropna(subset=["timestamp","symbol","open","high","low","close","volume"]); valid=(x.high>=x[["open","close","low"]].max(axis=1))&(x.low<=x[["open","close","high"]].min(axis=1))&(x[["open","high","low","close","volume"]]>=0).all(axis=1); x=x[valid]
    if regular_hours:
        local=x.timestamp.dt.tz_convert("America/New_York"); minutes=local.dt.hour*60+local.dt.minute; x=x[(local.dt.dayofweek<5)&(minutes>=570)&(minutes<960)]
    x["data_provider"]="alpaca_market_data_api"; return x[["timestamp","symbol","data_provider","open","high","low","close","volume"]].drop_duplicates(["symbol","timestamp"],keep="last").sort_values(["timestamp","symbol"])


def merge_bars(existing,new):
    frames=[frame for frame in (existing,new) if not frame.empty and not frame.isna().all().all()]
    if not frames: return existing.copy()
    combined=pd.concat(frames,ignore_index=True); combined["timestamp"]=pd.to_datetime(combined.timestamp,utc=True); return combined.drop_duplicates(["symbol","timestamp"],keep="last").sort_values(["timestamp","symbol"]).reset_index(drop=True)


def progress(message):
    print(f"[market-refresh] {message}",flush=True)


def fetch_symbol(client,base_url,headers,symbol,timeframe,start,end,feed,adjustment,sleep_seconds):
    params={"start":start.isoformat(),"end":end.isoformat(),"timeframe":timeframe,"adjustment":adjustment,"feed":feed,"limit":10000,"sort":"asc"}; rows=[]; token=None
    while True:
        if token: params["page_token"]=token
        response=None
        for attempt in range(4):
            response=client.get(f"{base_url}/v2/stocks/{symbol}/bars",headers=headers,params=params)
            if response.status_code!=429: break
            time.sleep(max(float(response.headers.get("Retry-After","2")),2**attempt))
        response.raise_for_status(); payload=response.json(); page=payload.get("bars") or []
        if not isinstance(page,list): raise RuntimeError(f"Unexpected Alpaca bars response for {symbol} {timeframe}")
        rows.extend(page); token=payload.get("next_page_token")
        if not token: break
        time.sleep(max(0,sleep_seconds))
    if not rows: return pd.DataFrame()
    x=pd.DataFrame(rows).rename(columns={"t":"timestamp","o":"open","h":"high","l":"low","c":"close","v":"volume"}); x["symbol"]=symbol; return x


def atomic_csv(frame,path):
    path.parent.mkdir(parents=True,exist_ok=True); temporary=path.with_suffix(path.suffix+".tmp"); frame.to_csv(temporary,index=False); os.replace(temporary,path)


def refresh(timeframes,symbols,end,sleep_seconds=.25,storage="files"):
    if storage not in {"files","database"}: raise ValueError("storage must be files or database")
    if storage=="database":
        from app.database.runtime_store import load_candles,save_runtime_state,upsert_candles
    load_env(); key,secret=credentials(); base=os.getenv("ALPACA_DATA_BASE_URL","https://data.alpaca.markets").rstrip("/"); feed=os.getenv("ALPACA_DATA_FEED","iex").lower(); headers={"APCA-API-KEY-ID":key,"APCA-API-SECRET-KEY":secret,"Accept":"application/json"}; results=[]
    with httpx.Client(timeout=45) as client:
        for timeframe in timeframes:
            config=TIMEFRAMES[timeframe]; path=config["output"]
            progress(f"starting {timeframe}")
            existing=load_candles(timeframe) if storage=="database" else (pd.read_csv(path) if path.exists() else pd.DataFrame(columns=["timestamp","symbol","data_provider","open","high","low","close","volume"]))
            existing["timestamp"]=pd.to_datetime(existing.timestamp,utc=True)
            latest=existing.timestamp.max() if len(existing) else pd.NaT; start=latest-config["overlap"] if pd.notna(latest) else pd.Timestamp(config["bootstrap"],tz="UTC"); frames=[]; failures=[]
            for symbol in symbols:
                try:
                    frame=fetch_symbol(client,base,headers,symbol,timeframe,start,end,feed,config["adjustment"],sleep_seconds); frames.append(frame); progress(f"downloaded {timeframe} {symbol}: {len(frame)} rows")
                except Exception as exc: failures.append({"symbol":symbol,"error":str(exc)})
            downloaded=validate_bars(pd.concat(frames,ignore_index=True) if frames else pd.DataFrame(),config["regular"])
            if failures: raise RuntimeError(f"{timeframe} refresh aborted; failures={failures}")
            merged=merge_bars(existing,downloaded)
            if storage=="database":
                progress(f"upserting {timeframe}: {len(downloaded)} rows"); upsert_candles(downloaded,timeframe)
            else: atomic_csv(merged,path)
            results.append({"timeframe":timeframe,"storage":storage,"output":str(path) if storage=="files" else "market_candles","downloaded_rows":len(downloaded),"total_rows":len(merged),"first":str(merged.timestamp.min()),"last":str(merged.timestamp.max()),"symbols":int(merged.symbol.nunique())})
            progress(f"completed {timeframe}: {len(merged)} total rows")
    manifest={"generated_at_utc":pd.Timestamp.now(tz="UTC").isoformat(),"feed":feed,"market_data_base_url":base,"storage":storage,"results":results}
    if storage=="database": save_runtime_state("alpaca_refresh_manifest",manifest)
    else: Path("data/alpaca_refresh_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    return manifest


if __name__=="__main__":
    p=argparse.ArgumentParser(description="Incrementally update candles from Alpaca's market-data API only."); p.add_argument("--timeframes",default="15Min,1Hour,1Day"); p.add_argument("--symbols",default=",".join(SYMBOLS)); p.add_argument("--end",default=pd.Timestamp.now(tz="UTC").isoformat()); p.add_argument("--sleep",type=float,default=.25); p.add_argument("--storage",choices=("files","database"),default=os.getenv("RUNTIME_STORAGE","files")); a=p.parse_args(); requested=[x.strip() for x in a.timeframes.split(",") if x.strip()]; invalid=set(requested)-set(TIMEFRAMES)
    if invalid: raise SystemExit(f"Unsupported timeframes: {sorted(invalid)}")
    print(json.dumps(refresh(requested,[x.strip().upper() for x in a.symbols.split(",") if x.strip()],pd.Timestamp(a.end),a.sleep,a.storage),indent=2))
