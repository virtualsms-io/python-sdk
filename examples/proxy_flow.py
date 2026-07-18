"""Proxy flow: browse the catalog, buy traffic, build a connection string, rotate the IP.

Usage:
    export VIRTUALSMS_API_KEY=vsms_your_api_key
    python examples/proxy_flow.py
"""

import os

from virtualsms import VirtualSMS


def main() -> None:
    api_key = os.environ.get("VIRTUALSMS_API_KEY")
    if not api_key:
        raise SystemExit("Set VIRTUALSMS_API_KEY first. Get a key at https://virtualsms.io")

    client = VirtualSMS(api_key)

    catalog = client.list_proxy_catalog()
    print(f"Pool types available: {[p['id'] for p in catalog]}")

    proxy = client.buy_proxy(pool_type="residential", gb=1, country_code="GB")
    print(f"Bought proxy {proxy['proxy_id']}: {proxy['gb_remaining']} GB remaining")

    endpoint = client.generate_proxy_endpoint(proxy["proxy_id"], country_code="GB", format="curl")
    print("Connection string:", endpoint["endpoints"][0])

    usage = client.get_proxy_usage(proxy["proxy_id"])
    print(f"Usage: {usage['gb_used']} GB used, {usage['gb_remaining']} GB remaining")

    rotated = client.rotate_proxy(proxy["proxy_id"])
    print("Rotated:", rotated)


if __name__ == "__main__":
    main()
