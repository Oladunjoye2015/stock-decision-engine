def update_maximum_loss(state, settings):
    if settings.ttp_maximum_loss_limit_usd is not None:
        state.maximum_loss_buffer_reached = state.realized_pnl <= -abs(settings.ttp_maximum_loss_limit_usd)
    return state.maximum_loss_buffer_reached

