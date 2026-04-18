"""
MQTT subscriber for NBIOT station uploads.

Stations publish CBOR-encoded batches to:

    {prefix}/{station_id}/readings

(prefix is MQTT_TOPIC_PREFIX, default "stations"). Authentication is enforced
at the broker — each station has its own MQTT credentials with a topic ACL
restricting it to its own path. This service only verifies that the
station_id in the topic corresponds to a station we recognize.

The subscriber runs in a background thread (paho's loop_start) so it lives
alongside the FastAPI HTTP handlers. Lifecycle is bound to the FastAPI
lifespan context in main.py.
"""

from __future__ import annotations

import logging
import ssl
import threading
from typing import Optional

import paho.mqtt.client as mqtt

from auth import known_station_ids
from codec import CodecError, decode_batch
from config import settings
from ingest import record_batch

logger = logging.getLogger(__name__)

_client: Optional[mqtt.Client] = None
_lock = threading.Lock()


def _subscribe_topic() -> str:
    return f"{settings.mqtt_topic_prefix}/+/readings"


def _station_from_topic(topic: str) -> Optional[str]:
    prefix = settings.mqtt_topic_prefix
    parts = topic.split("/")
    if len(parts) != 3 or parts[0] != prefix or parts[2] != "readings":
        return None
    return parts[1]


def _on_connect(client, userdata, flags, reason_code, properties=None):
    # reason_code == 0 (or Success in v5) means connected.
    if getattr(reason_code, "is_failure", False) or (isinstance(reason_code, int) and reason_code != 0):
        logger.error("mqtt connect failed reason=%s", reason_code)
        return
    topic = _subscribe_topic()
    client.subscribe(topic, qos=settings.mqtt_qos)
    logger.info("mqtt connected; subscribed topic=%s qos=%d", topic, settings.mqtt_qos)


def _on_disconnect(client, userdata, disconnect_flags=None, reason_code=None, properties=None):
    logger.warning("mqtt disconnected reason=%s (auto-reconnect active)", reason_code)


def _on_message(client, userdata, msg):
    station_id = _station_from_topic(msg.topic)
    if station_id is None:
        logger.warning("mqtt: unexpected topic=%s — dropped", msg.topic)
        return

    if station_id not in known_station_ids():
        logger.warning("mqtt: unknown station_id=%s — dropped", station_id)
        return

    try:
        batch = decode_batch(msg.payload)
    except CodecError as exc:
        logger.warning(
            "mqtt: decode failed station=%s bytes=%d err=%s",
            station_id, len(msg.payload), exc,
        )
        return

    try:
        count = record_batch(station_id, batch.readings)
    except Exception:
        # Don't propagate — paho would swallow it anyway; log and move on.
        logger.exception("mqtt: influx write failed station=%s", station_id)
        return

    logger.debug(
        "mqtt: ingested station=%s readings=%d payload_bytes=%d",
        station_id, count, len(msg.payload),
    )


def start() -> None:
    """Connect to the broker and start the background network loop. Idempotent."""
    global _client
    with _lock:
        if _client is not None:
            return
        if not settings.mqtt_enabled:
            logger.info("mqtt disabled (MQTT_ENABLED=false) — skipping")
            return

        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=settings.mqtt_client_id,
            protocol=mqtt.MQTTv5,
        )
        if settings.mqtt_username:
            client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
        if settings.mqtt_tls:
            ctx = ssl.create_default_context(cafile=settings.mqtt_tls_ca)
            client.tls_set_context(ctx)

        client.on_connect = _on_connect
        client.on_disconnect = _on_disconnect
        client.on_message = _on_message

        client.reconnect_delay_set(min_delay=1, max_delay=60)
        try:
            client.connect_async(settings.mqtt_host, settings.mqtt_port, keepalive=60)
        except Exception:
            logger.exception("mqtt: initial connect_async failed (will retry)")
        client.loop_start()

        _client = client
        logger.info(
            "mqtt: started host=%s port=%d tls=%s",
            settings.mqtt_host, settings.mqtt_port, settings.mqtt_tls,
        )


def stop() -> None:
    global _client
    with _lock:
        if _client is None:
            return
        try:
            _client.loop_stop()
            _client.disconnect()
        finally:
            _client = None
        logger.info("mqtt: stopped")
