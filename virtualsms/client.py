"""VirtualSMS API client: native Python client for the VirtualSMS REST API v1.

Covers SMS verification (activations/orders), number rentals (full-access and
platform tiers), residential/mobile/datacenter proxies, account data, webhook
subscriptions, and a couple of standalone public tools. This is a from-scratch
REST v1 client, not a wrapper around the legacy sms-activate-compatible
``/stubs/handler_api.php`` dispatcher used by v1.x of this package.

Quick start:
    >>> from virtualsms import VirtualSMS
    >>> client = VirtualSMS("vsms_your_api_key")
    >>> balance = client.get_balance()
    >>> order = client.create_order("wa", "GB")
    >>> result = client.wait_for_sms(order["order_id"])
    >>> print(result.get("code"))

Get your API key at https://virtualsms.io (Settings -> API Keys).
Docs: https://virtualsms.io/docs
"""

import re
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

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

DEFAULT_BASE_URL = "https://virtualsms.io/api/v1"
DEFAULT_TIMEOUT = 30.0

# ─── GET-only bounded retry policy ─────────────────────────────────────────
# Mutating calls (POST/PUT/PATCH/DELETE) are NEVER retried by the SDK: a 5xx
# or dropped connection on a mutating request does not prove the operation
# failed server-side, it may have gone through right before the error came
# back. Only idempotent reads get this safety net.
GET_RETRY_MAX_ATTEMPTS = 3  # 1 initial try + up to 2 retries
_GET_RETRY_BASE_DELAY_MS = 300

# Fixed gateway ports for proxy connection strings. Rotating vs. sticky is
# encoded entirely in the username's sessid/sessttl params, not by port choice.
_PROXY_HTTP_PORT = 823
_PROXY_SOCKS5_PORT = 824

# Statuses considered "active" (order is live and billable/cancellable).
_ACTIVE_ORDER_STATUSES = {"waiting", "pending", "sms_received", "created"}

# Internal ISO-3166 alpha-2 -> platform-network numeric country ID map.
# Required only by the platform-tier create call; every other rentals
# endpoint resolves country_code server-side. Not every ISO code the
# platform lists is rental-capable; an unmapped code means that country
# isn't available for platform-tier rentals.
PLATFORM_TIER_COUNTRY_IDS: Dict[str, int] = {
    "RU": 0, "UA": 1, "KZ": 2, "CN": 3, "PH": 4, "MM": 5, "ID": 6, "MY": 7, "KE": 8, "TZ": 9,
    "VN": 10, "KG": 11, "IL": 13, "HK": 14, "PL": 15, "GB": 16, "MG": 17, "CD": 18, "NG": 19,
    "MO": 20, "EG": 21, "IN": 22, "IE": 23, "KH": 24, "LA": 25, "HT": 26, "CI": 27, "GM": 28,
    "RS": 29, "YE": 30, "ZA": 31, "RO": 32, "CO": 33, "EE": 34, "AZ": 35, "CA": 36, "MA": 37,
    "GH": 38, "AR": 39, "UZ": 40, "CM": 41, "TD": 42, "DE": 43, "LT": 44, "HR": 45, "SE": 46,
    "IQ": 47, "NL": 48, "LV": 49, "AT": 50, "BY": 51, "TH": 52, "SA": 53, "MX": 54, "TW": 55,
    "ES": 56, "IR": 57, "DZ": 58, "SI": 59, "BD": 60, "SN": 61, "TR": 62, "CZ": 63, "LK": 64,
    "PE": 65, "PK": 66, "NZ": 67, "GN": 68, "ML": 69, "VE": 70, "ET": 71, "MN": 72, "BR": 73,
    "AF": 74, "UG": 75, "AO": 76, "CY": 77, "FR": 78, "PG": 79, "MZ": 80, "NP": 81, "BE": 82,
    "BG": 83, "HU": 84, "MD": 85, "IT": 86, "PY": 87, "HN": 88, "TN": 89, "NI": 90, "TL": 91,
    "BO": 92, "CR": 93, "GT": 94, "AE": 95, "ZW": 96, "PR": 97, "SD": 98, "TG": 99, "KW": 100,
    "SV": 101, "LY": 102, "JM": 103, "TT": 104, "EC": 105, "SZ": 106, "OM": 107, "BA": 108,
    "DO": 109, "SY": 110, "QA": 111, "PA": 112, "CU": 113, "MR": 114, "SL": 115, "JO": 116,
    "PT": 117, "BB": 118, "BI": 119, "BJ": 120, "BN": 121, "BS": 122, "BW": 123, "CF": 125,
    "GD": 127, "GE": 128, "GR": 129, "GW": 130, "GY": 131, "IS": 132, "KM": 133, "KN": 134,
    "LR": 135, "LS": 136, "MW": 137, "NA": 138, "NE": 139, "RW": 140, "SK": 141, "SR": 142,
    "TJ": 143, "MC": 144, "BH": 145, "RE": 146, "ZM": 147, "US": 187,
}


def _extract_code(text: Optional[str]) -> Optional[str]:
    """Pull the most likely numeric verification code out of an SMS body.

    Heuristic: first 4-8 digit run wins (covers "SMS code: 666512", "Your
    code is 1234", etc).
    """
    if not text:
        return None
    m = re.search(r"\b(\d{4,8})\b", text)
    return m.group(1) if m else None


def _parse_rfc3339(value: Optional[str]) -> Optional[datetime]:
    """Best-effort RFC3339 parse. Returns None instead of raising on garbage input."""
    if not value:
        return None
    try:
        v = value.strip()
        if v.endswith("Z"):
            v = v[:-1] + "+00:00"
        return datetime.fromisoformat(v)
    except (ValueError, AttributeError):
        return None


def _build_proxy_username(
    login: str,
    country_code: str,
    target_by: str,
    location_code: Optional[str],
    sticky_index: Optional[int] = None,
    sticky_minutes: Optional[int] = None,
) -> str:
    """Mirrors the frontend's ProxyEndpointGenerator buildUsername() exactly."""
    u = f"{login}__cr.{country_code.lower()}"
    loc = (location_code or "").strip()
    if loc and target_by != "country":
        if target_by == "state":
            u += f";state.{loc.lower()}"
        elif target_by == "city":
            u += f";city.{loc.lower()}"
        elif target_by == "zip":
            u += f";zip.{loc}"
        elif target_by == "asn":
            u += f";asn.{loc}"
    if sticky_index is not None:
        u += f";sessid.s{sticky_index};sessttl.{sticky_minutes or 10}"
    return u


def _build_proxy_endpoint_string(
    host: str, port: int, user: str, password: str, fmt: str, protocol: str
) -> str:
    """Mirrors the frontend's ProxyEndpointGenerator buildEndpoint() exactly."""
    if fmt == "host:port:user:pass":
        return f"{host}:{port}:{user}:{password}"
    if fmt == "user:pass@host:port":
        return f"{user}:{password}@{host}:{port}"
    scheme = "socks5h" if protocol == "SOCKS5" else "http"
    return f'curl -x "{scheme}://{user}:{password}@{host}:{port}" https://api.ipify.org'


class VirtualSMS:
    """Native Python client for the VirtualSMS REST API v1.

    Args:
        api_key: Your VirtualSMS API key. Get one at https://virtualsms.io
        base_url: API base URL (default: production ``/api/v1`` root).
        timeout: Per-request timeout in seconds (default: 30).
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        if not api_key:
            raise ValueError("api_key is required. Get one at https://virtualsms.io")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    # ─── Low-level HTTP layer ──────────────────────────────────────────────

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> requests.Response:
        url = f"{self.base_url}{path}"
        mutating = method.upper() not in ("GET", "HEAD")
        headers = {"X-API-Key": self.api_key, "Accept": "application/json"}
        if mutating:
            headers["X-Idempotency-Key"] = idempotency_key or str(uuid.uuid4())

        # Drop None-valued query params so requests doesn't serialize them.
        clean_params = {k: v for k, v in (params or {}).items() if v is not None} or None

        attempts = 0
        while True:
            attempts += 1
            try:
                resp = self.session.request(
                    method,
                    url,
                    params=clean_params,
                    json=json_body,
                    headers=headers,
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                if not mutating and attempts < GET_RETRY_MAX_ATTEMPTS:
                    time.sleep(_GET_RETRY_BASE_DELAY_MS * (2 ** (attempts - 1)) / 1000)
                    continue
                raise VirtualSMSError(f"Network error calling {method} {path}: {exc}") from exc

            if resp.status_code >= 500 and not mutating and attempts < GET_RETRY_MAX_ATTEMPTS:
                time.sleep(_GET_RETRY_BASE_DELAY_MS * (2 ** (attempts - 1)) / 1000)
                continue

            if resp.status_code >= 400:
                self._raise_for_status(resp, mutating)

            return resp

    @staticmethod
    def _raise_for_status(resp: requests.Response, mutating: bool) -> None:
        status = resp.status_code
        try:
            data = resp.json()
        except ValueError:
            data = {}
        raw_message = data.get("message") or data.get("error") if isinstance(data, dict) else None
        message = raw_message if isinstance(raw_message, str) else (resp.text or f"HTTP {status}")

        if status == 401:
            raise BadApiKeyError(f"Invalid API key. Get one at https://virtualsms.io. Details: {message}", status)
        if status == 402:
            raise InsufficientBalanceError(f"Insufficient balance. Top up at https://virtualsms.io. Details: {message}", status)
        if status == 404:
            raise NotFoundError(f"Not found: {message}", status)
        if status == 429:
            raise RateLimitedError("Rate limit exceeded. Please slow down requests; never auto-retry a 429.", status)
        if status >= 500:
            lower_message = message.lower()
            if "out of stock" in lower_message or "no number" in lower_message or "no stock" in lower_message:
                raise NoNumbersError(f"No numbers currently available: {message}", status)
            if mutating:
                raise ServerError(
                    f"VirtualSMS had a server error ({status}) on a request that may have made a purchase "
                    "or changed state. DO NOT blindly retry: first verify with a read call (list_orders, "
                    f"get_order, list_rentals, list_proxies, etc.) whether it actually succeeded, as you may "
                    f"have been charged. Details: {message}",
                    status,
                    retryable=False,
                )
            raise ServerError(
                f"VirtualSMS server error ({status}). Safe to retry this read-only request. Details: {message}",
                status,
                retryable=True,
            )
        raise ApiError(f"API error ({status}): {message}", status)

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        return self._request("GET", path, params=params).json()

    def _post(
        self,
        path: str,
        json_body: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Any:
        return self._request("POST", path, json_body=json_body or {}, idempotency_key=idempotency_key).json()

    def _patch(self, path: str, json_body: Optional[Dict[str, Any]] = None) -> Any:
        return self._request("PATCH", path, json_body=json_body or {}).json()

    def _delete(self, path: str) -> Any:
        return self._request("DELETE", path).json()

    # ─── 2.1 Activations / Orders (15 methods) ─────────────────────────────

    def list_services(self) -> List[Dict[str, Any]]:
        """List all SMS-verification services (Telegram, WhatsApp, etc). Public, no auth."""
        raw = self._get("/customer/services")
        items = raw.get("services", raw) if isinstance(raw, dict) else raw
        return [
            {
                "code": str(s.get("service_id", s.get("code", ""))),
                "name": str(s.get("service_name", s.get("name", ""))),
                "icon": s.get("icon"),
            }
            for s in items
        ]

    def list_countries(self) -> List[Dict[str, Any]]:
        """List all available countries. Public, no auth."""
        raw = self._get("/customer/countries")
        items = raw.get("countries", raw) if isinstance(raw, dict) else raw
        return [
            {
                "iso": str(c.get("country_id", c.get("iso", ""))),
                "name": str(c.get("country_name", c.get("name", ""))),
                "flag": c.get("flag"),
            }
            for c in items
        ]

    def _get_catalog_countries(self, service: str) -> List[Dict[str, Any]]:
        raw = self._get("/catalog/countries", params={"service": service})
        items = raw.get("countries", raw) if isinstance(raw, dict) else raw
        return [
            {
                "iso": str(c.get("id", c.get("iso", c.get("country", "")))),
                "name": str(c.get("name", c.get("country_name", ""))),
                "price_usd": float(c.get("price", c.get("our_price", c.get("price_usd", 0))) or 0),
                "count": int(c.get("count", 0) or 0),
            }
            for c in items
        ]

    def get_price(self, service: str, country: str) -> Dict[str, Any]:
        """Check price + real stock for a service+country combo.

        ``/price`` alone returns no availability field; real stock comes from
        ``/catalog/countries``'s per-country ``count`` (count > 0 == in stock).
        This replicates that two-call fail-closed pattern: never reports
        ``available: True`` off ``/price`` alone.
        """
        raw = self._get("/price", params={"service": service, "country": country})
        price = {
            "price_usd": float(raw.get("price", raw.get("price_usd", 0)) or 0),
            "currency": str(raw.get("currency", "USD")),
            "available": False,
        }
        try:
            catalog = self._get_catalog_countries(service)
            row = next((c for c in catalog if c["iso"].upper() == country.upper()), None)
            price["available"] = bool(row and row["count"] > 0)
        except VirtualSMSError:
            pass  # keep fail-closed default
        return price

    def create_order(self, service: str, country: str) -> Dict[str, Any]:
        """Buy a virtual number for one-off SMS verification."""
        try:
            return self._post("/customer/purchase", {"service": service, "country": country})
        except (NotFoundError, ApiError) as exc:
            low = str(exc).lower()
            if "no number" in low or "out of stock" in low or "no stock" in low:
                raise NoNumbersError(str(exc), status_code=exc.status_code) from exc
            raise

    def _normalize_order_detail(self, order: Dict[str, Any]) -> Dict[str, Any]:
        messages = order.get("messages") or []
        if not messages:
            text = order.get("sms_text") or order.get("sms_code")
            if text:
                messages = [{"content": text, "sender": None, "received_at": None}]
        first_content = messages[0]["content"] if messages else None
        code = order.get("sms_code") or (_extract_code(first_content) if first_content else None)

        result = dict(order)
        if messages:
            result["messages"] = messages
        if code:
            result["code"] = code
            result["sms_code"] = code
        if first_content:
            result["sms_text"] = first_content
        return result

    def get_order(self, order_id: str) -> Dict[str, Any]:
        """Full order detail including any received SMS, with ``code`` extracted."""
        raw = self._get(f"/customer/order/{order_id}")
        return self._normalize_order_detail(raw)

    def get_sms(self, order_id: str) -> Dict[str, Any]:
        """Poll for SMS delivery on an order. Thin client-side wrapper over get_order."""
        order = self.get_order(order_id)
        result: Dict[str, Any] = {"status": order.get("status"), "phone_number": order.get("phone_number")}
        if order.get("messages"):
            result["messages"] = order["messages"]
        if order.get("code"):
            result["code"] = order["code"]
            result["sms_code"] = order["code"]
        if order.get("sms_text"):
            result["sms_text"] = order["sms_text"]
        return result

    def wait_for_sms(
        self, order_id: str, timeout_seconds: int = 300, interval_seconds: int = 5
    ) -> Dict[str, Any]:
        """Block until an SMS arrives on ``order_id`` or ``timeout_seconds`` elapses.

        Polling-only baseline for v2.0.0 (the MCP tool's optional WebSocket
        race is a v2.1+ enhancement; polling alone is a supported baseline
        per the SDK spec). Never raises on timeout, returns a structured
        ``{"success": False, "error": "timeout", ...}`` result instead so the
        caller can retry or cancel.

        Defaults (300s timeout / 5s poll interval) intentionally differ from
        the MCP tool's own default (60s timeout, same 5s interval) -- a
        human/script blocking on this SDK call is typically willing to wait
        longer than an LLM agent loop, per the SDK spec.
        """
        start = time.monotonic()
        initial = self.get_order(order_id)
        phone_number = initial.get("phone_number")

        def build_success(order: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "success": True,
                "order_id": order_id,
                "phone_number": phone_number,
                "status": "sms_received",
                "messages": order.get("messages") or [],
                "code": order.get("code"),
                "delivery_method": "polling",
                "elapsed_seconds": round(time.monotonic() - start),
            }

        if initial.get("messages") or initial.get("code"):
            return build_success(initial)

        while True:
            elapsed = time.monotonic() - start
            remaining = timeout_seconds - elapsed
            if remaining <= 0:
                break

            order = self.get_order(order_id)
            if order.get("messages") or order.get("code"):
                return build_success(order)
            if order.get("status") in ("cancelled", "failed"):
                raise VirtualSMSError(f"Order {order_id} was {order['status']} before SMS arrived.")

            time.sleep(min(interval_seconds, remaining))

        return {
            "success": False,
            "error": "timeout",
            "order_id": order_id,
            "phone_number": phone_number,
        }

    def _precheck_cooldown(self, available_at: Optional[str], action: str) -> Optional[Dict[str, Any]]:
        dt = _parse_rfc3339(available_at)
        if dt is None:
            return None
        now = time.time()
        available_ts = dt.timestamp()
        if now >= available_ts:
            return None
        wait_seconds = int(available_ts - now) + 1
        return {
            "error": "cooldown_active",
            "action": action,
            "message": f"{'Cancel' if action == 'cancel' else 'Swap'} cooldown active. Try again in {wait_seconds} seconds.",
            "retry_at": available_at,
            "wait_seconds": wait_seconds,
        }

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel + refund an order (before any SMS received).

        Pre-checks ``cancel_available_at`` from a fresh get_order call and
        short-circuits locally with a ``cooldown_active`` result if the
        120-second post-purchase cooldown hasn't elapsed, saving a round-trip.
        """
        try:
            order = self.get_order(order_id)
            blocked = self._precheck_cooldown(order.get("cancel_available_at"), "cancel")
            if blocked:
                return blocked
        except VirtualSMSError:
            pass  # lookup failed; let the backend enforce the cooldown
        return self._post(f"/customer/cancel/{order_id}")

    def swap_number(self, order_id: str) -> Dict[str, Any]:
        """Get a new number for the same service/country, no extra charge. Same cooldown pre-check as cancel_order."""
        try:
            order = self.get_order(order_id)
            blocked = self._precheck_cooldown(order.get("swap_available_at"), "swap")
            if blocked:
                return blocked
        except VirtualSMSError:
            pass
        return self._post(f"/customer/swap/{order_id}")

    def retry_order(self, order_id: str) -> Dict[str, Any]:
        """Ask the current provider to resend the SMS to the SAME number."""
        return self._post(f"/orders/{order_id}/retry")

    def _normalize_order_summary(self, o: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "order_id": str(o.get("order_id", o.get("id", ""))),
            "phone_number": str(o.get("phone_number", "")),
            "service": str(o.get("service_id", o.get("service", ""))),
            "country": str(o.get("country_id", o.get("country", ""))),
            "price": float(o.get("price_charged", o.get("price", 0)) or 0),
            "created_at": o.get("created_at"),
            "expires_at": o.get("expires_at"),
            "status": str(o.get("status", "")),
            "sms_code": o.get("sms_code"),
            "sms_text": o.get("sms_text"),
        }

    def list_orders(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List orders, optional status filter. A 404 (endpoint absent on older deployments) is swallowed to []."""
        try:
            raw = self._get("/customer/orders", params={"status": status} if status else None)
        except NotFoundError:
            return []
        items = raw if isinstance(raw, list) else raw.get("orders", [])
        return [self._normalize_order_summary(o) for o in items]

    def order_history(
        self,
        status: Optional[str] = None,
        service: Optional[str] = None,
        country: Optional[str] = None,
        since_days: Optional[int] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """Order history with client-side filtering (service/country/since_days) and a hard cap of 50."""
        limit = min(max(limit, 1), 50)
        orders = self.list_orders(status)
        cutoff = time.time() - since_days * 86400 if since_days else None
        service_filter = service.lower() if service else None
        country_filter = country.upper() if country else None

        def keep(o: Dict[str, Any]) -> bool:
            if cutoff is not None:
                dt = _parse_rfc3339(o.get("created_at"))
                if dt is None or dt.timestamp() < cutoff:
                    return False
            if service_filter and (o.get("service") or "").lower() != service_filter:
                return False
            if country_filter and (o.get("country") or "").upper() != country_filter:
                return False
            return True

        filtered = [o for o in orders if keep(o)]
        capped = filtered[:limit]
        return {
            "count": len(capped),
            "total_matched": len(filtered),
            "filters": {"status": status, "service": service, "country": country, "since_days": since_days},
            "orders": capped,
        }

    def cancel_all_orders(self) -> Dict[str, Any]:
        """Bulk-cancel every active order. Gathers with partial failure; never aborts on the first error."""
        orders = self.list_orders()
        active = [o for o in orders if o.get("status") in _ACTIVE_ORDER_STATUSES]
        if not active:
            return {"cancelled": 0, "failed": 0, "total_active": 0, "cancelled_orders": [], "failures": []}

        cancelled: List[Dict[str, Any]] = []
        failures: List[Dict[str, Any]] = []
        for o in active:
            order_id = o["order_id"]
            try:
                res = self.cancel_order(order_id)
                cancelled.append({"order_id": order_id, "refunded": bool(res.get("refunded", False))})
            except VirtualSMSError as exc:
                failures.append({"order_id": order_id, "error": str(exc)})

        return {
            "cancelled": len(cancelled),
            "failed": len(failures),
            "total_active": len(active),
            "cancelled_orders": cancelled,
            "failures": failures,
        }

    def search_services(self, query: str) -> Dict[str, Any]:
        """Find the right service code using natural language ("uber", "binance", "steam")."""
        services = self.list_services()
        q = query.lower().strip()

        def score_service(s: Dict[str, Any]) -> Dict[str, Any]:
            name = s["name"].lower()
            code = s["code"].lower()
            if code == q or name == q:
                score = 1.0
            elif code.startswith(q) or name.startswith(q):
                score = 0.9
            elif q in code or q in name:
                score = 0.7
            else:
                query_tokens = q.split()
                name_tokens = re.split(r"[\s_-]+", name)
                matches = sum(1 for qt in query_tokens if any(qt in nt or nt in qt for nt in name_tokens))
                score = (matches / max(len(query_tokens), len(name_tokens))) * 0.6 if matches > 0 else 0.0
            return {"code": s["code"], "name": s["name"], "match_score": round(score, 2)}

        scored = [score_service(s) for s in services]
        matches = sorted((s for s in scored if s["match_score"] >= 0.5), key=lambda s: -s["match_score"])[:5]

        if matches:
            return {"query": query, "matches": matches, "tip": 'Use the "code" field as the service parameter in other methods.'}
        return {
            "query": query,
            "matches": [],
            "message": "No matching services found",
            "tip": "Try list_services() to browse all available services.",
        }

    def find_cheapest(self, service: str, limit: int = 5) -> Dict[str, Any]:
        """Find the cheapest in-stock countries for a service, sorted by price ascending."""
        catalog = self._get_catalog_countries(service)
        results = sorted(
            (
                {"country": c["iso"], "country_name": c["name"], "price_usd": c["price_usd"], "stock": True}
                for c in catalog
                if c["count"] > 0
            ),
            key=lambda c: c["price_usd"],
        )
        top = results[:limit]
        if not top:
            return {
                "service": service,
                "cheapest_options": [],
                "total_available_countries": 0,
                "message": (
                    f'No countries available for service "{service}". Use search_services() to verify '
                    "the service code, or list_services() to see all available services."
                ),
            }
        return {"service": service, "cheapest_options": top, "total_available_countries": len(results)}

    # ─── 2.2 Rentals (9 in-scope methods) ──────────────────────────────────
    # Two tiers, both refund-identical (full refund within 20 min of purchase,
    # before first SMS): "full_access" (local SIM inventory, any service) and
    # "platform" (global supplier network, one service per number, 24/72/168h
    # durations only). Never name the supplier.

    def rentals_pricing(self) -> List[Dict[str, Any]]:
        """List raw Full-Access pricing tiers. Catalog dump, not authoritative for what's purchasable today."""
        raw = self._get("/rentals/pricing")
        return raw if isinstance(raw, list) else raw.get("pricing", [])

    def rentals_available(
        self,
        country: Optional[str] = None,
        service: Optional[str] = None,
        type_: Optional[str] = None,
        tier: str = "full_access",
    ) -> Dict[str, Any]:
        """List country availability + pricing per tier. ``type_`` maps to the ``type`` query param."""
        params: Dict[str, Any] = {"country": country, "service": service, "type": type_}
        if tier == "platform":
            params["provider"] = "network"
        return self._get("/rentals/available", params=params)

    def rentals_services(self, country_code: str, duration_hours: int = 24) -> List[Dict[str, Any]]:
        """List platform-tier services available in a country, with stock + retail price.

        Explicit field allowlist: never forwards an internal supplier-code
        field the backend response may include.
        """
        raw = self._get("/rentals/services", params={"country_code": country_code, "duration": duration_hours})
        items = raw if isinstance(raw, list) else raw.get("services", [])
        return [
            {
                "service_id": str(s.get("service_id", "")),
                "service_name": str(s.get("service_name", "")),
                "physical_count": int(s.get("physical_count", 0) or 0),
                "our_price": s.get("our_price"),
                "base_price": s.get("base_price"),
                "popular": bool(s.get("popular", False)),
                "icon_url": s.get("icon_url"),
            }
            for s in items
        ]

    def rentals_price(self, service: str, country_code: str, duration_hours: int) -> Dict[str, Any]:
        """Get the catalog price for a (service, country, duration) platform-tier combo."""
        return self._get(
            "/rentals/price",
            params={"service": service, "country_code": country_code, "duration": duration_hours},
        )

    def create_rental(
        self,
        tier: str,
        country: str,
        duration_hours: int,
        service: Optional[str] = None,
        auto_renew: bool = False,
    ) -> Dict[str, Any]:
        """Create a rental (either tier).

        ``tier="full_access"``: local SIM inventory, any service.
        ``tier="platform"``: sourced via our global supplier network, one
        service per number; ``service`` is required and the ISO
        ``country`` code is resolved to the internal numeric ID locally via
        PLATFORM_TIER_COUNTRY_IDS.
        """
        if tier == "full_access":
            rental_type = "service" if service else "full"
            body: Dict[str, Any] = {
                "country": country,
                "rental_type": rental_type,
                "duration_hours": duration_hours,
                "auto_renew": bool(auto_renew),
            }
            if service:
                body["service"] = service
            return self._post("/rentals", body)

        if tier == "platform":
            if not service:
                raise ValueError("service is required for platform-tier rentals")
            country_id = PLATFORM_TIER_COUNTRY_IDS.get(country.upper())
            if country_id is None:
                raise NotFoundError(
                    f'Platform-tier rentals are not available for country_code "{country}". '
                    "Use rentals_available(tier='platform') to see supported countries."
                )
            data = self._post(
                "/rentals/provider",
                {"service": service, "country": country_id, "duration_hours": duration_hours, "provider": "network"},
            )
            return {
                "success": bool(data.get("success", True)),
                "rental_id": str(data.get("rental_id", "")),
                "phone_number": str(data.get("phone_number", "")),
                "expires_at": str(data.get("expires_at", "")),
                "retail_cost": data.get("retail_cost"),
                "currency": data.get("currency"),
                "status": "active",
            }

        raise ValueError(f'tier must be "full_access" or "platform", got {tier!r}')

    def list_rentals(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List rentals, optional status filter (server defaults to "active" when omitted)."""
        raw = self._get("/rentals", params={"status": status} if status else None)
        return raw if isinstance(raw, list) else raw.get("rentals", [])

    def get_rental(self, rental_id: str) -> Optional[Dict[str, Any]]:
        """Get one rental by id. No dedicated GET-by-id backend route exists; finds it in list_rentals('all')."""
        all_rentals = self.list_rentals(status="all")
        return next((r for r in all_rentals if r.get("id") == rental_id), None)

    def extend_rental(self, rental_id: str, duration_hours: int) -> Dict[str, Any]:
        """Extend an active rental, charged at current catalog price."""
        return self._post(f"/rentals/{rental_id}/extend", {"duration_hours": duration_hours})

    def cancel_rental(self, rental_id: str) -> Dict[str, Any]:
        """Full refund. Only within 20 minutes of purchase and before the first SMS, either tier."""
        return self._post(f"/rentals/{rental_id}/cancel")

    # ─── 2.3 Proxies (10 methods) ──────────────────────────────────────────

    def list_proxy_catalog(self) -> List[Dict[str, Any]]:
        """List pool types, countries, price/GB. Public, ~10min server cache."""
        raw = self._get("/proxies/catalog")
        pool_types = raw.get("pool_types", raw) if isinstance(raw, dict) else raw
        result = []
        for p in pool_types or []:
            countries = [
                {
                    "code": str(c.get("code", "")),
                    "name": str(c.get("name", "")),
                    "available": bool(c.get("available", False)),
                    "ip_count": int(c.get("ip_count", 0) or 0),
                }
                for c in (p.get("countries") or [])
            ]
            result.append(
                {
                    "id": str(p.get("id", "")),
                    "label": str(p.get("label", "")),
                    "price_per_gb": float(p.get("price_per_gb", 0) or 0),
                    "countries": countries,
                }
            )
        return result

    def list_proxies(self) -> List[Dict[str, Any]]:
        """List owned proxies with credentials."""
        raw = self._get("/proxies")
        items = raw if isinstance(raw, list) else raw.get("proxies", [])
        return [
            {
                "proxy_id": str(p.get("proxy_id", "")),
                "pool_type": str(p.get("pool_type", "")),
                "country_code": str(p.get("country_code", "")),
                "country_name": p.get("country_name"),
                "gb_total": float(p.get("gb_total", 0) or 0),
                "gb_used": float(p.get("gb_used", 0) or 0),
                "gb_remaining": float(p.get("gb_remaining", 0) or 0),
                "proxy_host": str(p.get("proxy_host", "")),
                "proxy_port": int(p.get("proxy_port", 0) or 0),
                "proxy_login": str(p.get("proxy_login", "")),
                "proxy_password": str(p.get("proxy_password", "")),
                "updated_at": p.get("updated_at"),
                "created_at": p.get("created_at"),
            }
            for p in items
        ]

    def buy_proxy(
        self,
        pool_type: str,
        gb: float,
        country_code: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Purchase proxy traffic (GB) for a pool type. ``country_code`` is a soft preference only."""
        body: Dict[str, Any] = {"pool_type": pool_type, "gb": gb}
        if country_code:
            body["country_code"] = country_code
        if idempotency_key:
            body["idempotency_key"] = idempotency_key
        return self._post("/proxies", body, idempotency_key=idempotency_key)

    def rotate_proxy(self, proxy_id: str, port: Optional[int] = None) -> Dict[str, Any]:
        """Get a fresh exit IP for an existing proxy."""
        body = {"port": port} if port is not None else {}
        return self._post(f"/proxies/{proxy_id}/rotate", body)

    def get_proxy_usage(self, proxy_id: str) -> Dict[str, Any]:
        """Cached GB used/remaining (refreshed ~5min, no upstream call)."""
        return self._get(f"/proxies/{proxy_id}/usage")

    def get_proxy_usage_history(self, proxy_id: str, range: str = "7d") -> Dict[str, Any]:
        """Per-day GB/requests series, "7d" or "30d"."""
        return self._get(f"/proxies/{proxy_id}/usage-history", params={"range": range})

    def set_proxy_targeting(
        self,
        proxy_id: str,
        country_code: str,
        cities: Optional[List[str]] = None,
        asns: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Persist default geo-targeting on a proxy sub-user.

        Country-only is free; cities/asns bill 2x GB on non-premium pools
        (free on ``residential_premium``).
        """
        body: Dict[str, Any] = {"country_code": country_code}
        if cities is not None:
            body["cities"] = cities
        if asns is not None:
            body["asns"] = asns
        return self._post(f"/proxies/{proxy_id}/targeting", body)

    def test_proxy(
        self,
        proxy_id: str,
        country: str,
        session: Optional[str] = None,
        protocol: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dial out through the proxy; reports exit IP/country/city/ISP/latency. Rate-limited ~1/20s per proxy."""
        body: Dict[str, Any] = {"country": country}
        if session:
            body["session"] = session
        if protocol:
            body["protocol"] = protocol
        return self._post(f"/proxies/{proxy_id}/test", body)

    def list_proxy_locations(self, pool_type: str, country: str, kind: str) -> List[Dict[str, Any]]:
        """Discover valid cities/states/asns/zips for a pool_type+country. Public, 6h cache. Not for residential_premium."""
        raw = self._get("/proxies/locations", params={"pool_type": pool_type, "country": country, "kind": kind})
        items = raw.get("items", raw) if isinstance(raw, dict) else raw
        return [
            {"code": str(i.get("code", "")), "name": str(i.get("name", "")), "count": int(i.get("count", 0) or 0)}
            for i in items or []
        ]

    def generate_proxy_endpoint(
        self,
        proxy_id: str,
        country_code: str,
        target_by: str = "country",
        location_code: Optional[str] = None,
        session: str = "rotating",
        sticky_ttl_minutes: int = 10,
        count: int = 1,
        protocol: str = "HTTP",
        format: str = "host:port:user:pass",
    ) -> Dict[str, Any]:
        """Compose a ready-to-use connection string. No backend call, no purchase.

        Pure function ported byte-identical to the frontend's
        ProxyEndpointGenerator logic. Fixed ports: HTTP=823, SOCKS5=824.
        Looks up credentials via list_proxies() first.
        """
        proxies = self.list_proxies()
        proxy = next((p for p in proxies if p["proxy_id"] == proxy_id), None)
        if not proxy:
            raise NotFoundError(f"Not found: proxy {proxy_id} does not exist on this account")

        count = max(1, min(100, int(count)))
        port = _PROXY_SOCKS5_PORT if protocol == "SOCKS5" else _PROXY_HTTP_PORT
        premium_2x = (
            target_by != "country"
            and bool((location_code or "").strip())
            and proxy["pool_type"] != "residential_premium"
        )

        if session == "rotating":
            user = _build_proxy_username(proxy["proxy_login"], country_code, target_by, location_code)
            ep = _build_proxy_endpoint_string(proxy["proxy_host"], port, user, proxy["proxy_password"], format, protocol)
            endpoints = [ep] * count
        else:
            endpoints = [
                _build_proxy_endpoint_string(
                    proxy["proxy_host"],
                    port,
                    _build_proxy_username(
                        proxy["proxy_login"], country_code, target_by, location_code, i + 1, sticky_ttl_minutes
                    ),
                    proxy["proxy_password"],
                    format,
                    protocol,
                )
                for i in range(count)
            ]

        return {
            "proxy_id": proxy["proxy_id"],
            "pool_type": proxy["pool_type"],
            "host": proxy["proxy_host"],
            "port": port,
            "protocol": protocol,
            "session": session,
            "sticky_ttl_minutes": sticky_ttl_minutes if session == "sticky" else None,
            "country_code": country_code,
            "target_by": target_by,
            "location_code": location_code,
            "premium_2x": premium_2x,
            "endpoints": endpoints,
        }

    # ─── 2.4 Account (4 methods) ────────────────────────────────────────────

    def get_balance(self) -> Dict[str, Any]:
        """Check account balance."""
        raw = self._get("/customer/balance")
        return {"balance_usd": float(raw.get("balance_usd", raw.get("balance", 0)) or 0)}

    def get_profile(self) -> Dict[str, Any]:
        """Full account profile."""
        raw = self._get("/customer/profile")
        return {
            "id": str(raw.get("id", "")),
            "email": str(raw.get("email", "")),
            "telegram_linked": bool(raw.get("telegram_linked", False)),
            "telegram_username": raw.get("telegram_username"),
            "balance_usd": float(raw.get("balance_usd", 0) or 0),
            "total_spent_usd": float(raw.get("total_spent_usd", 0) or 0),
            "total_credits_usd": float(raw.get("total_credits_usd", 0) or 0),
            "total_orders": int(raw.get("total_orders", 0) or 0),
            "active_api_keys": int(raw.get("active_api_keys", 0) or 0),
            "created_at": str(raw.get("created_at", "")),
        }

    def get_transactions(
        self,
        type: Optional[str] = None,
        from_: Optional[str] = None,
        to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Paginated transaction history. ``limit`` is 1-200 (server default 50)."""
        params: Dict[str, Any] = {"type": type, "from": from_, "to": to, "limit": limit, "offset": offset}
        raw = self._get("/customer/transactions", params=params)
        items = raw.get("transactions", []) if isinstance(raw, dict) else []
        return {
            "count": int(raw.get("count", len(items)) or 0),
            "limit": int(raw.get("limit", limit) or limit),
            "offset": int(raw.get("offset", offset) or offset),
            "transactions": items,
        }

    def get_stats(self, since_days: int = 30) -> Dict[str, Any]:
        """Aggregated usage stats over a lookback window. Calls get_balance + list_orders, aggregates locally."""
        cutoff = time.time() - since_days * 86400
        balance = self.get_balance()
        orders = self.list_orders()

        def in_window(o: Dict[str, Any]) -> bool:
            dt = _parse_rfc3339(o.get("created_at"))
            return dt is not None and dt.timestamp() >= cutoff

        windowed = [o for o in orders if in_window(o)]

        by_status: Dict[str, int] = {}
        by_service: Dict[str, int] = {}
        by_country: Dict[str, int] = {}
        total_spend = 0.0
        successful = 0
        terminal = 0

        for o in windowed:
            status = o.get("status", "")
            by_status[status] = by_status.get(status, 0) + 1
            if o.get("service"):
                by_service[o["service"]] = by_service.get(o["service"], 0) + 1
            if o.get("country"):
                by_country[o["country"]] = by_country.get(o["country"], 0) + 1
            if status != "cancelled" and isinstance(o.get("price"), (int, float)):
                total_spend += o["price"]
            if status in ("completed", "sms_received", "expired", "cancelled"):
                terminal += 1
                if status in ("completed", "sms_received"):
                    successful += 1

        def top_entries(d: Dict[str, int], n: int = 5) -> List[Dict[str, Any]]:
            return [{"key": k, "count": v} for k, v in sorted(d.items(), key=lambda kv: -kv[1])[:n]]

        result: Dict[str, Any] = {
            "window_days": since_days,
            "balance_usd": balance["balance_usd"],
            "total_orders": len(windowed),
            "successful_orders": successful,
            "success_rate": round(successful / terminal * 1000) / 10 if terminal > 0 else None,
            "total_spend_usd": round(total_spend, 2),
            "status_breakdown": by_status,
            "top_services": top_entries(by_service),
            "top_countries": top_entries(by_country),
        }
        if len(orders) >= 50:
            result["note"] = "Server caps order history at 50 rows. Stats may undercount if your activity exceeds 50 orders in the window."
        return result

    # ─── 2.5 Session (1 in-scope method) ───────────────────────────────────

    def start_manual_registration_session(
        self,
        service_name: Optional[str] = None,
        country: Optional[str] = None,
        device_mode: Optional[str] = None,
        with_proxy: Optional[bool] = None,
        target_url: Optional[str] = None,
        order_id: Optional[str] = None,
        mode: str = "fresh",
    ) -> Dict[str, Any]:
        """Start a country-matched cloud browser session the caller drives manually via ``viewer_url``.

        BETA - requires the invite-only Sessions feature; may return
        403/503 if not enabled on the account. On a beta-gate signal
        (403/404/503) this raises a clean invite message rather than a raw
        HTTP error.
        """
        body = {
            "serviceName": service_name,
            "country": country,
            "deviceMode": device_mode,
            "withProxy": with_proxy if with_proxy is not None else bool(country),
            "targetUrl": target_url,
            "orderId": order_id,
            "mode": mode,
        }
        try:
            raw = self._post("/browser-sessions/start", body)
        except VirtualSMSError as exc:
            if exc.status_code in (403, 404, 503):
                raise VirtualSMSError(
                    "Manual registration sessions are an invite-only beta. "
                    "Join https://t.me/VirtualSMS_io to request access."
                ) from exc
            raise
        return raw.get("session", raw) if isinstance(raw, dict) else raw

    # ─── 2.6 Other (1 method, public) ──────────────────────────────────────

    def check_number(self, number: str) -> Dict[str, Any]:
        """Carrier + line-type lookup for an arbitrary E.164 number (e.g. "+447911123456"). Public, no auth."""
        return self._get("/tools/number-check", params={"number": number})

    # ─── 2.7 Webhooks (7 methods) ──────────────────────────────────────────

    def list_webhooks(self) -> Dict[str, Any]:
        """List the account's webhook subscriptions."""
        return self._get("/customer/webhooks")

    def create_webhook(
        self,
        url: str,
        events: List[str],
        description: Optional[str] = None,
        threshold: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Create a webhook subscription. ``url`` must be https://, no localhost/IP literals.

        ``threshold`` is required if ``events`` includes "balance.low".
        The returned secret is shown exactly once, on create only: store it
        immediately.
        """
        body: Dict[str, Any] = {"url": url, "events": events}
        if description is not None:
            body["description"] = description
        if threshold is not None:
            body["threshold"] = threshold
        return self._post("/customer/webhooks", body)

    def get_webhook(self, webhook_id: str) -> Dict[str, Any]:
        """Get one webhook (no secret)."""
        return self._get(f"/customer/webhooks/{webhook_id}")

    def update_webhook(self, webhook_id: str, **fields: Any) -> Dict[str, Any]:
        """Partial update. Accepts any subset of url/description/events/threshold/active/paused.

        Un-pausing (``paused=False`` when previously True) resets
        ``failure_count_consecutive`` to 0 server-side.
        """
        allowed = {"url", "description", "events", "threshold", "active", "paused"}
        body = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not body:
            raise ValueError("update_webhook requires at least one field to update")
        return self._patch(f"/customer/webhooks/{webhook_id}", body)

    def delete_webhook(self, webhook_id: str) -> Dict[str, Any]:
        """Delete a webhook."""
        return self._delete(f"/customer/webhooks/{webhook_id}")

    def test_webhook(self, webhook_id: str) -> Dict[str, Any]:
        """Fire a synthetic test event through the real dispatcher. Requires the webhook be active and not paused."""
        return self._post(f"/customer/webhooks/{webhook_id}/test")

    def list_webhook_deliveries(self, webhook_id: str, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """List recent delivery attempts for a webhook."""
        return self._get(f"/customer/webhooks/{webhook_id}/deliveries", params={"limit": limit, "offset": offset})
