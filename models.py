"""Shared models for UDP ingestion and Influx writes."""

from datetime import datetime

from pydantic import BaseModel, Field


class BatchReading(BaseModel):
    temperature: float = Field(..., ge=-5, le=50, description="Water temperature in °C")
    turbidity: float = Field(..., ge=0, description="Turbidity in NTU")
    ph: float | None = Field(None, ge=0, le=14, description="pH (0-14)")
    tds: float | None = Field(None, ge=0, description="TDS / conductivity in µS/cm")
    timestamp: datetime


class DecodedPacket(BaseModel):
    version: int
    station_number: int
    station_label: str
    packet_counter: int
    start_timestamp: datetime
    interval_s: int
    readings: list[BatchReading] = Field(..., min_length=1, max_length=1000)
