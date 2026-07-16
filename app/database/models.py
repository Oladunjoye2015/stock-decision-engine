from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time_utils import utc_now
from app.database.engine import Base


class TimestampMixin:
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class MarketCandle(Base):
    __tablename__ = "market_candles"
    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "timestamp_utc", name="uq_market_candle"),
        Index("ix_market_candles_timeframe_timestamp", "timeframe", "timestamp_utc"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(24), index=True)
    timeframe: Mapped[str] = mapped_column(String(16), index=True)
    timestamp_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    data_provider: Mapped[str] = mapped_column(String(64))
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float)


class RuntimeState(Base):
    __tablename__ = "runtime_states"
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    updated_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class SignalRecord(TimestampMixin, Base):
    __tablename__ = "signals"
    id: Mapped[int] = mapped_column(primary_key=True)
    signal_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    symbol: Mapped[str] = mapped_column(String(24), index=True)
    timeframe: Mapped[str] = mapped_column(String(24))
    signal_time_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="received")


class SignalClaim(TimestampMixin, Base):
    __tablename__ = "signal_claims"
    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_key: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    primary_signal_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(64))
    symbol: Mapped[str] = mapped_column(String(24), index=True)
    strategy: Mapped[str] = mapped_column(String(128))
    timeframe: Mapped[str] = mapped_column(String(24))
    canonical_bar_close_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class DecisionRecord(TimestampMixin, Base):
    __tablename__ = "signal_decisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    decision_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    signal_id: Mapped[str] = mapped_column(String(128), index=True)
    symbol: Mapped[str] = mapped_column(String(24))
    side: Mapped[str] = mapped_column(String(8))
    strategy: Mapped[str] = mapped_column(String(128))
    primary_timeframe: Mapped[str] = mapped_column(String(24))
    final_decision: Mapped[str] = mapped_column(String(32))
    execution_mode: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(JSON)


class TradeTicket(TimestampMixin, Base):
    __tablename__ = "trade_tickets"
    __table_args__ = (UniqueConstraint("decision_id", name="uq_ticket_decision"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    decision_id: Mapped[str] = mapped_column(String(64), index=True)
    signal_id: Mapped[str] = mapped_column(String(128), index=True)
    symbol: Mapped[str] = mapped_column(String(24), index=True)
    side: Mapped[str] = mapped_column(String(8))
    execution_mode: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), index=True)
    expires_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    proposed_entry_price: Mapped[float] = mapped_column(Float)
    proposed_stop_price: Mapped[float] = mapped_column(Float)
    proposed_target_price: Mapped[float] = mapped_column(Float)
    proposed_quantity: Mapped[int] = mapped_column(Integer)
    estimated_risk_usd: Mapped[float] = mapped_column(Float)
    estimated_reward_usd: Mapped[float] = mapped_column(Float)
    expected_movement_per_share: Mapped[float | None] = mapped_column(Float, nullable=True)
    reference_one_minute_volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    maximum_quantity_by_volume_rule: Mapped[int | None] = mapped_column(Integer, nullable=True)
    signalstack_request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    signalstack_idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    signalstack_response_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    actual_entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_entry_quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_entry_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_exit_quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fees: Mapped[float] = mapped_column(Float, default=0)
    realized_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ExecutionRecord(TimestampMixin, Base):
    __abstract__ = True
    id: Mapped[int] = mapped_column(primary_key=True)
    execution_id: Mapped[str] = mapped_column(String(64), unique=True)
    ticket_id: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(16))
    price: Mapped[float] = mapped_column(Float)
    quantity: Mapped[float] = mapped_column(Float)
    fees: Mapped[float] = mapped_column(Float, default=0)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ManualExecution(ExecutionRecord):
    __tablename__ = "manual_executions"


class PaperExecution(ExecutionRecord):
    __tablename__ = "paper_executions"


class Position(TimestampMixin, Base):
    __tablename__ = "positions"
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(24), index=True)
    side: Mapped[str] = mapped_column(String(8))
    quantity: Mapped[float] = mapped_column(Float)
    entry_price: Mapped[float] = mapped_column(Float)
    stop_price: Mapped[float] = mapped_column(Float)
    execution_mode: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="open")


class DailyRiskState(TimestampMixin, Base):
    __tablename__ = "daily_risk_state"
    id: Mapped[int] = mapped_column(primary_key=True)
    date_key: Mapped[str] = mapped_column(String(10), unique=True)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0)
    open_risk: Mapped[float] = mapped_column(Float, default=0)
    trades_count: Mapped[int] = mapped_column(Integer, default=0)
    reconciled: Mapped[bool] = mapped_column(Boolean, default=False)
    kill_switch: Mapped[bool] = mapped_column(Boolean, default=False)
    daily_pause: Mapped[bool] = mapped_column(Boolean, default=False)
    maximum_loss_buffer_reached: Mapped[bool] = mapped_column(Boolean, default=False)


class SignalStackRequest(TimestampMixin, Base):
    __tablename__ = "signalstack_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    ticket_id: Mapped[str] = mapped_column(String(64), index=True)
    request_type: Mapped[str] = mapped_column(String(32), default="entry")
    priority: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="")


class SignalStackResponse(TimestampMixin, Base):
    __tablename__ = "signalstack_responses"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class SignalStackQueue(TimestampMixin, Base):
    __tablename__ = "signalstack_queue"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    state: Mapped[str] = mapped_column(String(32), default="queued")
    reason: Mapped[str] = mapped_column(Text, default="")


class EventRecord(TimestampMixin):
    __abstract__ = True
    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), default="check")
    subject_id: Mapped[str] = mapped_column(String(128), default="", index=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ComplianceEvent(EventRecord, Base): __tablename__ = "compliance_events"
class AuditEvent(EventRecord, Base): __tablename__ = "audit_events"
class ModelPrediction(EventRecord, Base): __tablename__ = "model_predictions"
class AIReview(EventRecord, Base): __tablename__ = "ai_reviews"
class NewsCheck(EventRecord, Base): __tablename__ = "news_checks"
class NoiseCheck(EventRecord, Base): __tablename__ = "noise_checks"
class MarketRegime(EventRecord, Base): __tablename__ = "market_regimes"
class TimeframeConfirmation(EventRecord, Base): __tablename__ = "timeframe_confirmations"
class ApprovalRecord(EventRecord, Base): __tablename__ = "approval_records"
class PolicyVersion(EventRecord, Base): __tablename__ = "policy_versions"
class VolumeRuleCheck(EventRecord, Base): __tablename__ = "volume_rule_checks"
