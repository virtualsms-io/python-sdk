# VirtualSMS Python SDK

## What is VirtualSMS?

Official Python SDK for the VirtualSMS API. VirtualSMS is an account verification platform
for individuals, developers, and AI agents: one-time SMS verification, dedicated number
rentals, matching-country proxies, and private cloud browser sessions (beta), all behind one
API, one MCP server, and one prepaid balance. This SDK is a native Python client over the
REST API, backed by real carrier-issued mobile numbers (real physical SIM cards, not VoIP)
across 2500+ services in 145+ countries.

Built for developers and AI agents: REST API, hosted MCP server, SDKs.

This package talks to `https://virtualsms.io/api/v1` directly. It is not a drop-in client library for any other verification service; version 2.0.0 is a from-scratch rewrite, replacing the v1.x package that wrapped a legacy dispatcher.

## Installation

```bash
pip install virtualsms
```

## Quick start

<!-- TODO: re-point to /dashboard once the frontend migration ships -->

```python
from virtualsms import VirtualSMS

# Get your API key at https://virtualsms.io (Settings -> API Keys)
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

## Capabilities

1. One-time SMS verification. Receive a code for a service like WhatsApp, Telegram, Discord,
   or a dating app, on demand, from $0.05 per code.
2. Dedicated number rentals. Hold one number for 1-30 days and receive SMS from any service
   on that number, from $0.25/day.
3. Matching-country proxies. Pair a number with an IP from the same country, across 223
   proxy countries, from $1.10/GB.
4. Private cloud browser sessions (beta). Start a country-matched browser in a live viewer
   for the signup step itself, invite-only.

## Why real SIM cards

VirtualSMS runs on real carrier-issued mobile numbers, backed by real physical SIM cards,
not VoIP. Services like WhatsApp, Telegram, Discord, and dating apps run a carrier lookup
before they send a code, and VoIP or virtual numbers fail that check more often than a real
SIM does. A physical SIM on a real carrier network reads like any other phone on that network,
carriers like Vodafone, O2, and T-Mobile depending on the country, which is part of why
VirtualSMS holds a 95%+ success rate across 2500+ services in 145+ countries.

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

## AI agents and MCP

This SDK is the API-client half: a typed wrapper an application or agent framework calls
directly. The hosted MCP server is the separate agent-facing half, exposing the same
capabilities as MCP tools for MCP-compatible clients like Claude and Cursor. Use this SDK when
you're writing code that calls VirtualSMS; use the MCP server when an AI agent needs to call
VirtualSMS itself without a code layer in between.

## FAQ

### What is VirtualSMS?

VirtualSMS is an account verification platform for individuals, developers, and AI agents. It combines one-time SMS verification, dedicated number rentals, matching-country proxies, and private cloud browser sessions behind one API, one MCP server, and one prepaid balance.

### Does VirtualSMS use real SIM cards or VoIP numbers?

VirtualSMS uses real carrier-issued mobile numbers, backed by real physical SIM cards, not VoIP. Many services, including WhatsApp, Telegram, Discord, and dating apps, reject VoIP and virtual numbers at signup; a real physical SIM on a real carrier network passes that check far more often, which is reflected in a 95%+ success rate.

### Which services and countries does VirtualSMS support?

VirtualSMS covers 2500+ services across 145+ countries for SMS verification and number rentals, plus matching-country proxies across 223 proxy countries. Coverage spans messaging apps, social platforms, marketplaces, dating apps, and financial services.

### Can I rent a number, or only buy one-time codes?

Both. Buy a single one-time code from $0.05, or rent a dedicated number for 1-30 days from $0.25/day to receive SMS from any service on that number for the rental window.

### Does VirtualSMS work with AI agents and MCP?

Yes. VirtualSMS exposes a hosted MCP server plus a REST API and official SDKs in nine languages, so an AI agent can request a number, wait for a code, or manage a rental the same way a developer would call the API directly.

### How much does VirtualSMS cost?

Pricing is pay-as-you-go from one prepaid balance: SMS verification from $0.05 per code, number rentals from $0.25/day, and proxies from $1.10/GB. There is no subscription requirement.

### Is there a free API key?

Yes. Creating a VirtualSMS account issues an API key immediately, at no cost. You only spend from your prepaid balance when you place an order: an activation, a rental, or a proxy.

## Links

### Product

- **Homepage:** [virtualsms.io](https://virtualsms.io)
- **Docs:** [virtualsms.io/docs](https://virtualsms.io/docs)
- **MCP server:** [virtualsms.io/mcp](https://virtualsms.io/mcp)
- **Pricing:** [virtualsms.io/pricing](https://virtualsms.io/pricing)
- **REST API:** [virtualsms.io/api/v1](https://virtualsms.io/api/v1)
- **Other SDKs:** [PHP](https://packagist.org/packages/virtualsms/sdk) · [Node.js](https://www.npmjs.com/package/virtualsms-sdk) · [Ruby](https://rubygems.org/gems/virtualsms-sdk) · [.NET](https://www.nuget.org/packages/VirtualSMS) · [Go](https://pkg.go.dev/github.com/virtualsms-io/go-sdk) · [Rust](https://crates.io/crates/virtualsms) · [Swift](https://github.com/virtualsms-io/swift-sdk) · [Java](https://central.sonatype.com/artifact/io.virtualsms/virtualsms-sdk)
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
