from datetime import datetime, timedelta, timezone


def test_health_and_compliance(client, headers):
    home = client.get("/", follow_redirects=False)
    assert home.status_code == 307 and home.headers["location"] == "/dashboard/"
    assert client.get("/health").status_code == 200
    compliance = client.get("/compliance/status").json()
    assert compliance["alpaca_connectivity"] == "absent"
    assert compliance["direct_trade_the_pool"] == "prohibited"
    assert client.get("/compliance/approval").json()["conditional_and_revocable"] is True
    assert client.get("/signalstack/status").json()["outbound_transport_enabled"] is False
    assert client.post("/signalstack/test-configuration",headers=headers).json()["outbound_request_made"] is False
    shadow = client.get("/shadow/status").json()
    assert shadow["execution_enabled"] is False and shadow["automatic_promotion_enabled"] is False
    dashboard = client.get("/dashboard/")
    assert dashboard.status_code == 200 and "Stock Decision Engine" in dashboard.text


def test_webhook_authentication(client, fresh_signal):
    body = {**fresh_signal, "signal_id": "unauthorized"}
    assert client.post("/signals", json=body).status_code == 401
    tradingview={**fresh_signal,"webhook_token":"wrong-token-value"}
    assert client.post("/tradingview/signals",json=tradingview).status_code==401


def test_non_primary_timeframes_cannot_trade(client, headers, fresh_signal):
    for tf in ("15Min", "5Min", "1Day"):
        body = {**fresh_signal, "signal_id": f"blocked-{tf}", "timeframe": tf}
        result = client.post("/signals", headers=headers, json=body).json()
        assert result["final_decision"] == "blocked"


def test_stale_and_idempotent_signals(client, headers, fresh_signal):
    stale = {**fresh_signal, "signal_id": "stale", "signal_time_utc": (datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()}
    assert client.post("/signals", headers=headers, json=stale).json()["final_decision"] == "blocked"
    assert client.post("/signals", headers=headers, json=stale).json()["idempotent"] is True


def test_gate_failure_skips_ai(client, headers, fresh_signal):
    body = {**fresh_signal, "signal_id": "bad-tech", "indicators": {"atr": 0, "rsi": 80, "ema20": 90, "ema50": 100}}
    result = client.post("/signals", headers=headers, json=body).json()
    decision = client.get(f"/decisions/{result['decision_id']}").json()
    assert result["final_decision"] == "blocked"
    assert "ai_review" not in decision["details"]


def test_news_and_noise_can_block(client, headers, fresh_signal):
    news = {**fresh_signal, "signal_id": "bad-news", "external_metadata": {"news": {"event_types": ["offering"]}}}
    assert client.post("/signals", headers=headers, json=news).json()["final_decision"] == "blocked"
    noise = {**fresh_signal, "signal_id": "bad-noise", "volume": 0, "indicators": {"atr": .01, "vol_ratio": .1}}
    assert client.post("/signals", headers=headers, json=noise).json()["final_decision"] == "blocked"


def test_paper_flow_has_no_external_order(client, headers, fresh_signal):
    assert client.post("/risk/reconcile", headers=headers, json={"realized_pnl": 0, "open_risk": 0, "trades_count": 0}).status_code == 200
    body = {**fresh_signal, "signal_id": "paper-flow", "signal_time_utc": datetime.now(timezone.utc).isoformat()}
    result = client.post("/signals", headers=headers, json=body).json()
    assert result["final_decision"] == "paper_submitted"
    accepted = client.post(f"/tickets/{result['ticket_id']}/accept", json={}).json()
    assert accepted["status"] == "paper_opened"
    closed = client.post(f"/tickets/{result['ticket_id']}/record-exit", json={"price": 105, "quantity": accepted["proposed_quantity"]}).json()
    assert closed["status"] == "paper_closed" and closed["realized_pnl"] > 0


def test_kill_switch_blocks_new_proposal(client, headers, fresh_signal):
    client.post("/risk/kill-switch", headers=headers, json={"reason": "test"})
    body = {**fresh_signal, "signal_id": "killed", "symbol": "MSFT", "signal_time_utc": datetime.now(timezone.utc).isoformat()}
    assert client.post("/signals", headers=headers, json=body).json()["final_decision"] == "blocked"
    client.post("/risk/kill-switch/reset", headers=headers, json={"reason": "done"})
