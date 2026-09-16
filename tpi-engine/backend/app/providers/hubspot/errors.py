class HubSpotError(RuntimeError):
    code = "HUBSPOT_ERROR"
    http_status = 502
    retryable = False


class InvalidOAuthStateError(HubSpotError):
    code = "INVALID_OAUTH_STATE"
    http_status = 400


class OAuthDeniedError(HubSpotError):
    code = "OAUTH_DENIED"
    http_status = 400


class TokenExchangeError(HubSpotError):
    code = "HUBSPOT_TOKEN_EXCHANGE_FAILED"


class TokenRefreshError(HubSpotError):
    code = "HUBSPOT_TOKEN_REFRESH_FAILED"


class ConnectionRevokedError(HubSpotError):
    code = "HUBSPOT_CONNECTION_REVOKED"
    http_status = 401


class ProviderRateLimitError(HubSpotError):
    code = "PROVIDER_RATE_LIMIT"
    http_status = 429
    retryable = True


class ProviderValidationError(HubSpotError):
    code = "PROVIDER_VALIDATION_ERROR"
    http_status = 400


class ProviderAuthError(HubSpotError):
    code = "PROVIDER_AUTH_ERROR"
    http_status = 401


class ProviderTemporaryError(HubSpotError):
    code = "PROVIDER_TEMPORARY_ERROR"
    http_status = 503
    retryable = True


class ProviderPermanentError(HubSpotError):
    code = "PROVIDER_PERMANENT_ERROR"


class MalformedProviderResponseError(HubSpotError):
    code = "MALFORMED_PROVIDER_RESPONSE"


class ConnectionNotFoundError(HubSpotError):
    code = "HUBSPOT_NOT_CONNECTED"
    http_status = 404
