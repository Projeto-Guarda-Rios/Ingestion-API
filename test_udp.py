"""Simple UDP station simulator for the Guarda-Rios ingestion service."""

from __future__ import annotations

import argparse
import random
import socket
import time
from datetime import datetime, timedelta, timezone

from models import BatchReading
from udp_codec import encode_packet

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 40416
TEMP_RANGE = (10.0, 25.0)
TURBIDITY_RANGE = (1.0, 50.0)
def random_reading(ts: datetime) -> BatchReading:
    return BatchReading(
        temperature=round(random.uniform(*TEMP_RANGE), 2),
        turbidity=round(random.uniform(*TURBIDITY_RANGE), 2),
        timestamp=ts,
    )


def build_readings(sample_count: int, interval_s: int) -> list[BatchReading]:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    start = now - timedelta(seconds=interval_s * (sample_count - 1))
    return [
        random_reading(start + timedelta(seconds=index * interval_s))
        for index in range(sample_count)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Guarda-Rios UDP station simulator")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--station-id", type=int, default=1, help="numeric UDP station_id")
    parser.add_argument("--secret", required=True, help="station secret used to generate the auth tag")
    parser.add_argument("--interval", type=int, default=60, help="seconds between samples")
    parser.add_argument("--sample-count", type=int, default=10, help="samples per packet")
    parser.add_argument("--packets", type=int, default=1, help="number of packets to send")
    parser.add_argument("--pause", type=float, default=1.0, help="seconds between packets")
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    packet_counter = 1
    try:
        for _ in range(args.packets):
            readings = build_readings(args.sample_count, args.interval)
            payload = encode_packet(
                station_number=args.station_id,
                packet_counter=packet_counter,
                start_timestamp=int(readings[0].timestamp.timestamp()),
                interval_s=args.interval,
                readings=readings,
                secret=args.secret,
            )
            sock.sendto(payload, (args.host, args.port))
            print(
                f"sent packet_counter={packet_counter} station_id={args.station_id} "
                f"samples={len(readings)} bytes={len(payload)} target={args.host}:{args.port}"
            )
            packet_counter += 1
            if packet_counter <= args.packets:
                time.sleep(args.pause)
    finally:
        sock.close()


if __name__ == "__main__":
    main()
