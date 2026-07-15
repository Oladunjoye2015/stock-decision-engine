from datetime import datetime, timedelta, timezone

import pytest
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.compliance.approval_state import validate_live_approval
from app.compliance.trade_the_pool_rules import policy_state, validate_planned_exit
from app.config import Settings
from app.core.exceptions import SignalStackNotConfiguredError
from app.core.rate_limit import RollingRateLimiter
from app.core.retry_policy import retry_delay
from app.database.engine import Base
from app.execution.signalstack_queue import SignalStackRequestQueue
from app.execution.signalstack_schemas import SignalStackWebhookPayload, format_signalstack_payload
from app.execution.signalstack_transport import SignalStackTestTransport
from app.analysis.breakout_demo_gate import evaluate as evaluate_breakout_demo
from app.schemas.signals import SignalIn
from app.ai.external_reviewer import OpenAITradeReviewer
from app.analysis.decision_scorecard import build as build_scorecard
from app.market_data.volume_validation import validate_previous_minute_volume


def test_rate_limit_caps_two_and_spaces_requests():
    now = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
    limiter = RollingRateLimiter(99, 1, clock=lambda: now)
    assert limiter.evaluate([now-timedelta(seconds=31)]).allowed
    blocked = limiter.evaluate([now-timedelta(seconds=31), now-timedelta(seconds=10)])
    assert not blocked.allowed and blocked.sent_last_minute == 2 and blocked.retry_after_seconds >= 20


def test_queue_is_idempotent_prioritizes_exits_and_fails_on_overflow():
    engine = create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine)
    settings = Settings(signalstack_queue_enabled=True, signalstack_max_queue_size=2)
    with Session(engine) as db:
        queue = SignalStackRequestQueue(settings)
        entry = queue.enqueue(db, "t1", {"x": 1}, "same", "entry")
        assert queue.enqueue(db, "t1", {"x": 2}, "same", "entry").request_id == entry.request_id
        exit_request = queue.enqueue(db, "t2", {"x": 3}, "exit", "exit")
        assert queue.list(db)[0].request_id == exit_request.request_id
        with pytest.raises(SignalStackNotConfiguredError): queue.enqueue(db, "t3", {}, "overflow")


def test_volume_rule_missing_stale_and_valid():
    now = datetime.now(timezone.utc)
    assert not validate_previous_minute_volume(None, None, 1)["passed"]
    assert not validate_previous_minute_volume(1000, now-timedelta(minutes=10), 1)["passed"]
    valid = validate_previous_minute_volume(1000, now, 50)
    assert valid["passed"] and valid["maximum_shares_allowed"] == 50


def test_30_second_and_ten_cent_rules():
    settings = Settings()
    start = datetime.now(timezone.utc)
    assert not validate_planned_exit(start, start+timedelta(seconds=20), 100, 100.05, settings)["passed"]
    assert validate_planned_exit(start, start+timedelta(seconds=31), 100, 100.10, settings)["passed"]


def test_approval_revocation_and_policy_staleness_are_configurable():
    revoked = Settings(signalstack_written_approval_confirmed=False)
    assert not validate_live_approval(revoked)["passed"]
    stale = Settings(ttp_account_program="evaluation", ttp_rule_version="2026-01", ttp_rule_last_verified_at=datetime.now(timezone.utc)-timedelta(days=31), ttp_daily_pause_threshold_usd=100, ttp_maximum_loss_limit_usd=500)
    assert policy_state(stale)["stale"]


def test_placeholder_policy_timestamp_fails_closed_without_crashing_settings():
    settings=Settings(ttp_rule_last_verified_at="<current ISO timestamp>")
    assert settings.ttp_rule_last_verified_at is None
    assert "rule_last_verified_at" in policy_state(settings)["missing"]


def test_retry_is_bounded_and_never_rapid():
    assert retry_delay(0, True, 2, 1) == 30
    assert retry_delay(1, True, 2, 1) == 60
    assert retry_delay(2, True, 2, 1) is None


def test_confirmed_demo_payload_is_exact_and_strict():
    assert format_signalstack_payload(" aapl ", 1, "buy") == {"symbol": "AAPL", "quantity": 1, "action": "buy"}
    with pytest.raises(ValueError):
        SignalStackWebhookPayload(symbol="AAPL", quantity=0, action="buy")
    with pytest.raises(ValueError):
        SignalStackWebhookPayload(symbol="AAPL", quantity=1, action="short")
    with pytest.raises(ValueError):
        SignalStackWebhookPayload(symbol="AAPL", quantity=1, action="buy", price=100)


def test_transport_refuses_live_and_sends_only_explicit_test_webhook():
    payload=SignalStackWebhookPayload(symbol="AAPL",quantity=1,action="buy")
    live=Settings(signalstack_webhook_url="https://example.test/hook",signalstack_webhook_type="production",signalstack_test_transport_enabled=True)
    with pytest.raises(SignalStackNotConfiguredError): SignalStackTestTransport(live).send(payload)

    def handler(request):
        assert request.url == "https://example.test/hook"
        assert request.content == b'{"symbol":"AAPL","quantity":1,"action":"buy"}'
        return httpx.Response(200,json={"ok":True})
    settings=Settings(signalstack_webhook_url="https://example.test/hook",signalstack_webhook_type="test",signalstack_test_transport_enabled=True)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result=SignalStackTestTransport(settings,client).send(payload)
    assert result["sent"] and result["test_only"] and result["status_code"]==200


def test_frozen_breakout_demo_gate_is_explicit_and_fail_closed(fresh_signal):
    signal=SignalIn.model_validate({**fresh_signal,"strategy":"breakout-medium-high-vol-shadow-v1",
        "indicators":{**fresh_signal["indicators"],"prior_high20":100,"adx":25,"atr_pct":.01},
        "external_metadata":{"bar_confirmed":True}})
    assert evaluate_breakout_demo(signal,True)["passed"]
    assert not evaluate_breakout_demo(signal,False)["passed"]
    assert not evaluate_breakout_demo(signal.model_copy(update={"close":99}),True)["passed"]


def test_external_ai_reviewer_is_veto_only_and_fails_closed():
    disabled=OpenAITradeReviewer(Settings()).review({})
    assert disabled["passed"] and not disabled["enabled"]
    missing=OpenAITradeReviewer(Settings(external_ai_review_enabled=True)).review({})
    assert not missing["passed"] and missing["fail_closed"]
    output={"decision":"allow","viability_score":82,"confidence":.8,"reason":"aligned","reasons":["market supportive"],"primary_risks":[],"context_alignment":"supportive"}
    def handler(request):
        body=request.read().decode(); assert "trade_viability_review" in body
        return httpx.Response(200,json={"output":[{"content":[{"type":"output_text","text":__import__("json").dumps(output)}]}]})
    settings=Settings(external_ai_review_enabled=True,openai_api_key="test-key")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result=OpenAITradeReviewer(settings,client).review({"technical":"passed"})
    assert result["passed"] and result["confidence"]==.8


def test_decision_scorecard_is_weighted_but_cannot_override_hard_failures():
    passed={"passed":True}; context={"complete":True,"benchmarks_available":True,"benchmark_support":True}
    score=build_scorecard(breakout={"applicable":True,"passed":True},technical={"passed":True,"score":80},market_context=context,
        timeframe=passed,regime=passed,news=passed,noise=passed,risk=passed,compliance=passed)
    assert score["score"]==97 and not score["hard_failures"] and score["advisory_only"]
    blocked=build_scorecard(breakout={"applicable":True,"passed":True},technical={"passed":True,"score":100},market_context=context,
        timeframe=passed,regime=passed,news={"passed":False},noise=passed,risk=passed,compliance=passed)
    assert "news" in blocked["hard_failures"] and blocked["score"]==90
