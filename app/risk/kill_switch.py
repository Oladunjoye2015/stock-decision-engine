from app.risk.daily_risk import get_or_create


def set_state(db, settings, active: bool):
    state = get_or_create(db, settings); state.kill_switch = active; db.commit(); db.refresh(state); return state

