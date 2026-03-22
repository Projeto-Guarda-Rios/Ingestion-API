from fastapi import FastAPI, Depends
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from influxdb_client import Point, WritePrecision

from auth import get_station_id
from influx import write_point

app = FastAPI(
    title="Guarda-Rios Ingestion API",
    description="Water quality sensor ingestion endpoint for the Guarda-Rios monitoring network.",
    version="1.0.0",
)


class WaterReading(BaseModel):
    temperature:  float           = Field(..., ge=-5,  le=50,  description="Water temperature in °C")
    turbidity:    float           = Field(..., ge=0,           description="Turbidity in NTU")
    ph:           float | None    = Field(None, ge=0,  le=14,  description="pH (0–14) (optional)")
    tds:          float | None    = Field(None, ge=0,          description="Electrical conductivity in µS/cm (optional)")
    timestamp:    datetime | None = Field(None,                description="ISO 8601 UTC timestamp from station (optional, defaults to server time)")


class IngestResponse(BaseModel):
    status:     str
    station:    str
    timestamp:  str


@app.post("/ingest", response_model=IngestResponse, status_code=201)
def ingest(reading: WaterReading, station_id: str = Depends(get_station_id)):
    """
    Receive a water quality reading from a sensor station and write it to InfluxDB.
    Authenticate with the station's API key in the X-API-Key header.
    """
    ts = reading.timestamp or datetime.now(timezone.utc)

    point = (
        Point("water_quality")
        .tag("station_id", station_id)
        .field("temperature", reading.temperature)
        .field("turbidity",   reading.turbidity)
        .time(ts, "s")
    )

    if reading.ph is not None:
        point.field("ph", reading.ph)
    if reading.tds is not None:
        point.field("tds", reading.conductivity)

    write_point(point)

    return IngestResponse(
        status="ok",
        station=station_id,
        timestamp=ts.isoformat(),
    )


@app.get("/health")
def health():
    """Basic liveness check."""
    return {"status": "ok"}
