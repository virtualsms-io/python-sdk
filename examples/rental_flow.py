"""Number rental flow: check availability, create a rental, extend it, cancel it.

Usage:
    export VIRTUALSMS_API_KEY=vsms_your_api_key
    python examples/rental_flow.py
"""

import os

from virtualsms import VirtualSMS


def main() -> None:
    api_key = os.environ.get("VIRTUALSMS_API_KEY")
    if not api_key:
        raise SystemExit("Set VIRTUALSMS_API_KEY first. Get a key at https://virtualsms.io")

    client = VirtualSMS(api_key)

    availability = client.rentals_available(country="GB", tier="full_access")
    print(f"Available countries: {availability.get('total_available')}")

    # Full Access tier: local SIM inventory, works with any service.
    rental = client.create_rental(tier="full_access", country="GB", duration_hours=24, service="wa")
    print(f"Rental created: {rental['rental_id']} -> {rental['phone_number']}")

    # Extend it by another 24 hours.
    extended = client.extend_rental(rental["rental_id"], duration_hours=24)
    print("Extended:", extended)

    # Full refund window is 20 minutes and zero SMS received, otherwise it runs to natural expiry.
    result = client.cancel_rental(rental["rental_id"])
    print("Cancel result:", result)


if __name__ == "__main__":
    main()
