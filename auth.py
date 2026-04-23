from __future__ import annotations

import hashlib
import hmac

from config import settings

_station_keys: dict[str, str] | None = None
_known_ids: frozenset[str] | None = None
_station_secrets: dict[str, tuple[bytes, ...]] | None = None
_udp_station_map: dict[int, str] | None = None


def _get_keys() -> dict[str, str]:
    global _station_keys
    if _station_keys is None:
        _station_keys = settings.get_station_keys()
    return _station_keys


def _candidate_secret_bytes(secret: str) -> tuple[bytes, ...]:
    candidates: list[bytes] = [secret.encode("utf-8")]
    compact = secret.strip()
    if compact and len(compact) % 2 == 0:
        try:
            raw = bytes.fromhex(compact)
        except ValueError:
            raw = None
        if raw and raw not in candidates:
            candidates.append(raw)
    return tuple(candidates)


def _get_station_secrets() -> dict[str, tuple[bytes, ...]]:
    global _station_secrets
    if _station_secrets is None:
        _station_secrets = {
            station_label: _candidate_secret_bytes(secret)
            for secret, station_label in settings.iter_station_pairs()
        }
    return _station_secrets


def _get_udp_station_map() -> dict[int, str]:
    global _udp_station_map
    if _udp_station_map is None:
        _udp_station_map = settings.get_udp_station_map()
    return _udp_station_map


def station_name_from_number(station_number: int) -> str | None:
    return _get_udp_station_map().get(station_number)


def verify_auth_tag(station_label: str, message: bytes, auth_tag: bytes) -> bool:
    for secret in _get_station_secrets().get(station_label, ()):
        digest = hmac.new(secret, message, hashlib.sha256).digest()[:16]
        if hmac.compare_digest(digest, auth_tag):
            return True
    return False


def known_station_ids() -> frozenset[str]:
    """Station labels the server will accept."""
    global _known_ids
    if _known_ids is None:
        _known_ids = frozenset(_get_keys().values())
    return _known_ids
