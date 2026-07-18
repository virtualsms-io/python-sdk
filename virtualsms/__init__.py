"""VirtualSMS: native Python client for the VirtualSMS REST API v1."""

from .client import VirtualSMS
from .exceptions import (
    ApiError,
    BadApiKeyError,
    InsufficientBalanceError,
    NoNumbersError,
    NotFoundError,
    RateLimitedError,
    ServerError,
    VirtualSMSError,
)

__version__ = "2.0.0"
__all__ = [
    "VirtualSMS",
    "VirtualSMSError",
    "BadApiKeyError",
    "InsufficientBalanceError",
    "NotFoundError",
    "NoNumbersError",
    "RateLimitedError",
    "ServerError",
    "ApiError",
]
