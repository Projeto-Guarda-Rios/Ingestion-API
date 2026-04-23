"""Binary UDP codec for Guarda-Rios station uploads."""

from __future__ import annotations

import hashlib
import hmac
import struct
from datetime import datetime, timedelta, timezone

from pydantic import ValidationError

from auth import station_name_from_number, verify_auth_tag
from models import BatchReading, DecodedPacket

TEMP_SCALE = 100
TURBIDITY_SCALE = 100

SUPPORTED_VERSION = 1
AUTH_TAG_SIZE = 16
HEADER_STRUCT = struct.Struct(">BHIIHB")
SAMPLE_STRUCT = struct.Struct(">hh")


class CodecError(ValueError):
    """Raised when a UDP payload does not conform to the binary schema."""


def decode_packet(payload: bytes) -> DecodedPacket:
    minimum_size = HEADER_STRUCT.size + AUTH_TAG_SIZE
    if len(payload) < minimum_size:
        raise CodecError(f"packet too short: expected at least {minimum_size} bytes")

    version, station_number, packet_counter, start_timestamp, interval_s, sample_count = (
        HEADER_STRUCT.unpack_from(payload)
    )
    if version != SUPPORTED_VERSION:
        raise CodecError(f"unsupported packet version {version}")
    if sample_count < 1:
        raise CodecError("sample_count must be at least 1")

    station_label = station_name_from_number(station_number)
    if station_label is None:
        raise CodecError(f"unknown station_id {station_number}")

    expected_size = HEADER_STRUCT.size + (sample_count * SAMPLE_STRUCT.size) + AUTH_TAG_SIZE
    if len(payload) != expected_size:
        raise CodecError(f"packet size mismatch: expected {expected_size} bytes, got {len(payload)}")

    signed_portion = payload[:-AUTH_TAG_SIZE]
    auth_tag = payload[-AUTH_TAG_SIZE:]
    if not verify_auth_tag(station_label, signed_portion, auth_tag):
        raise CodecError("auth tag verification failed")

    start_ts = datetime.fromtimestamp(start_timestamp, tz=timezone.utc)
    readings: list[BatchReading] = []
    offset = HEADER_STRUCT.size
    for index in range(sample_count):
        temp_raw, turbidity_raw = SAMPLE_STRUCT.unpack_from(payload, offset)
        offset += SAMPLE_STRUCT.size
        try:
            readings.append(
                BatchReading(
                    temperature=temp_raw / TEMP_SCALE,
                    turbidity=turbidity_raw / TURBIDITY_SCALE,
                    ph=None,
                    tds=None,
                    timestamp=start_ts + timedelta(seconds=index * interval_s),
                )
            )
        except ValidationError as exc:
            raise CodecError(f"sample {index} failed validation: {exc}") from exc

    return DecodedPacket(
        version=version,
        station_number=station_number,
        station_label=station_label,
        packet_counter=packet_counter,
        start_timestamp=start_ts,
        interval_s=interval_s,
        readings=readings,
    )


def encode_packet(
    *,
    station_number: int,
    packet_counter: int,
    start_timestamp: int,
    interval_s: int,
    readings: list[BatchReading],
    secret: str,
) -> bytes:
    if not readings:
        raise CodecError("empty packet")
    if len(readings) > 255:
        raise CodecError("sample_count exceeds one-byte limit")

    header = HEADER_STRUCT.pack(
        SUPPORTED_VERSION,
        station_number,
        packet_counter,
        start_timestamp,
        interval_s,
        len(readings),
    )
    body = bytearray()
    for reading in readings:
        body.extend(
            SAMPLE_STRUCT.pack(
                int(round(reading.temperature * TEMP_SCALE)),
                int(round(reading.turbidity * TURBIDITY_SCALE)),
            )
        )

    signed_portion = header + body
    auth_tag = hmac.new(secret.encode("utf-8"), signed_portion, hashlib.sha256).digest()[:16]
    return signed_portion + auth_tag
