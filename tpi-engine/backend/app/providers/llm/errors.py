class LLMError(RuntimeError):
    code = "LLM_PROVIDER_ERROR"
    http_status = 502
    retryable = False


class LLMAuthError(LLMError):
    code = "PROVIDER_AUTH_ERROR"
    http_status = 503


class LLMRateLimitError(LLMError):
    code = "PROVIDER_RATE_LIMIT"
    http_status = 429
    retryable = True


class LLMValidationError(LLMError):
    code = "PROVIDER_VALIDATION_ERROR"
    http_status = 400


class LLMTemporaryError(LLMError):
    code = "PROVIDER_TEMPORARY_ERROR"
    http_status = 503
    retryable = True


class LLMUnavailableError(LLMError):
    code = "PROVIDER_UNAVAILABLE"
    http_status = 503
    retryable = True


class MalformedLLMResponseError(LLMError):
    code = "MALFORMED_PROVIDER_RESPONSE"
    http_status = 502
