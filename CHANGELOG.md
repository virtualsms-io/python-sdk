# Changelog

## 2.0.0

Breaking rewrite. v1.x wrapped the legacy sms-activate-compatible `/stubs/handler_api.php`
dispatcher. v2.0.0 talks to `/api/v1/*` REST endpoints directly and does not use that
dispatcher at all. Method names changed; there is no compatibility shim.

Method mapping (v1.x -> v2.0.0):

| v1.x | v2.0.0 |
|---|---|
| `get_balance()` -> `float` | `get_balance()` -> `{"balance_usd": float}` |
| `get_number(service, country)` -> `Activation` | `create_order(service, country)` -> `dict` (order) |
| `get_status(activation_id)` -> `(status, code)` | `get_sms(order_id)` -> `dict`, or `get_order(order_id)` for full detail |
| `wait_for_code(activation_id, ...)` -> `str \| None` | `wait_for_sms(order_id, ...)` -> `dict` (never raises on timeout) |
| `done(activation_id)` | not applicable; orders resolve automatically |
| `cancel(activation_id)` | `cancel_order(order_id)` -> `dict` |
| `get_prices(service, country)` -> raw string | `get_price(service, country)` -> `dict` with real stock |

Added in 2.0.0 and not present in v1.x at all: rentals (`rentals_available`, `create_rental`,
`list_rentals`, `extend_rental`, `cancel_rental`, ...), proxies (`list_proxy_catalog`,
`buy_proxy`, `rotate_proxy`, `generate_proxy_endpoint`, ...), account (`get_profile`,
`get_transactions`, `get_stats`), webhooks (`list_webhooks`, `create_webhook`,
`update_webhook`, `test_webhook`, `list_webhook_deliveries`, ...), `check_number`, and
`start_manual_registration_session`.

## 1.0.0

Initial release. SMS verification only, via the legacy sms-activate-compatible dispatcher.
