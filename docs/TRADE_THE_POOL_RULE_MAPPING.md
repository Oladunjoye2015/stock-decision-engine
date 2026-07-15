# Trade The Pool rule mapping

| Rule | Local control | Fail-closed evidence |
|---|---|---|
| Conditional approval/account program | `approval_state.py`, environment flags | Approval status stored and configurable without code |
| Current policy/version | `trade_the_pool_rules.policy_state` | Missing/stale version blocks live mode |
| Daily Pause | `daily_risk_state.daily_pause` | Reconciliation updates and new entries block |
| Maximum Loss | `maximum_loss_buffer_reached` | Reconciliation updates and new entries block |
| 30-second rule | exact entry timestamps and `validate_planned_exit` | Planned early exit conflict recorded/blocked |
| 10-cent rule | expected movement per share | Sub-$0.10 profitable intent blocked where configured |
| 5% Position Volume | `volume_validation.py` and `volume_rule_checks` | Timestamp, volume, percentage, maximum and proposed shares persisted |
| Position/trade/exposure limits | broker-neutral risk engine | Ticket creation blocked |
| Shorts/symbol/program/session | settings plus compliance rule result | Unsupported state blocks |
| SignalStack-only execution | execution factory | Paper/manual never transmit; direct TTP route absent |
| Two requests/minute | `RollingRateLimiter` | Rolling-window count plus 30-second minimum interval |
| Queue/retry safety | durable idempotent priority queue, bounded retry policy | Overflow/duplicate/rapid retry fails closed |

Rules can differ by program and can change. Configuration must be verified against the current official policy; this mapping is not a guarantee of compliance.

