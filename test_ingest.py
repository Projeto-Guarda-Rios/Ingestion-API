"""
test_ingest.py — Sends random water quality readings to the Guarda-Rios API.
Simulates a station sending data every N seconds.

Usage:
    python test_ingest.py                   # sends every 5 seconds, forever
    python test_ingest.py --interval 2      # sends every 2 seconds
    python test_ingest.py --count 10        # sends exactly 10 readings then stops
    python test_ingest.py --url http://my-server:8000  # custom server URL
"""

import argparse
import random
import time
from datetime import datetime, timezone

import requests

# ── Config ────────────────────────────────────────────────────────────────────

DEFAULT_URL      = "http://localhost:8000"
DEFAULT_INTERVAL = 5       # seconds between readings
DEFAULT_COUNT    = None    # None = run forever

# Replace with a real key from your .env STATION_KEYS
API_KEY = "a70b521465b960822290c93b7e06b2b5111e140ff17e0dc4e7107c53565775c0"
STATION_LABEL = "station_001 (simulated)"

# Realistic river water ranges
TEMP_RANGE       = (10.0, 25.0)   # °C
TURBIDITY_RANGE  = (1.0,  50.0)   # NTU

# ── Helpers ───────────────────────────────────────────────────────────────────

def random_reading() -> dict:
    return {
        "temperature": round(random.uniform(*TEMP_RANGE), 2),
        "turbidity":   round(random.uniform(*TURBIDITY_RANGE), 2),
        "timestamp":   datetime.now(timezone.utc).isoformat(),
    }


def send_reading(url: str, reading: dict) -> None:
    try:
        resp = requests.post(
            f"{url}/ingest",
            json=reading,
            headers={"X-API-Key": API_KEY},
            timeout=5,
        )
        if resp.status_code == 201:
            data = resp.json()
            print(
                f"[{data['timestamp']}]  OK  "
                f"temp={reading['temperature']}°C  "
                f"turbidity={reading['turbidity']} NTU  "
                f"→ {data['station']}"
            )
        else:
            print(f"  ERROR {resp.status_code}: {resp.text}")
    except requests.exceptions.ConnectionError:
        print(f"  ERROR: Could not connect to {url} — is the server running?")
    except requests.exceptions.Timeout:
        print("  ERROR: Request timed out.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Guarda-Rios API test data sender")
    parser.add_argument("--url",      default=DEFAULT_URL,      help="API base URL")
    parser.add_argument("--interval", default=DEFAULT_INTERVAL, type=float, help="Seconds between readings")
    parser.add_argument("--count",    default=DEFAULT_COUNT,    type=int,   help="Number of readings to send (default: forever)")
    args = parser.parse_args()

    mode = f"{args.count} readings" if args.count else "forever (Ctrl+C to stop)"
    print(f"Guarda-Rios test sender")
    print(f"  Target : {args.url}/ingest")
    print(f"  Station: {STATION_LABEL}")
    print(f"  Mode   : {mode}")
    print(f"  Interval: {args.interval}s")
    print("-" * 60)

    sent = 0
    try:
        while True:
            reading = random_reading()
            send_reading(args.url, reading)
            sent += 1

            if args.count and sent >= args.count:
                print(f"\nDone — sent {sent} readings.")
                break

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print(f"\nStopped — sent {sent} readings.")


if __name__ == "__main__":
    main()
