from app.ai.schemas import AIReviewResult


class StructuredAIReviewer:
    """Local fail-closed reviewer boundary; replace only via an injected implementation."""
    def review(self, context: dict) -> AIReviewResult:
        required = {"symbol", "side", "primary_timeframe", "model_probability", "technical_gate", "timeframe_alignment", "market_regime", "news_status", "noise_status", "proposed_entry", "proposed_stop", "proposed_target", "reward_risk_ratio", "recent_ohlcv"}
        missing = required - context.keys()
        if missing: return AIReviewResult(approved=False, confidence=0, reason=f"missing structured fields: {sorted(missing)}", primary_risks=["incomplete_context"], recommended_action="block")
        approved = context["model_probability"] >= .5 and context["reward_risk_ratio"] >= 1.5
        return AIReviewResult(approved=approved, confidence=context["model_probability"], reason="structured review passed" if approved else "probability or reward/risk below policy", primary_risks=[], invalidation_condition=f"price crosses stop {context['proposed_stop']}", recommended_action="propose" if approved else "block")

