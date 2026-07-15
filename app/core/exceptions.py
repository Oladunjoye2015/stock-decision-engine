class DecisionEngineError(Exception):
    """Base domain exception."""


class SignalStackNotConfiguredError(DecisionEngineError):
    pass


class ModelCompatibilityError(DecisionEngineError):
    pass


class RiskCheckError(DecisionEngineError):
    pass


class TicketStateError(DecisionEngineError):
    pass

