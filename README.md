# VirtualSMS Python SDK

Python client for [VirtualSMS](https://virtualsms.io) — SMS verification using real physical SIM cards.

Unlike VoIP-based services, VirtualSMS uses real SIM cards in hardware modems connected to European and US cellular networks. This means near-100% delivery rates on platforms like WhatsApp, Telegram, and banking apps that block virtual numbers.

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

700+ services supported. Full list at [virtualsms.io/services](https://virtualsms.io/services).

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

30+ countries available. See [virtualsms.io/pricing](https://virtualsms.io/pricing) for all options.

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

## Why Real SIM Cards?

Most SMS verification services use VoIP numbers that get blocked:

- WhatsApp blocks 90%+ of VoIP numbers
- Telegram flags and restricts VoIP accounts
- Banking apps reject non-mobile numbers
- Crypto exchanges require real carrier numbers

VirtualSMS solves this with physical SIM cards in real mobile networks. [Learn more](https://virtualsms.io).

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

- **Website:** [virtualsms.io](https://virtualsms.io)
- **API Docs:** [virtualsms.io/api](https://virtualsms.io/api)
- **Pricing:** [virtualsms.io/pricing](https://virtualsms.io/pricing)
- **GitHub:** [github.com/virtualsms-io](https://github.com/virtualsms-io)

## License

MIT
