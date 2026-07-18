# VirtualSMS Python SDK

VirtualSMS is an account verification platform that combines real carrier mobile numbers, matching-country proxies, and a private cloud browser into one connected workflow.

This package is the official **native Python client for the VirtualSMS REST API v1**: it talks to `https://virtualsms.io/api/v1` directly. It is not a drop-in client library for any other verification service; version 2.0.0 is a from-scratch rewrite, replacing the v1.x package that wrapped a legacy dispatcher.

**Who it's for:** developers and AI agents automating account creation, sign-up, or verification steps (bots, growth tooling, QA pipelines, agent frameworks), anywhere you need a number a platform will actually accept.

**Why VirtualSMS:** real physical SIM cards, not VoIP, so codes land on WhatsApp, Telegram, banking apps, and crypto exchanges that block virtual numbers. Pricing is public and live stock is shown before you commit. One connected account across numbers, rentals, and proxies today, reachable the same way whether you call the REST API, the hosted MCP server, or this SDK.

## Installation

```bash
pip install virtualsms
```

## Quick start

```python
from virtualsms import VirtualSMS

# Get your API key at https://virtualsms.io/dashboard (Settings -> API Keys)
client = VirtualSMS("vsms_your_api_key")

# 1. Check balance
balance = client.get_balance()
print(f"Balance: ${balance['balance_usd']:.2f}")

# 2. Buy a number for WhatsApp verification in the UK
order = client.create_order("wa", "GB")
print(f"Use this number: {order['phone_number']}")

# 3. Wait for the verification code
result = client.wait_for_sms(order["order_id"])
if result["success"]:
    print(f"Code: {result['code']}")
else:
    print("Timed out, try get_sms(order_id) again later or cancel_order(order_id) for a refund.")
```

Full API reference: [virtualsms.io/docs](https://virtualsms.io/docs)

## What this SDK covers

All 46+ non-gated REST v1 methods across seven groups: activations/orders, rentals (full-access and platform tiers), proxies, account, one session-start method, one standalone public tool, and webhooks.

| Group | Examples |
|---|---|
| Activations / Orders | `list_services`, `get_price`, `create_order`, `wait_for_sms`, `cancel_order`, `swap_number`, `search_services`, `find_cheapest` |
| Rentals | `rentals_available`, `create_rental`, `list_rentals`, `extend_rental`, `cancel_rental` |
| Proxies | `list_proxy_catalog`, `buy_proxy`, `rotate_proxy`, `set_proxy_targeting`, `generate_proxy_endpoint` |
| Account | `get_balance`, `get_profile`, `get_transactions`, `get_stats` |
| Session | `start_manual_registration_session` (invite-only beta) |
| Tools | `check_number` |
| Webhooks | `list_webhooks`, `create_webhook`, `update_webhook`, `test_webhook`, `list_webhook_deliveries` |

Not covered (by design, gated on the API itself): `release_rental` (fee policy pending), interactive browser session control beyond starting one, and account registration/login (account creation is a web-only flow).

## Rentals

Two tiers, identical refund terms (full refund within 20 minutes of purchase, before the first SMS):

```python
# Full Access: local SIM inventory, works with any service
rental = client.create_rental(tier="full_access", country="GB", duration_hours=24, service="wa")

# Platform: sourced via our global supplier network, locked to one service per number
rental = client.create_rental(tier="platform", country="GB", duration_hours=24, service="wa")

client.extend_rental(rental["rental_id"], duration_hours=24)
client.cancel_rental(rental["rental_id"])
```

## Proxies

```python
catalog = client.list_proxy_catalog()
proxy = client.buy_proxy(pool_type="residential", gb=1, country_code="GB")
usage = client.get_proxy_usage(proxy["proxy_id"])
endpoint = client.generate_proxy_endpoint(proxy["proxy_id"], country_code="GB")
print(endpoint["endpoints"][0])
```

## Errors

Every method raises a typed subclass of `VirtualSMSError`:

```python
from virtualsms import VirtualSMS, InsufficientBalanceError, NoNumbersError, BadApiKeyError, RateLimitedError

client = VirtualSMS("vsms_your_api_key")
try:
    order = client.create_order("wa", "GB")
except NoNumbersError:
    print("No stock for this service/country right now.")
except InsufficientBalanceError:
    print("Top up at https://virtualsms.io")
except BadApiKeyError:
    print("Bad API key.")
except RateLimitedError:
    print("Slow down and retry later.")
```

A server error (5xx) on a mutating call (purchase, cancel, rotate, extend, etc.) is never retried automatically by this SDK, because the operation may have completed server-side despite the error. Verify with a read call (`list_orders`, `get_order`, `list_rentals`) before retrying by hand. GET requests get a bounded automatic retry (up to 3 attempts) on network errors and 5xx responses only.

## Examples

See [`examples/`](./examples) for complete, runnable scripts: an activation flow, a rental flow, and a proxy flow.

## Links

### Product

- **Homepage:** [virtualsms.io](https://virtualsms.io)
- **Docs:** [virtualsms.io/docs](https://virtualsms.io/docs)
- **MCP server:** [virtualsms.io/mcp](https://virtualsms.io/mcp)
- **Pricing:** [virtualsms.io/pricing](https://virtualsms.io/pricing)
- **REST API:** [virtualsms.io/api/v1](https://virtualsms.io/api/v1)
- **GitHub:** [github.com/virtualsms-io](https://github.com/virtualsms-io)

### Ecosystem

VirtualSMS's MCP server is listed across the major MCP directories:

- **Official MCP registry:** `io.github.virtualsms-io/sms` ([registry.modelcontextprotocol.io](https://registry.modelcontextprotocol.io))
- **Glama:** [VirtualSMS on Glama](https://glama.ai/mcp/servers)
- **Smithery:** [smithery.ai/servers/virtualsms/virtualsms-mcp](https://smithery.ai/servers/virtualsms/virtualsms-mcp)
- **mcp.so:** [mcp.so/servers/mcp-server-virtualsms-io](https://mcp.so/servers/mcp-server-virtualsms-io)
- **npm (MCP server package):** [virtualsms-mcp](https://www.npmjs.com/package/virtualsms-mcp)

## Development

Run `sh scripts/check-positioning.sh` before committing copy changes. It fails on stale service or country counts and other banned positioning wording.

```bash
pip install -e ".[dev]"
pytest
```

## Migrating from v1.x

v1.x wrapped a legacy sms-activate-compatible dispatcher (`getBalance`, `getNumber`, `getStatus`, etc). v2.0.0 is a full rewrite talking to `/api/v1/*` REST endpoints directly and is not backward compatible with the v1.x method names. See `CHANGELOG.md` for the full method mapping.

## License

MIT
