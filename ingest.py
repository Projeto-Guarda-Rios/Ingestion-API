"""
Protocol-agnostic ingestion pipeline.

The UDP listener calls into this module so the rules for translating a
reading into an InfluxDB point live in exactly one place.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable

from influxdb_client import Point

from influx import write_points
from models import BatchReading

logger = logging.getLogger(__name__)


def _ensure_utc(ts: datetime) -> datetime:
    return ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)


def _build_point(
    station_id: str,
    reading: BatchReading,
    default_ts: datetime,
) -> Point:
    ts = _ensure_utc(reading.timestamp or default_ts)

    point = (
        Point("water_quality")
        .tag("station_id", station_id)
        .field("temperature", float(reading.temperature))
        .field("turbidity", float(reading.turbidity))
        .time(ts, "s")
    )
    if reading.ph is not None:
        point.field("ph", float(reading.ph))
    if reading.tds is not None:
        point.field("tds", float(reading.tds))
    return point


def record_batch(station_id: str, readings: Iterable[BatchReading]) -> int:
    """Persist a batch of readings in a single Influx write. Returns count."""
    now = datetime.now(timezone.utc)
    points = [_build_point(station_id, r, now) for r in readings]
    write_points(points)
    logger.info("ingest batch station=%s count=%d", station_id, len(points))
    return len(points)
