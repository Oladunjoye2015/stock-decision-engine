from app.execution.manual import ManualExecutionAdapter
from app.execution.paper import PaperExecutionAdapter
from app.execution.signalstack import SignalStackAdapter


def get_adapter(settings):
    if settings.execution_mode == "paper": return PaperExecutionAdapter(settings)
    if settings.execution_mode == "manual": return ManualExecutionAdapter()
    if settings.execution_mode == "signalstack": return SignalStackAdapter(settings)
    raise RuntimeError(f"Unsupported execution mode {settings.execution_mode}; failing closed")
