class InferscaleError(Exception):
    """Base class for all Inferscale exceptions."""

# Gateway

class GatewayError(InferscaleError):
    """Raised when there is a gateway error."""

class InvalidRequestError(InferscaleError):
    """Raised when the request is invalid."""

class AuthenticationError(InferscaleError):
    """Raised when there is an authentication error."""

class RateLimitError(InferscaleError):
    """Raised when the rate limit is exceeded."""

# Queue

class QueueError(InferscaleError):
    """Base exception for queue-related errors."""


class QueueConnectionError(QueueError):
    """Raised when the queue backend cannot be reached."""


class QueueFullError(QueueError):
    """Raised when the queue cannot accept another request."""


class JobNotFoundError(QueueError):
    """Raised when a requested job does not exist."""


# Router

class RouterError(InferscaleError):
    """Base exception for router-related errors."""


class ModelNotFoundError(RouterError):
    """Raised when the requested model does not exist."""


class NoAvailableModelError(RouterError):
    """Raised when no healthy model can handle a request."""


# Worker

class WorkerError(InferscaleError):
    """Base exception for worker-related errors."""


class WorkerUnavailableError(WorkerError):
    """Raised when a worker cannot accept a request."""


class InferenceError(WorkerError):
    """Raised when model inference fails."""


class InferenceTimeoutError(WorkerError):
    """Raised when inference exceeds the configured timeout."""