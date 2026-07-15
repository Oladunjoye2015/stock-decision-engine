import pytest

from app.config import Settings
from app.core.exceptions import ModelCompatibilityError, RiskCheckError, SignalStackNotConfiguredError
from app.execution.signalstack import SignalStackAdapter
from app.models.feature_schema import validate_feature_order
from app.risk.position_sizing import calculate


def test_position_sizing_respects_stop_distance():
    near = calculate(100, 99, 50000, 50000, 150, 20)
    far = calculate(100, 95, 50000, 50000, 150, 20)
    assert near["quantity"] == 100  # symbol exposure is the binding limit
    assert far["quantity"] == 30
    assert far["estimated_risk_usd"] <= 150


def test_invalid_stop_fails_closed():
    with pytest.raises(RiskCheckError): calculate(100, 100, 50000, 50000, 150, 20)


def test_feature_order_is_exact():
    validate_feature_order({"a": 1, "b": 2}, ["a", "b"])
    with pytest.raises(ModelCompatibilityError): validate_feature_order({"b": 2, "a": 1}, ["a", "b"])


def test_signalstack_has_no_network_and_always_refuses():
    adapter = SignalStackAdapter(Settings(app_env="production", signalstack_enabled=True, signalstack_written_approval_confirmed=True, signalstack_account_program_approved=True, signalstack_official_docs_available=True, signalstack_credentials_configured=True, signalstack_live_execution_allowed=True))
    with pytest.raises(SignalStackNotConfiguredError): adapter.submit_signal({"symbol": "AAPL"})
    assert not hasattr(adapter, "url") and not hasattr(adapter, "client")

