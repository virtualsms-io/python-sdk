"""Basic SMS verification (activation) flow: buy a number, wait for the code, done.

Usage:
    export VIRTUALSMS_API_KEY=vsms_your_api_key
    python examples/activation_flow.py
"""

import os

from virtualsms import InsufficientBalanceError, NoNumbersError, VirtualSMS


def main() -> None:
    api_key = os.environ.get("VIRTUALSMS_API_KEY")
    if not api_key:
        raise SystemExit("Set VIRTUALSMS_API_KEY first. Get a key at https://virtualsms.io")

    client = VirtualSMS(api_key)

    balance = client.get_balance()
    print(f"Balance: ${balance['balance_usd']:.2f}")

    # Optional: find the cheapest in-stock country for a service before buying.
    cheapest = client.find_cheapest("wa", limit=3)
    print("Cheapest WhatsApp options:", cheapest["cheapest_options"])

    try:
        order = client.create_order("wa", "GB")
    except NoNumbersError:
        print("No stock for wa/GB right now.")
        return
    except InsufficientBalanceError:
        print("Top up at https://virtualsms.io")
        return

    print(f"Number: {order['phone_number']} (order_id={order['order_id']})")

    result = client.wait_for_sms(order["order_id"], timeout_seconds=120)
    if result["success"]:
        print(f"Code: {result['code']}")
    else:
        print("No code within the timeout. Cancelling for a refund.")
        client.cancel_order(order["order_id"])


if __name__ == "__main__":
    main()
