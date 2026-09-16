class EmbeddingError(RuntimeError):
    code = "EMBEDDING_PROVIDER_ERROR"
    http_status = 502
    retryable = False


class EmbeddingAuthError(EmbeddingError):
    code = "PROVIDER_AUTH_ERROR"
    http_status = 503


class EmbeddingRateLimitError(EmbeddingError):
    code = "PROVIDER_RATE_LIMIT"
    http_status = 429
    retryable = True


class EmbeddingValidationError(EmbeddingError):
    code = "PROVIDER_VALIDATION_ERROR"
    http_status = 400


class EmbeddingTemporaryError(EmbeddingError):
    code = "PROVIDER_TEMPORARY_ERROR"
    http_status = 503
    retryable = True


class EmbeddingUnavailableError(EmbeddingError):
    code = "PROVIDER_UNAVAILABLE"
    http_status = 503
    retryable = True


class MalformedEmbeddingResponseError(EmbeddingError):
    code = "MALFORMED_PROVIDER_RESPONSE"


class EmbeddingDimensionError(EmbeddingError):
    code = "EMBEDDING_DIMENSION_MISMATCH"
    http_status = 409
