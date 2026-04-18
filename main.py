import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

import mqtt_client
from auth import get_station_id
from ingest import record_batch, record_reading
from models import BatchUpload, IngestResponse, WaterReading

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    mqtt_client.start()
    try:
        yield
    finally:
        mqtt_client.stop()


app = FastAPI(
    title="Guarda-Rios Ingestion API",
    description=(
        "Water quality sensor ingestion for the Guarda-Rios monitoring network. "
        "MQTT (CBOR batches) is the primary path for NBIOT stations; HTTP/JSON "
        "remains available for manual testing and admin use."
    ),
    version="2.0.0",
    lifespan=lifespan,
)


@app.post("/ingest", response_model=IngestResponse, status_code=201)
def ingest(reading: WaterReading, station_id: str = Depends(get_station_id)):
    """Submit a single reading (HTTP/JSON). Authenticate via X-API-Key."""
    record_reading(station_id, reading)
    return IngestResponse(status="ok", station=station_id, accepted=1)


@app.post("/ingest/batch", response_model=IngestResponse, status_code=201)
def ingest_batch(batch: BatchUpload, station_id: str = Depends(get_station_id)):
    """
    Submit a batch of readings (HTTP/JSON).

    The MQTT path is strictly preferred for NBIOT stations — this endpoint
    exists for backfills, debugging, and clients on regular networks.
    """
    count = record_batch(station_id, batch.readings)
    return IngestResponse(status="ok", station=station_id, accepted=count)


@app.get("/health")
def health():
    """Liveness check."""
    return {"status": "ok"}
