"""Smoke test: get_balance, list_services, get_price succeed against a mocked backend.

Mocked rather than live so CI doesn't need a real API key. Verifies the client
builds correct requests, parses responses into the documented shapes, and
that imports/instantiation work end to end.
"""

from unittest.mock import MagicMock, patch

import pytest

from virtualsms import VirtualSMS


def _mock_response(json_data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = ""
    return resp


@pytest.fixture
def client():
    return VirtualSMS("vsms_test_key", base_url="https://virtualsms.io/api/v1")


def test_get_balance(client):
    with patch.object(client.session, "request", return_value=_mock_response({"balance_usd": 12.5})) as mock_req:
        balance = client.get_balance()

    assert balance == {"balance_usd": 12.5}
    assert "/customer/balance" in mock_req.call_args.args[1]
    assert mock_req.call_args.kwargs["headers"]["X-API-Key"] == "vsms_test_key"


def test_list_services(client):
    payload = {"services": [{"service_id": "wa", "service_name": "WhatsApp"}]}
    with patch.object(client.session, "request", return_value=_mock_response(payload)):
        services = client.list_services()

    assert services == [{"code": "wa", "name": "WhatsApp", "icon": None}]


def test_get_price_fails_closed_without_stock(client):
    price_resp = _mock_response({"price": 0.9, "currency": "USD"})
    catalog_resp = _mock_response({"countries": [{"id": "GB", "name": "United Kingdom", "price": 0.9, "count": 0}]})

    with patch.object(client.session, "request", side_effect=[price_resp, catalog_resp]):
        price = client.get_price("wa", "GB")

    assert price["price_usd"] == 0.9
    assert price["available"] is False  # count == 0 -> fail closed


def test_get_price_available_when_in_stock(client):
    price_resp = _mock_response({"price": 0.9, "currency": "USD"})
    catalog_resp = _mock_response({"countries": [{"id": "GB", "name": "United Kingdom", "price": 0.9, "count": 42}]})

    with patch.object(client.session, "request", side_effect=[price_resp, catalog_resp]):
        price = client.get_price("wa", "GB")

    assert price["available"] is True


def test_requires_api_key():
    with pytest.raises(ValueError):
        VirtualSMS("")


def test_bad_api_key_raises_typed_error(client):
    from virtualsms import BadApiKeyError

    with patch.object(client.session, "request", return_value=_mock_response({"message": "invalid key"}, status_code=401)):
        with pytest.raises(BadApiKeyError):
            client.get_balance()
