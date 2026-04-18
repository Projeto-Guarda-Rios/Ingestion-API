"""
Compact binary codec for NBIOT station batch uploads.

Designed for data-constrained cellular links (2 MB/month NBIOT plans).
Typical cost: ~10-15 bytes per reading in CBOR vs ~150 bytes per reading in
JSON — a 10x+ reduction at the payload level, plus the MQTT framing overhead
is itself ~50x smaller than HTTP headers.

Wire format — CBOR map with integer keys (integer keys cost 1 byte each,
vs ~12 bytes for a string key like "temperature"):

    {
      0: uint32,                 # base timestamp (Unix epoch seconds, UTC)
      1: [                       # readings, at least one
        {
          0: int16 (optional),   # offset seconds from base_ts (default 0)
          1: int16,              # temperature * 100   (0.01 °C precision)
          2: uint16,             # turbidity * 100     (0.01 NTU precision)
          3: uint16 (optional),  # pH * 100            (0.01 precision)
          4: uint16 (optional),  # tds in µS/cm
        },
        ...
      ]
    }

Optional fields are *omitted* (not sent as null) when the station does not
have the sensor installed — this saves 2-3 bytes per reading per missing
field.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import cbor2

from models import BatchReading, BatchUpload

# Top-level keys
K_BASE_TS = 0
K_READINGS = 1

# Per-reading keys
R_OFFSET = 0
R_TEMP = 1
R_TURBIDITY = 2
R_PH = 3
R_TDS = 4

TEMP_SCALE = 100
TURBIDITY_SCALE = 100
PH_SCALE = 100


class CodecError(ValueError):
    """Raised when a payload does not conform to the compact CBOR schema."""


def decode_batch(payload: bytes) -> BatchUpload:
    try:
        data = cbor2.loads(payload)
    except Exception as exc:
        raise CodecError(f"invalid CBOR: {exc}") from exc

    if not isinstance(data, dict):
        raise CodecError("root must be a map")

    base_ts_raw = data.get(K_BASE_TS)
    if not isinstance(base_ts_raw, int):
        raise CodecError("missing or invalid base timestamp (key 0)")

    raw_readings = data.get(K_READINGS)
    if not isinstance(raw_readings, list) or not raw_readings:
        raise CodecError("missing or empty readings array (key 1)")

    readings: list[BatchReading] = []
    for i, item in enumerate(raw_readings):
        if not isinstance(item, dict):
            raise CodecError(f"reading {i}: not a map")

        temp = item.get(R_TEMP)
        turb = item.get(R_TURBIDITY)
        if not isinstance(temp, int) or not isinstance(turb, int):
            raise CodecError(f"reading {i}: temperature/turbidity required and must be ints")

        offset = item.get(R_OFFSET, 0)
        if not isinstance(offset, int):
            raise CodecError(f"reading {i}: offset must be an int")

        ph = item.get(R_PH)
        tds = item.get(R_TDS)
        if ph is not None and not isinstance(ph, int):
            raise CodecError(f"reading {i}: pH must be an int or absent")
        if tds is not None and not isinstance(tds, int):
            raise CodecError(f"reading {i}: tds must be an int or absent")

        ts = datetime.fromtimestamp(base_ts_raw + offset, tz=timezone.utc)

        readings.append(
            BatchReading(
                temperature=temp / TEMP_SCALE,
                turbidity=turb / TURBIDITY_SCALE,
                ph=(ph / PH_SCALE) if ph is not None else None,
                tds=float(tds) if tds is not None else None,
                timestamp=ts,
            )
        )

    return BatchUpload(readings=readings)


def encode_batch(batch: BatchUpload) -> bytes:
    """Encode a batch into the compact CBOR wire format. Used by the simulator."""
    if not batch.readings:
        raise CodecError("empty batch")

    base_ts = int(batch.readings[0].timestamp.timestamp())
    items: list[dict[int, Any]] = []
    for r in batch.readings:
        item: dict[int, Any] = {
            R_TEMP: int(round(r.temperature * TEMP_SCALE)),
            R_TURBIDITY: int(round(r.turbidity * TURBIDITY_SCALE)),
        }
        offset = int(r.timestamp.timestamp()) - base_ts
        if offset:
            item[R_OFFSET] = offset
        if r.ph is not None:
            item[R_PH] = int(round(r.ph * PH_SCALE))
        if r.tds is not None:
            item[R_TDS] = int(round(r.tds))
        items.append(item)

    return cbor2.dumps({K_BASE_TS: base_ts, K_READINGS: items})
