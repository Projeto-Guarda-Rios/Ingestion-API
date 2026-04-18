from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # InfluxDB
    influx_url: str
    influx_token: str
    influx_org: str
    influx_bucket: str

    # Station auth (shared by HTTP and MQTT paths)
    station_keys: str  # raw "key1:station_001,key2:station_002"

    # MQTT broker — primary ingestion path for NBIOT stations
    mqtt_enabled: bool = True
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_username: Optional[str] = None
    mqtt_password: Optional[str] = None
    mqtt_tls: bool = False
    mqtt_tls_ca: Optional[str] = None
    mqtt_client_id: str = "guarda-rios-ingest"
    mqtt_topic_prefix: str = "stations"
    mqtt_qos: int = 1

    class Config:
        env_file = ".env"

    def get_station_keys(self) -> dict[str, str]:
        """Parse 'key1:station_001,key2:station_002' into {api_key: station_id}."""
        result: dict[str, str] = {}
        for pair in self.station_keys.split(","):
            pair = pair.strip()
            if ":" in pair:
                key, station_id = pair.split(":", 1)
                result[key.strip()] = station_id.strip()
        return result


settings = Settings()
