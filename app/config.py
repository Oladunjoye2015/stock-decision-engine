from functools import lru_cache
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_name: str = "stock-decision-engine"
    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite:///./stock_decision_engine.db"
    runtime_storage: Literal["files", "database"] = "files"
    webhook_passphrase: str = ""
    execution_mode: Literal["paper", "manual", "signalstack"] = "paper"

    primary_signal_timeframe: str = "60Min"
    higher_timeframes: str = "4Hour,1Day"
    entry_confirmation_timeframe: str = "15Min"
    execution_check_timeframe: str = "5Min"
    allow_60min_signals: bool = True
    allow_15min_signals: bool = False
    allow_5min_signals: bool = False
    allow_daily_signals: bool = False

    account_size_usd: float = 50_000
    buying_power_usd: float = 50_000
    max_risk_per_trade_usd: float = 75
    max_daily_loss_usd: float = 350
    max_aggregate_open_risk_usd: float = 150
    max_open_positions: int = 1
    max_trades_per_day: int = 2
    max_symbol_exposure_pct: float = 20
    max_sector_exposure_pct: float = 35
    allow_longs: bool = True
    allow_shorts: bool = False
    require_stop_loss: bool = True
    min_reward_risk: float = 1.5
    signal_max_age_seconds: int = 120
    ticket_expiry_seconds: int = 300

    technical_gate_enabled: bool = True
    news_filter_enabled: bool = True
    noise_filter_enabled: bool = True
    market_regime_enabled: bool = True
    timeframe_alignment_enabled: bool = True
    ai_review_enabled: bool = True
    neutral_higher_timeframe_allowed: bool = True
    execution_quality_check_enabled: bool = False

    model_registry_path: Path = Path("model_artifacts/registry.json")
    model_artifact_dir: Path = Path("model_artifacts/artifacts")
    paper_slippage_bps: float = 5
    paper_commission_per_share: float = 0
    paper_fill_delay_seconds: int = 0
    paper_partial_fill_pct: float = 100
    paper_simulate_rejection: bool = False
    daily_reconciliation_required: bool = True
    kill_switch_enabled: bool = False

    signalstack_enabled: bool = False
    signalstack_written_approval_confirmed: bool = True
    signalstack_account_program_approved: bool = True
    signalstack_official_docs_available: bool = False
    signalstack_credentials_configured: bool = False
    signalstack_live_execution_allowed: bool = False
    signalstack_max_requests_per_minute: int = 2
    signalstack_min_request_interval_seconds: int = 30
    signalstack_queue_enabled: bool = True
    signalstack_max_queue_size: int = 100
    signalstack_retry_enabled: bool = True
    signalstack_max_retries: int = 2
    signalstack_retry_base_seconds: int = 30
    signalstack_api_key: str = ""
    signalstack_webhook_url: str = ""
    signalstack_account_reference: str = ""
    signalstack_webhook_type: Literal["disabled", "test", "production"] = "disabled"
    signalstack_test_transport_enabled: bool = False
    demo_signalstack_routing_enabled: bool = False
    deterministic_breakout_demo_enabled: bool = False
    tradingview_webhook_token: str = ""

    ttp_account_program: str = ""
    ttp_account_size_usd: float = 50_000
    ttp_buying_power_usd: float = 50_000
    ttp_daily_pause_enabled: bool = True
    ttp_daily_pause_threshold_usd: float | None = None
    ttp_maximum_loss_limit_usd: float | None = None
    ttp_min_hold_seconds: int = 30
    ttp_min_profit_movement_per_share_usd: float = .10
    ttp_max_position_volume_pct: float = 5
    ttp_max_open_positions: int = 1
    ttp_max_trades_per_day: int = 2
    ttp_max_symbol_exposure_pct: float = 20
    ttp_max_sector_exposure_pct: float = 35
    ttp_allow_longs: bool = True
    ttp_allow_shorts: bool = False
    ttp_rule_version: str = ""
    ttp_rule_last_verified_at: datetime | None = None
    ttp_policy_stale_after_days: int = 30

    allowed_symbols: str = ""
    notification_log_path: Path = Path("logs/notifications.log")
    finnhub_api_key: str = ""
    finnhub_base_url: str = "https://finnhub.io/api/v1"
    finnhub_timeout_seconds: float = 10
    finnhub_news_lookback_days: int = 3
    finnhub_news_limit: int = 50
    finnhub_use_bid_ask: bool = False
    finnhub_fail_closed: bool = False

    @field_validator("execution_mode")
    @classmethod
    def supported_mode(cls, value: str) -> str:
        if value not in {"paper", "manual", "signalstack"}:
            raise ValueError("Unsupported execution mode; refusing to start")
        return value

    @field_validator("ttp_daily_pause_threshold_usd", "ttp_maximum_loss_limit_usd", "ttp_rule_last_verified_at", mode="before")
    @classmethod
    def empty_optional_values_are_unset(cls, value):
        text = "" if value is None else str(value).strip()
        return None if not text or (text.startswith("<") and text.endswith(">")) else value

    @property
    def allowed_symbol_set(self) -> set[str]:
        return {item.strip().upper() for item in self.allowed_symbols.split(",") if item.strip()}

    @property
    def signalstack_safety_flags(self) -> dict[str, bool]:
        return {
            "enabled": self.signalstack_enabled,
            "written_approval": self.signalstack_written_approval_confirmed,
            "account_program_approved": self.signalstack_account_program_approved,
            "official_docs": self.signalstack_official_docs_available,
            "credentials": self.signalstack_credentials_configured and bool(self.signalstack_api_key),
            "live_execution_allowed": self.signalstack_live_execution_allowed,
            "production": self.app_env == "production",
            "webhook_url": bool(self.signalstack_webhook_url),
            "account_reference": bool(self.signalstack_account_reference),
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
