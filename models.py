"""Shared Pydantic models for HTTP and MQTT ingestion paths."""

from datetime import datetime

from pydantic import BaseModel, Field


class WaterReading(BaseModel):
    """Single reading, as accepted by the legacy HTTP endpoint."""

    temperature: float = Field(..., ge=-5, le=50, description="Water temperature in °C")
    turbidity: float = Field(..., ge=0, description="Turbidity in NTU")
    ph: float | None = Field(None, ge=0, le=14, description="pH (0-14)")
    tds: float | None = Field(None, ge=0, description="TDS / conductivity in µS/cm")
    timestamp: datetime | None = Field(
        None,
        description="ISO 8601 UTC timestamp (defaults to server time)",
    )


class BatchReading(BaseModel):
    """One reading inside a batch. Timestamp is required so the server preserves sampling order."""

    temperature: float = Field(..., ge=-5, le=50)
    turbidity: float = Field(..., ge=0)
    ph: float | None = Field(None, ge=0, le=14)
    tds: float | None = Field(None, ge=0)
    timestamp: datetime


class BatchUpload(BaseModel):
    """Multiple readings sent in a single HTTP/MQTT message (NBIOT-friendly)."""

    readings: list[BatchReading] = Field(..., min_length=1, max_length=1000)


class IngestResponse(BaseModel):
    status: str
    station: str
    accepted: int
