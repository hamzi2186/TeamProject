class MailerError(RuntimeError):
    """Base Mailer error."""


class MailerTenantError(MailerError):
    pass


class MailerValidationError(MailerError):
    pass


class MailerProviderError(MailerError):
    pass


class MailerConversationNotFound(MailerError):
    pass


class MailerStopCondition(MailerError):
    pass
