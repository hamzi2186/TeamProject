class CallingError(Exception):
    """Base error for the Calling Engine."""


class LeadNotCallableError(CallingError):
    pass


class KnowledgeBaseUnavailableError(CallingError):
    pass


class CallNotFoundError(CallingError):
    pass
