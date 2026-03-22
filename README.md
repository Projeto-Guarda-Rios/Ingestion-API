# Guarda-Rios Ingestion API

Lightweight FastAPI service that receives water quality readings from AquaNode sensor stations and writes them to InfluxDB.

## Project Structure

```
guarda-rios-api/
├── main.py          # FastAPI app, routes, and Pydantic models
├── config.py        # Settings loaded from .env
├── influx.py        # InfluxDB client and write helper
├── auth.py          # Per-station API key authentication
├── .env             # Secrets (never commit)
├── .env.example     # Template
└── requirements.txt
```

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your InfluxDB credentials and station keys

# 3. Run
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Adding a Station

Generate a secure API key for each station:

```bash
openssl rand -hex 32
```

Add it to `STATION_KEYS` in `.env`:

```env
STATION_KEYS=abc123yourkeyhere:station_001,def456anotherkeyhere:station_002
```

Restart the server. Each station uses its key in the `X-API-Key` header.

## Sending a Reading

```bash
curl -X POST http://localhost:8000/ingest \
  -H "X-API-Key: your-station-key" \
  -H "Content-Type: application/json" \
  -d '{
    "ph": 7.42,
    "temperature": 18.3,
    "do_mgl": 9.1,
    "turbidity": 3.5,
    "conductivity": 412.0,
    "timestamp": "2026-03-21T10:00:00Z"
  }'
```

`timestamp` is optional — the server uses the current UTC time if omitted.

## InfluxDB Data Model

- **Measurement**: `water_quality`
- **Tags**: `station_id`
- **Fields**: `ph`, `temperature`, `do_mgl`, `turbidity`, `conductivity` (optional)

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/ingest` | Submit a water quality reading |
| `GET`  | `/health` | Liveness check |
| `GET`  | `/docs`   | Auto-generated Swagger UI |
