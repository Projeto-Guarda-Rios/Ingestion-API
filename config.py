from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # InfluxDB
    influx_url: str
    influx_token: str
    influx_org: str
    influx_bucket: str

    # Station secrets keyed by station label, raw "key1:station_a,key2:station_b"
    station_keys: str

    # UDP ingestion
    udp_host: str = "0.0.0.0"
    udp_port: int = 40416
    udp_station_map: str | None = None  # raw "1:station_a,2:station_b"
    udp_buffer_size: int = 65535

    class Config:
        env_file = ".env"

    def iter_station_pairs(self) -> list[tuple[str, str]]:
        """Parse STATION_KEYS while preserving the configured order."""
        result: list[tuple[str, str]] = []
        for pair in self.station_keys.split(","):
            pair = pair.strip()
            if ":" in pair:
                key, station_label = pair.split(":", 1)
                result.append((key.strip(), station_label.strip()))
        return result

    def get_station_keys(self) -> dict[str, str]:
        """Parse STATION_KEYS into {api_key: station_label}."""
        return {key: station_label for key, station_label in self.iter_station_pairs()}

    def get_udp_station_map(self) -> dict[int, str]:
        """
        Parse UDP_STATION_MAP into {numeric_station_id: station_label}.

        When UDP_STATION_MAP is unset, stations are assigned sequentially using the
        order in STATION_KEYS: 1, 2, 3, ...
        """
        if not self.udp_station_map:
            return {
                index: station_label
                for index, (_, station_label) in enumerate(self.iter_station_pairs(), start=1)
            }

        result: dict[int, str] = {}
        for pair in self.udp_station_map.split(","):
            pair = pair.strip()
            if ":" not in pair:
                continue
            station_number_raw, station_label = pair.split(":", 1)
            result[int(station_number_raw.strip())] = station_label.strip()
        return result


settings = Settings()
