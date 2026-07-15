from datetime import timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai.reviewer import StructuredAIReviewer
from app.ai.external_reviewer import OpenAITradeReviewer
from app.analysis import breakout_demo_gate, market_regime, news_filter, noise_filter, technical_gate, timeframe_alignment
from app.analysis.feature_engineering import build_features
from app.analysis.server_market_context import build_server_context
from app.analysis.decision_scorecard import build as build_scorecard
from app.compliance.audit import record
from app.compliance.trade_the_pool_rules import evaluate as evaluate_ttp_rules
from app.config import Settings, get_settings
from app.core.exceptions import ModelCompatibilityError, RiskCheckError
from app.core.security import authenticate_webhook
from app.core.time_utils import utc_now
from app.database.engine import get_db
from app.database.models import (AIReview, DecisionRecord, MarketRegime, ModelPrediction, NewsCheck,
                                 NoiseCheck, SignalRecord, TimeframeConfirmation, TradeTicket, VolumeRuleCheck)
from app.database.repositories import get_by, list_recent
from app.market_data.freshness import check as freshness_check
from app.market_data.finnhub import FinnhubClient, FinnhubError
from app.market_data.volume_validation import validate_previous_minute_volume
from app.models.predictor import predict
from app.models.registry import ModelRegistry
from app.notifications.service import NotificationService
from app.risk.daily_risk import check as daily_check, get_or_create
from app.risk.exposure import check as exposure_check
from app.risk.position_sizing import calculate
from app.execution.factory import get_adapter
from app.execution.signalstack_queue import SignalStackRequestQueue
from app.execution.signalstack_schemas import SignalStackWebhookPayload
from app.execution.signalstack_transport import send_and_record_test
from app.schemas.signals import SignalIn

router = APIRouter(prefix="/signals", tags=["signals"])


def _event(db, model, signal_id, event_type, data): db.add(model(subject_id=signal_id, event_type=event_type, data=data))


def _blocked(db, signal, settings, reason, details):
    decision = DecisionRecord(decision_id=str(uuid4()), signal_id=signal.signal_id, symbol=signal.symbol, side="short" if signal.side_hint in {"short", "sell"} else "long", strategy=signal.strategy, primary_timeframe=settings.primary_signal_timeframe, final_decision="blocked", execution_mode=settings.execution_mode, reason=reason, details=details)
    db.add(decision); db.commit(); db.refresh(decision)
    record(db, "decision_blocked", decision.decision_id, {"reason": reason, "signal_id": signal.signal_id})
    NotificationService(settings).send("blocked_proposal", {"decision_id": decision.decision_id, "reason": reason})
    return decision


def create_ticket(db, decision, settings):
    d = decision.details
    sizing = d["risk"]["sizing"]
    quantity = sizing["quantity"]
    entry, stop, target = d["prices"]["entry"], d["prices"]["stop"], d["prices"]["target"]
    volume = d.get("volume_rule", {})
    ticket = TradeTicket(ticket_id=str(uuid4()), decision_id=decision.decision_id, signal_id=decision.signal_id, symbol=decision.symbol, side=decision.side, execution_mode=settings.execution_mode, status="proposed", expires_at_utc=utc_now() + timedelta(seconds=settings.ticket_expiry_seconds), proposed_entry_price=entry, proposed_stop_price=stop, proposed_target_price=target, proposed_quantity=quantity, estimated_risk_usd=abs(entry-stop)*quantity, estimated_reward_usd=abs(target-entry)*quantity, expected_movement_per_share=abs(target-entry), reference_one_minute_volume=volume.get("reference_candle_volume"), maximum_quantity_by_volume_rule=volume.get("maximum_shares_allowed"), signalstack_idempotency_key=f"ticket:{decision.decision_id}" if settings.execution_mode == "signalstack" else None, details=d)
    db.add(ticket); decision.final_decision = "manual_ticket_created" if settings.execution_mode == "manual" else "paper_submitted" if settings.execution_mode == "paper" else "proposed"
    db.commit(); db.refresh(ticket); return ticket


@router.post("", dependencies=[Depends(authenticate_webhook)])
def receive(signal: SignalIn, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    return process_signal(signal, db, settings)


def process_signal(signal: SignalIn, db: Session, settings: Settings):
    existing = get_by(db, SignalRecord, signal_id=signal.signal_id)
    if existing:
        decision = get_by(db, DecisionRecord, signal_id=signal.signal_id)
        return {"idempotent": True, "signal_id": signal.signal_id, "decision_id": decision.decision_id if decision else None, "final_decision": decision.final_decision if decision else None}
    row = SignalRecord(signal_id=signal.signal_id, symbol=signal.symbol, timeframe=signal.timeframe, signal_time_utc=signal.signal_time_utc, payload=signal.model_dump(mode="json"))
    db.add(row)
    try: db.commit()
    except IntegrityError: db.rollback(); return {"idempotent": True, "signal_id": signal.signal_id}
    details = {}
    if settings.allowed_symbol_set and signal.symbol not in settings.allowed_symbol_set: return _response(_blocked(db, signal, settings, "symbol is not allowed", details))
    if signal.timeframe != settings.primary_signal_timeframe or not settings.allow_60min_signals: return _response(_blocked(db, signal, settings, "only 60Min signals may create decisions", details))
    fresh = freshness_check(signal.signal_time_utc, settings.signal_max_age_seconds); details["freshness"] = fresh
    if not fresh["passed"]: return _response(_blocked(db, signal, settings, fresh["reason"], details))
    server_context={"complete":False,"reason":"not required for this strategy"}
    if signal.strategy == "breakout-medium-high-vol-shadow-v1":
        try: server_context=build_server_context(signal,settings)
        except Exception as exc: server_context={"complete":False,"reason":f"server market context unavailable: {type(exc).__name__}"}
        details["server_market_context"]=server_context
        if not server_context.get("complete") or not server_context.get("benchmarks_available") or not server_context.get("benchmark_support"):
            return _response(_blocked(db,signal,settings,"server candle or benchmark context did not support the setup",details))
        primary=server_context["symbols"][signal.symbol]
        signal=signal.model_copy(update={"indicators":{**signal.indicators,**{key:primary[key] for key in ("prior_high20","vol_ratio","adx","atr","atr_pct","rsi","ema20","ema50","ema200","macd_hist")}}})
    breakout_demo = breakout_demo_gate.evaluate(signal, settings.deterministic_breakout_demo_enabled); details["breakout_demo_gate"] = breakout_demo
    if signal.strategy == "breakout-medium-high-vol-shadow-v1" and not breakout_demo["passed"]:
        return _response(_blocked(db, signal, settings, breakout_demo["reason"], details))
    finnhub = {"provider": "finnhub", "news": None, "quote": None, "bid_ask": None, "available": False}
    if settings.finnhub_api_key and (settings.news_filter_enabled or settings.noise_filter_enabled):
        client = None
        try:
            client = FinnhubClient(settings.finnhub_api_key, settings.finnhub_base_url, settings.finnhub_timeout_seconds)
            snapshot = client.snapshot(signal.symbol, settings.finnhub_news_lookback_days, settings.finnhub_news_limit, settings.finnhub_use_bid_ask)
            finnhub.update(snapshot); finnhub["available"] = True
        except FinnhubError as exc:
            finnhub["error"] = str(exc)
            if settings.finnhub_fail_closed: return _response(_blocked(db, signal, settings, "Finnhub market data unavailable", {**details, "finnhub": finnhub}))
        finally:
            if client: client.close()
    elif settings.finnhub_fail_closed and (settings.news_filter_enabled or settings.noise_filter_enabled):
        return _response(_blocked(db, signal, settings, "FINNHUB_API_KEY is required by fail-closed policy", {**details, "finnhub": finnhub}))
    details["finnhub"] = finnhub
    regime = market_regime.evaluate(signal.higher_timeframe_context, settings.market_regime_enabled); details["market_regime"] = regime; _event(db, MarketRegime, signal.signal_id, "market_regime", regime)
    side = "short" if signal.side_hint in {"short", "sell"} else "long"
    align = timeframe_alignment.evaluate(side, signal.higher_timeframe_context, settings.neutral_higher_timeframe_allowed, settings.timeframe_alignment_enabled); details["timeframe_alignment"] = align; _event(db, TimeframeConfirmation, signal.signal_id, "timeframe_alignment", align)
    tech = technical_gate.evaluate(signal, settings.technical_gate_enabled).dict(); details["technical_gate"] = tech
    noise = noise_filter.evaluate(signal, settings.noise_filter_enabled, finnhub.get("quote"), finnhub.get("bid_ask")); details["noise_filter"] = noise; _event(db, NoiseCheck, signal.signal_id, "noise_check", noise)
    news = news_filter.evaluate(signal.external_metadata, settings.news_filter_enabled, finnhub.get("news")); details["news_filter"] = news; _event(db, NewsCheck, signal.signal_id, "news_check", news)
    db.commit()
    failed = [name for name, result in (("market regime", regime), ("timeframe alignment", align), ("technical gate", tech), ("noise filter", noise), ("news filter", news)) if not result["passed"]]
    if failed: return _response(_blocked(db, signal, settings, "deterministic gate failed: " + ", ".join(failed), details))
    try:
        entry = signal.current_price
        atr = float(signal.indicators.get("atr") or max(signal.high-signal.low, entry*.01))
        stop = signal.stop_hint or (entry-atr if side == "long" else entry+atr)
        target = signal.take_profit_hint or (entry+atr*settings.min_reward_risk if side == "long" else entry-atr*settings.min_reward_risk)
        rr = abs(target-entry) / abs(entry-stop)
        if breakout_demo["passed"]:
            prediction = {"model_id":"deterministic-breakout-demo","probability":.5,"margin":0,
                          "research_only":True,"production_model_used":False,
                          "reason":"Frozen breakout is demo-eligible; disabled ML remains comparison-only."}
        else:
            entry_model = ModelRegistry(settings).resolve(signal.symbol, signal.timeframe)
            features = build_features(signal, entry_model["feature_names"])
            prediction = predict(entry_model, settings, signal.symbol, signal.timeframe, features)
        details["model"] = prediction; _event(db, ModelPrediction, signal.signal_id, "prediction", prediction)
        preliminary = calculate(entry, stop, settings.buying_power_usd, settings.account_size_usd, settings.max_risk_per_trade_usd, settings.max_symbol_exposure_pct)
        volume_check = validate_previous_minute_volume(signal.external_metadata.get("previous_one_minute_volume"), signal.external_metadata.get("previous_one_minute_candle_time"), 1, settings.ttp_max_position_volume_pct) if settings.execution_mode == "signalstack" else {"passed": True, "reason": "not required for local execution modes"}
        sizing = calculate(entry, stop, settings.buying_power_usd, settings.account_size_usd, settings.max_risk_per_trade_usd, settings.max_symbol_exposure_pct, volume_cap=volume_check.get("maximum_shares_allowed") if settings.execution_mode == "signalstack" and volume_check.get("passed") else None)
        if settings.execution_mode == "signalstack":
            volume_check["proposed_shares"] = sizing["quantity"]; volume_check["passed"] = volume_check["maximum_shares_allowed"] >= sizing["quantity"] >= 1; volume_check["reason"] = "passed" if volume_check["passed"] else volume_check["reason"]
        details["volume_rule"] = volume_check; _event(db, VolumeRuleCheck, signal.signal_id, "volume_rule", volume_check)
        daily_state = get_or_create(db, settings); risk = daily_check(daily_state, settings, sizing["estimated_risk_usd"])
        exposure = exposure_check(db, settings, signal.symbol)
        if side == "short" and not settings.allow_shorts: risk = {"passed": False, "reason": "short sales are disabled"}
        if rr < settings.min_reward_risk: risk = {"passed": False, "reason": "minimum reward/risk not met"}
        rate_state = SignalStackRequestQueue(settings).rate_state(db) if settings.execution_mode == "signalstack" else {"allowed": True, "reason": "local mode", "sent_last_minute": 0, "retry_after_seconds": 0}
        compliance = evaluate_ttp_rules(settings, side, entry, target, daily_state, volume_check, rate_state, settings.execution_mode)
        details["prices"] = {"entry": entry, "stop": stop, "target": target, "reward_risk_ratio": rr}; details["risk"] = {"passed": risk["passed"] and exposure["passed"], "reason": f"{risk['reason']}; {exposure['reason']}", "sizing": sizing}; details["compliance"] = compliance; details["request_rate_state"] = rate_state
    except (ModelCompatibilityError, RiskCheckError) as exc: return _response(_blocked(db, signal, settings, str(exc), details))
    if not details["risk"]["passed"]: return _response(_blocked(db, signal, settings, details["risk"]["reason"], details))
    review_context = {"symbol": signal.symbol, "side": side, "primary_timeframe": signal.timeframe, "model_probability": prediction["probability"], "model_margin": prediction["margin"], "technical_gate": tech, "timeframe_alignment": align, "market_regime": regime, "volatility_state": tech["volatility_state"], "news_status": news, "noise_status": noise, "proposed_entry": entry, "proposed_stop": stop, "proposed_target": target, "reward_risk_ratio": rr, "recent_ohlcv": signal.recent_ohlcv, "trade_the_pool_rule_state": compliance, "current_request_rate_state": rate_state}
    review = StructuredAIReviewer().review(review_context).model_dump() if settings.ai_review_enabled else {"approved": True, "reason": "disabled", "confidence": 0, "primary_risks": [], "invalidation_condition": "", "recommended_action": "propose"}
    details["ai_review"] = review; _event(db, AIReview, signal.signal_id, "ai_review", review); db.commit()
    if not review["approved"]: return _response(_blocked(db, signal, settings, "AI review blocked proposal", details))
    if not compliance["passed"]: return _response(_blocked(db, signal, settings, compliance["reason"], details))
    scorecard=build_scorecard(breakout=breakout_demo,technical=tech,market_context=server_context,timeframe=align,
        regime=regime,news=news,noise=noise,risk=details["risk"],compliance=compliance)
    details["decision_scorecard"]=scorecard
    external_evidence={"signal":{"id":signal.signal_id,"symbol":signal.symbol,"strategy":signal.strategy,"time":signal.signal_time_utc.isoformat()},
        "breakout":breakout_demo,"server_market_context":server_context,"technical_gate":tech,"market_regime":regime,
        "timeframe_alignment":align,"news_filter":news,"noise_filter":noise,"risk":details["risk"],
        "prices":details["prices"],"model_research_context":prediction,"trade_the_pool_compliance":compliance,
        "deterministic_scorecard":scorecard}
    external_review=OpenAITradeReviewer(settings).review(external_evidence); details["external_ai_review"]=external_review
    _event(db,AIReview,signal.signal_id,"external_ai_veto_review",external_review); db.commit()
    if not external_review["passed"]: return _response(_blocked(db,signal,settings,"external AI viability review blocked proposal",details))
    decision = DecisionRecord(decision_id=str(uuid4()), signal_id=signal.signal_id, symbol=signal.symbol, side=side, strategy=signal.strategy, primary_timeframe=signal.timeframe, final_decision="proposed", execution_mode=settings.execution_mode, reason="all checks passed", details=details)
    db.add(decision); db.commit(); db.refresh(decision)
    ticket = create_ticket(db, decision, settings); record(db, "ticket_created", ticket.ticket_id, {"mode": settings.execution_mode}); NotificationService(settings).send(f"approved_{settings.execution_mode}_proposal", {"ticket_id": ticket.ticket_id})
    if settings.execution_mode == "signalstack":
        ticket = get_adapter(settings).accept(db, ticket); decision.final_decision = "signalstack_queued"; db.commit(); NotificationService(settings).send("signalstack_order_intent_queued", {"ticket_id": ticket.ticket_id, "request_id": ticket.signalstack_request_id, "status": ticket.status})
    demo_delivery=None
    if breakout_demo["passed"] and settings.demo_signalstack_routing_enabled:
        try:
            demo_delivery=send_and_record_test(db,settings,SignalStackWebhookPayload(symbol=signal.symbol,quantity=ticket.proposed_quantity,action="buy"))
            decision.final_decision="demo_test_sent"; ticket.status="signalstack_test_sent"; db.commit()
        except Exception as exc:
            demo_delivery={"sent":False,"test_only":True,"error":type(exc).__name__}; record(db,"signalstack_demo_send_failed",ticket.ticket_id,demo_delivery,True)
    return {**_response(decision), "ticket_id": ticket.ticket_id, "ticket_status": ticket.status, "demo_delivery":demo_delivery}


def _response(decision): return {"signal_id": decision.signal_id, "decision_id": decision.decision_id, "final_decision": decision.final_decision, "reason": decision.reason}


@router.get("")
def list_signals(limit: int = 100, db: Session = Depends(get_db)): return [{"signal_id": x.signal_id, "symbol": x.symbol, "timeframe": x.timeframe, "status": x.status, "created_at_utc": x.created_at_utc} for x in list_recent(db, SignalRecord, limit)]


@router.get("/{signal_id}")
def get_signal(signal_id: str, db: Session = Depends(get_db)):
    x = get_by(db, SignalRecord, signal_id=signal_id)
    if not x: raise HTTPException(404, "Signal not found")
    return {"signal_id": x.signal_id, "symbol": x.symbol, "timeframe": x.timeframe, "status": x.status, "payload": x.payload, "created_at_utc": x.created_at_utc}
