# VirtualSMS Python SDK

VirtualSMS is an account verification platform that combines real carrier mobile numbers, matching-country proxies and a private cloud browser into one connected workflow.

Built for developers and AI agents: REST API, hosted MCP server, SDKs.

This package is the official Python client for **VirtualSMS SMS verification**: request a real carrier number, not a VoIP number, wait for the code, done. For the rest of the platform (proxies, the private cloud browser, number rentals), use the [REST API](https://virtualsms.io/docs) or the [hosted MCP server](https://virtualsms.io/mcp) directly. See "What this SDK does (and doesn't)" below for exactly what's implemented in this package.

**Who it's for:** developers and AI agents automating account creation, sign-up, or verification steps (bots, growth tooling, QA pipelines, agent frameworks), anywhere you need a number a platform will actually accept.

**Why VirtualSMS:** real carrier-issued numbers, not VoIP, so codes land on WhatsApp, Telegram, banking apps, and crypto exchanges that block virtual numbers. Pricing is public and live stock is shown before you commit, so there's no surprise unavailability after you've paid. And it's one connected account across numbers, proxies, and the cloud browser, reachable the same way whether you call the REST API, the MCP server, or an SDK.

## Installation

```bash
pip install virtualsms
```

## Quick Start

```python
from virtualsms import VirtualSMS

# Get your API key at https://virtualsms.io (Settings → API Keys)
client = VirtualSMS("vsms_your_api_key")

# Check balance
balance = client.get_balance()
print(f"Balance: ${balance:.2f}")

# Get a number for WhatsApp verification
activation = client.get_number("wa", country=22)  # 22 = UK
print(f"Use this number: {activation.phone}")

# Wait for the verification code
code = client.wait_for_code(activation.activation_id)
print(f"Verification code: {code}")

# Mark as done
client.done(activation.activation_id)
```

## What this SDK does (and doesn't)

This package wraps VirtualSMS's **SMS verification** endpoints only:

- Get account balance (`get_balance`)
- Request a number for a service (`get_number`)
- Poll or wait for the incoming SMS code (`get_status`, `wait_for_code`)
- Mark an activation done, or cancel it for a refund (`done`, `cancel`)
- Look up prices for services/countries (`get_prices`)

It does **not** currently wrap proxies, number rentals, or the cloud browser, even though the wider VirtualSMS platform supports all three. For those:

- **REST API** (full platform, including numbers, proxies and cloud browser): [virtualsms.io/docs](https://virtualsms.io/docs)
- **Hosted MCP server** (lets AI agents drive the full platform, including proxies and the cloud browser): [virtualsms.io/mcp](https://virtualsms.io/mcp)

> Note: this package ships a `Rental` data class for forward compatibility, but no method in this SDK currently creates or manages a rental. That's on the roadmap, coming soon. Use the REST API for rentals today.

## Services

Common service codes:

| Service | Code |
|---------|------|
| WhatsApp | `wa` |
| Telegram | `tg` |
| Google | `go` |
| Instagram | `ig` |
| Facebook | `fb` |
| Discord | `ds` |
| TikTok | `lf` |
| Twitter/X | `tw` |

2500+ services supported. Full list at [virtualsms.io/services](https://virtualsms.io/services).

## Countries

Common country codes:

| Country | Code |
|---------|------|
| United States | `187` |
| United Kingdom | `22` |
| Germany | `12` |
| France | `33` |
| Netherlands | `57` |
| Russia | `0` |

145+ countries available. See [virtualsms.io/pricing](https://virtualsms.io/pricing) for all options.

## API Methods

### `get_balance() → float`
Returns current account balance in USD.

### `get_number(service, country) → Activation`
Request a phone number for verification. Returns an `Activation` with `activation_id` and `phone`.

### `get_status(activation_id) → (status, code)`
Check if SMS has arrived. Returns `("waiting", None)` or `("received", "438271")`.

### `wait_for_code(activation_id, timeout=300) → str | None`
Poll for SMS code with automatic retry. Returns the code or None on timeout.

### `done(activation_id)`
Mark activation as complete after using the code.

### `cancel(activation_id)`
Cancel activation and get automatic refund.

### `get_prices(service=None, country=None)`
Get current pricing for services and countries.

## Why Real Carrier Numbers?

Most SMS verification services use VoIP numbers that get blocked:

- WhatsApp blocks VoIP numbers
- Telegram flags and restricts VoIP accounts
- Banking apps reject non-mobile numbers
- Crypto exchanges require real carrier numbers

VirtualSMS uses real carrier-issued numbers, not VoIP. [Learn more](https://virtualsms.io).

## Migrating from DaisySMS?

VirtualSMS API is fully compatible with the sms-activate protocol. If you used DaisySMS, change one line:

```python
# Before
client = VirtualSMS("your_key", base_url="https://daisysms.com/stubs/handler_api.php")

# After
client = VirtualSMS("your_key")  # defaults to virtualsms.io
```

See the [migration guide](https://virtualsms.io/daisysms-alternative).

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

Run `sh scripts/check-positioning.sh` before committing copy changes. It fails on
stale service or country counts and other banned positioning wording.

## License

MIT
