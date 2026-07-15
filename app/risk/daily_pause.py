def update_daily_pause(state, settings):
    if settings.ttp_daily_pause_enabled and settings.ttp_daily_pause_threshold_usd is not None:
        state.daily_pause = state.realized_pnl <= -abs(settings.ttp_daily_pause_threshold_usd)
    return state.daily_pause

