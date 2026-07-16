"""VirtualSMS API client: real SIM card SMS verification."""

import time
import requests
from dataclasses import dataclass
from typing import Optional


BASE_URL = "https://virtualsms.io/stubs/handler_api.php"
REST_URL = "https://virtualsms.io/api/v1"


@dataclass
class Activation:
    """Represents an SMS activation (one-time verification)."""
    activation_id: int
    phone: str
    service: str
    country: int

    def __str__(self):
        return f"Activation({self.activation_id}, {self.phone})"


@dataclass
class Rental:
    """Represents a number rental (dedicated number for 1-90 days)."""
    rental_id: int
    phone: str
    service: str
    country: str
    price: float
    expires_at: str
    status: str

    def __str__(self):
        return f"Rental({self.rental_id}, {self.phone})"


class VirtualSMSError(Exception):
    """Base exception for VirtualSMS API errors."""
    pass


class NoNumbersError(VirtualSMSError):
    """No numbers available for the requested service/country."""
    pass


class VirtualSMS:
    """Client for VirtualSMS API: SMS verification with real physical SIM cards.

    VirtualSMS provides real physical SIM cards, not VoIP, on carrier networks
    across 145+ countries and 2500+ services. Unlike VoIP services, these
    numbers pass carrier-type checks on WhatsApp, Telegram, and other platforms.

    Quick start:
        >>> from virtualsms import VirtualSMS
        >>> client = VirtualSMS("vsms_your_api_key")
        >>> balance = client.get_balance()
        >>> activation = client.get_number("wa", country=187)
        >>> code = client.wait_for_code(activation.activation_id)
        >>> print(f"Verification code: {code}")

    Get your API key at https://virtualsms.io (Settings → API Keys).

    Docs: https://virtualsms.io/api
    """

    def __init__(self, api_key: str, base_url: str = BASE_URL):
        """Initialize VirtualSMS client.

        Args:
            api_key: Your VirtualSMS API key (starts with vsms_).
                     Get one at https://virtualsms.io
            base_url: API base URL (default: production).
        """
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()

    def _request(self, action: str, **params) -> str:
        """Make a request to the sms-activate compatible API."""
        params["action"] = action
        params["api_key"] = self.api_key
        resp = self.session.get(self.base_url, params=params)
        resp.raise_for_status()
        return resp.text.strip()

    def get_balance(self) -> float:
        """Get current account balance in USD.

        Returns:
            Account balance as float.

        Raises:
            VirtualSMSError: If API key is invalid.

        Example:
            >>> client = VirtualSMS("vsms_your_key")
            >>> print(f"Balance: ${client.get_balance():.2f}")
            Balance: $50.30
        """
        result = self._request("getBalance")
        if result.startswith("ACCESS_BALANCE:"):
            return float(result.split(":")[1])
        raise VirtualSMSError(result)

    def get_number(self, service: str, country: int = 187) -> Activation:
        """Request a phone number for SMS verification.

        Args:
            service: Service code (e.g., 'wa' for WhatsApp, 'tg' for Telegram).
                     See https://virtualsms.io/api for full list.
            country: Country ID (default: 187 = US).
                     Common: 22=UK, 12=Germany, 33=France, 14=Russia.

        Returns:
            Activation object with phone number and activation ID.

        Raises:
            NoNumbersError: No numbers available for this service/country.
            VirtualSMSError: Other API error.

        Example:
            >>> activation = client.get_number("wa", country=22)
            >>> print(f"Use this number: {activation.phone}")
        """
        result = self._request("getNumber", service=service, country=country)
        if result.startswith("ACCESS_NUMBER:"):
            parts = result.split(":")
            return Activation(
                activation_id=int(parts[1]),
                phone=parts[2],
                service=service,
                country=country,
            )
        if result == "NO_NUMBERS":
            raise NoNumbersError(f"No numbers available for {service} in country {country}")
        raise VirtualSMSError(result)

    def get_status(self, activation_id: int) -> tuple:
        """Check status of an activation.

        Args:
            activation_id: The activation ID from get_number().

        Returns:
            Tuple of (status, code). Status is one of:
            - ("waiting", None): SMS not yet received
            - ("received", "438271"): SMS received, code extracted
            - ("done", None): Activation completed

        Example:
            >>> status, code = client.get_status(12345)
            >>> if code:
            ...     print(f"Got code: {code}")
        """
        result = self._request("getStatus", id=activation_id)
        if result == "STATUS_WAIT_CODE":
            return ("waiting", None)
        if result.startswith("STATUS_OK:"):
            return ("received", result.split(":")[1])
        if result == "STATUS_CANCEL":
            return ("cancelled", None)
        return (result, None)

    def set_status(self, activation_id: int, status: int = 6) -> str:
        """Set activation status.

        Args:
            activation_id: The activation ID.
            status: Status code (6 = done, 8 = cancel).

        Returns:
            API response string.
        """
        return self._request("setStatus", id=activation_id, status=status)

    def done(self, activation_id: int) -> str:
        """Mark activation as done (code used successfully).

        Args:
            activation_id: The activation ID to complete.
        """
        return self.set_status(activation_id, status=6)

    def cancel(self, activation_id: int) -> str:
        """Cancel an activation and get a refund.

        Args:
            activation_id: The activation ID to cancel.
        """
        return self.set_status(activation_id, status=8)

    def wait_for_code(self, activation_id: int, timeout: int = 300,
                      poll_interval: int = 5) -> Optional[str]:
        """Wait for an SMS code to arrive.

        Polls the API every poll_interval seconds until a code arrives
        or the timeout is reached.

        Args:
            activation_id: The activation ID to monitor.
            timeout: Maximum wait time in seconds (default: 300).
            poll_interval: Seconds between status checks (default: 5).

        Returns:
            The verification code as a string, or None if timed out.

        Example:
            >>> activation = client.get_number("wa")
            >>> # Use activation.phone to verify on WhatsApp
            >>> code = client.wait_for_code(activation.activation_id)
            >>> if code:
            ...     print(f"WhatsApp code: {code}")
            ... else:
            ...     print("Timed out waiting for SMS")
        """
        start = time.time()
        while time.time() - start < timeout:
            status, code = self.get_status(activation_id)
            if code:
                return code
            if status == "cancelled":
                return None
            time.sleep(poll_interval)
        return None

    def get_prices(self, service: str = None, country: int = None) -> str:
        """Get current prices for services/countries.

        Args:
            service: Optional service code to filter.
            country: Optional country ID to filter.

        Returns:
            Raw API response with pricing data.
        """
        params = {}
        if service:
            params["service"] = service
        if country:
            params["country"] = country
        return self._request("getPrices", **params)
