class InferscaleError(Exception):
    """Base class for all Inferscale exceptions."""

    # HTTP status and OpenAI-style error type used when this error reaches a client.
    status_code: int = 500
    error_type: str = "server_error"

    def __init__(self, message: str = "", *, code: str | None = None) -> None:
        super().__init__(message or self.__doc__ or self.__class__.__name__)
        self.message = str(self.args[0])
        self.code = code


# Gateway


class GatewayError(InferscaleError):
    """Raised when there is a gateway error."""


class InvalidRequestError(InferscaleError):
    """Raised when the request is invalid."""

    status_code = 400
    error_type = "invalid_request_error"


class AuthenticationError(InferscaleError):
    """Raised when there is an authentication error."""

    status_code = 401
    error_type = "authentication_error"


class RateLimitError(InferscaleError):
    """Raised when the rate limit is exceeded."""

    status_code = 429
    error_type = "rate_limit_error"


# Queue


class QueueError(InferscaleError):
    """Base exception for queue-related errors."""


class QueueConnectionError(QueueError):
    """Raised when the queue backend cannot be reached."""

    status_code = 503


class QueueFullError(QueueError):
    """Raised when the queue cannot accept another request."""

    status_code = 429
    error_type = "rate_limit_error"


class JobNotFoundError(QueueError):
    """Raised when a requested job does not exist."""

    status_code = 404
    error_type = "not_found_error"


# Router


class RouterError(InferscaleError):
    """Base exception for router-related errors."""


class ModelNotFoundError(RouterError):
    """Raised when the requested model does not exist."""

    status_code = 404
    error_type = "invalid_request_error"


class NoAvailableModelError(RouterError):
    """Raised when no healthy model can handle a request."""

    status_code = 503


# Worker


class WorkerError(InferscaleError):
    """Base exception for worker-related errors."""

    status_code = 502


class WorkerUnavailableError(WorkerError):
    """Raised when a worker cannot accept a request."""


class InferenceError(WorkerError):
    """Raised when model inference fails."""


class InferenceTimeoutError(WorkerError):
    """Raised when inference exceeds the configured timeout."""

    status_code = 504
    error_type = "timeout_error"
