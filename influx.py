from typing import Sequence

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

from config import settings

client = InfluxDBClient(
    url=settings.influx_url,
    token=settings.influx_token,
    org=settings.influx_org,
)

write_api = client.write_api(write_options=SYNCHRONOUS)


def write_point(point: Point) -> None:
    write_api.write(bucket=settings.influx_bucket, record=point)


def write_points(points: Sequence[Point]) -> None:
    if not points:
        return
    write_api.write(bucket=settings.influx_bucket, record=list(points))
