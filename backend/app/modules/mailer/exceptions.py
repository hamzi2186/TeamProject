class MailerError(RuntimeError):
    """Base Mailer error."""


class MailerTenantError(MailerError):
    pass


class MailerValidationError(MailerError):
    pass


class MailerConfigurationError(MailerError):
    """A required setting is missing, so nothing was sent or written."""


class MailerProviderError(MailerError):
    """A provider, the LLM or the knowledge base failed. `retryable` says whether trying again
    could help, so a worker can tell a timeout from a rejected request."""

    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


class MailerConversationNotFound(MailerError):
    pass


class MailerStopCondition(MailerError):
    """The conversation or lead must not be emailed again."""
