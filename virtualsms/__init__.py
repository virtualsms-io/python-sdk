"""VirtualSMS — Python SDK for SMS verification with real SIM cards."""

from .client import VirtualSMS, Activation, Rental

__version__ = "1.0.0"
__all__ = ["VirtualSMS", "Activation", "Rental"]
