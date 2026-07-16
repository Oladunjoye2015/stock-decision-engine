from __future__ import annotations

import httpx
import pandas as pd


class AlpacaCandleClient:
    """Market-data-only client. It has no account, position, or order methods."""

    def __init__(self, settings, client: httpx.Client | None = None):
        self.settings=settings; self.client=client

    def recent(self, symbol: str, end, timeframe: str = "1Hour", days: int = 90, limit: int = 250, regular_hours: bool = True) -> pd.DataFrame:
        if not self.settings.alpaca_api_key or not self.settings.alpaca_api_secret:
            raise RuntimeError("Alpaca market-data credentials are missing")
        end=pd.Timestamp(end)
        if end.tzinfo is None: end=end.tz_localize("UTC")
        params={"start":(end-pd.to_timedelta(days,unit="D")).isoformat(),"end":end.isoformat(),"timeframe":timeframe,
                "adjustment":"raw","feed":self.settings.alpaca_data_feed,"limit":10000,"sort":"asc"}
        headers={"APCA-API-KEY-ID":self.settings.alpaca_api_key,"APCA-API-SECRET-KEY":self.settings.alpaca_api_secret}
        owns=self.client is None; client=self.client or httpx.Client(timeout=15); rows=[]; token=None
        try:
            while True:
                if token: params["page_token"]=token
                response=client.get(f"{self.settings.alpaca_data_base_url.rstrip('/')}/v2/stocks/{symbol}/bars",headers=headers,params=params)
                response.raise_for_status(); data=response.json(); rows.extend(data.get("bars") or []); token=data.get("next_page_token")
                if not token: break
        finally:
            if owns: client.close()
        frame=pd.DataFrame(rows).rename(columns={"t":"timestamp","o":"open","h":"high","l":"low","c":"close","v":"volume"})
        if frame.empty: return pd.DataFrame(columns=["timestamp","symbol","data_provider","open","high","low","close","volume"])
        frame["timestamp"]=pd.to_datetime(frame.timestamp,utc=True); frame["symbol"]=symbol; frame["data_provider"]="alpaca_market_data_api"
        if regular_hours:
            local=frame.timestamp.dt.tz_convert("America/New_York"); minutes=local.dt.hour*60+local.dt.minute
            frame=frame[(local.dt.dayofweek<5)&(minutes>=570)&(minutes<960)]
        return frame[["timestamp","symbol","data_provider","open","high","low","close","volume"]].drop_duplicates(["symbol","timestamp"],keep="last").tail(limit)

    def recent_hourly(self, symbol: str, end) -> pd.DataFrame:
        return self.recent(symbol,end,"1Hour",90,250,True)
