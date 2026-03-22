from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    influx_url: str
    influx_token: str
    influx_org: str
    influx_bucket: str
    station_keys: str  # raw string from .env, parsed below

    class Config:
        env_file = ".env"

    def get_station_keys(self) -> dict[str, str]:
        """Parse 'key1:station_001,key2:station_002' into a dict."""
        result = {}
        for pair in self.station_keys.split(","):
            pair = pair.strip()
            if ":" in pair:
                key, station_id = pair.split(":", 1)
                result[key.strip()] = station_id.strip()
        return result


settings = Settings()
