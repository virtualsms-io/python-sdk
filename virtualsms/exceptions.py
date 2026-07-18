"""Exception hierarchy for the VirtualSMS SDK.

Mirrors the HTTP status code mapping used by the VirtualSMS REST API v1.
Every SDK method raises one of these instead of a raw requests exception.
"""

from typing import Optional


class VirtualSMSError(Exception):
    """Base exception for all VirtualSMS SDK errors."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

    def __str__(self) -> str:
        return self.message


class BadApiKeyError(VirtualSMSError):
    """401: invalid or missing API key. Get one at https://virtualsms.io"""


class InsufficientBalanceError(VirtualSMSError):
    """402: balance too low for the requested purchase. Top up at https://virtualsms.io"""


class NotFoundError(VirtualSMSError):
    """404: resource not found (order/rental/proxy/webhook id, etc.)."""


class NoNumbersError(NotFoundError):
    """No numbers available for the requested service/country combination."""


class RateLimitedError(VirtualSMSError):
    """429: rate limit exceeded. Never retried automatically; slow down and retry later."""


class ServerError(VirtualSMSError):
    """5xx server error.

    ``retryable`` is only ever True for a GET/HEAD request, and only after the
    SDK's own bounded retry already gave up. A ``ServerError`` raised from a
    mutating call (POST/PUT/PATCH/DELETE) is NEVER retried automatically: the
    operation may have completed server-side despite the error. Verify with a
    read call (``list_orders``, ``get_order``, ``list_rentals``, etc.) before
    retrying by hand.
    """

    def __init__(self, message: str, status_code: Optional[int] = None, retryable: bool = False):
        super().__init__(message, status_code)
        self.retryable = retryable


class ApiError(VirtualSMSError):
    """Generic 4xx error not covered by a more specific subclass above."""
