from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
from config import settings

api_key_header = APIKeyHeader(name="X-API-Key")

_station_keys: dict[str, str] | None = None


def _get_keys() -> dict[str, str]:
    global _station_keys
    if _station_keys is None:
        _station_keys = settings.get_station_keys()
    return _station_keys


def get_station_id(api_key: str = Security(api_key_header)) -> str:
    station = _get_keys().get(api_key)
    if not station:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return station
