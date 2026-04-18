"""
test_mqtt.py — Simulates an NBIOT station publishing CBOR batches over MQTT.

Examples:

    # Publish 20 readings as a single batch to the local broker, once
    python test_mqtt.py --station station_001 --count 20

    # Loop forever: every 60s collect a reading, upload a batch every 10 min
    python test_mqtt.py --station station_001 --interval 60 --batch-size 10 --loop

The `--station` flag is the station_id the server expects (from STATION_KEYS).
MQTT credentials are separate — set --mqtt-user/--mqtt-pass to whatever the
broker's ACL expects (typically the station_id itself, with a password set
at the broker).
"""

from __future__ import annotations

import argparse
import random
import time
from datetime import datetime, timedelta, timezone

import paho.mqtt.client as mqtt

from codec import encode_batch
from models import BatchReading, BatchUpload

TEMP_RANGE = (10.0, 25.0)
TURBIDITY_RANGE = (1.0, 50.0)


def random_reading(ts: datetime, *, with_ph: bool, with_tds: bool) -> BatchReading:
    return BatchReading(
        temperature=round(random.uniform(*TEMP_RANGE), 2),
        turbidity=round(random.uniform(*TURBIDITY_RANGE), 2),
        ph=round(random.uniform(6.5, 8.5), 2) if with_ph else None,
        tds=round(random.uniform(100, 800), 0) if with_tds else None,
        timestamp=ts,
    )


def build_batch(
    size: int,
    interval_s: int,
    *,
    with_ph: bool,
    with_tds: bool,
) -> BatchUpload:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    readings = [
        random_reading(now - timedelta(seconds=interval_s * (size - 1 - i)),
                       with_ph=with_ph, with_tds=with_tds)
        for i in range(size)
    ]
    return BatchUpload(readings=readings)


def publish(
    client: mqtt.Client,
    topic: str,
    payload: bytes,
    qos: int,
) -> None:
    info = client.publish(topic, payload=payload, qos=qos)
    info.wait_for_publish(timeout=10)
    if info.rc != mqtt.MQTT_ERR_SUCCESS:
        raise RuntimeError(f"publish failed rc={info.rc}")


def main() -> None:
    p = argparse.ArgumentParser(description="Guarda-Rios MQTT station simulator")
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=1883)
    p.add_argument("--mqtt-user", default=None)
    p.add_argument("--mqtt-pass", default=None)
    p.add_argument("--tls", action="store_true")
    p.add_argument("--prefix", default="stations", help="topic prefix")
    p.add_argument("--station", required=True, help="station_id (also used as topic segment)")
    p.add_argument("--qos", type=int, default=1, choices=[0, 1, 2])
    p.add_argument("--count", type=int, default=10, help="readings per batch")
    p.add_argument("--batch-size", type=int, default=None,
                   help="alias for --count when --loop is set")
    p.add_argument("--interval", type=float, default=60,
                   help="seconds between readings inside a batch (for timestamp spacing)")
    p.add_argument("--loop", action="store_true",
                   help="publish a batch every (count * interval) seconds until Ctrl+C")
    p.add_argument("--with-ph", action="store_true")
    p.add_argument("--with-tds", action="store_true")
    args = p.parse_args()

    batch_size = args.batch_size if args.batch_size is not None else args.count
    topic = f"{args.prefix}/{args.station}/readings"

    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    if args.mqtt_user:
        client.username_pw_set(args.mqtt_user, args.mqtt_pass)
    if args.tls:
        client.tls_set()
    client.connect(args.host, args.port, keepalive=30)
    client.loop_start()

    print(f"Publishing to {args.host}:{args.port} topic={topic} qos={args.qos}")

    try:
        while True:
            batch = build_batch(
                batch_size,
                int(args.interval),
                with_ph=args.with_ph,
                with_tds=args.with_tds,
            )
            payload = encode_batch(batch)
            publish(client, topic, payload, qos=args.qos)
            print(
                f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] "
                f"published {batch_size} readings in {len(payload)} bytes "
                f"({len(payload)/batch_size:.1f} B/reading)"
            )
            if not args.loop:
                break
            time.sleep(batch_size * args.interval)
    except KeyboardInterrupt:
        print("stopped")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
