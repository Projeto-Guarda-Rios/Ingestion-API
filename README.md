# Guarda-Rios Ingestion API

FastAPI service that receives water-quality readings from AquaNode sensor
stations and writes them to InfluxDB.

Two ingestion paths:

| Path | Protocol | Payload     | Used by                        |
|------|----------|-------------|--------------------------------|
| MQTT | MQTT 5   | CBOR batch  | **NBIOT stations (primary)**   |
| HTTP | HTTP/1.1 | JSON        | Admin, manual tests, backfills |

The MQTT path is optimised for the 2 MB/month data budget typical of NBIOT
SIMs — see [Data budget](#data-budget) below.

## Project structure

```
guarda-rios-api/
├── main.py          # FastAPI app, lifespan, HTTP endpoints
├── config.py        # Settings loaded from .env (Influx + MQTT)
├── influx.py        # InfluxDB client and write helpers
├── auth.py          # HTTP X-API-Key auth + known-station-IDs
├── models.py        # Shared Pydantic models
├── ingest.py        # Protocol-agnostic reading → Influx pipeline
├── codec.py         # Compact CBOR batch codec
├── mqtt_client.py   # MQTT subscriber (paho-mqtt)
├── test_ingest.py   # HTTP test publisher
├── test_mqtt.py     # MQTT test publisher (NBIOT simulator)
└── requirements.txt
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env     # edit Influx + MQTT values
uvicorn main:app --host 0.0.0.0 --port 8000
```

The MQTT subscriber starts automatically with the FastAPI app (via the
`lifespan` hook) and shuts down cleanly on exit. Set `MQTT_ENABLED=false`
to disable it — useful in CI or when running the HTTP path standalone.

## Stations

Generate a station API key (still needed for the HTTP path):

```bash
openssl rand -hex 32
```

Add to `STATION_KEYS` in `.env`:

```
STATION_KEYS=abc123...:station_001,def456...:station_002
```

Each station's `station_id` is also the topic segment it publishes to over
MQTT. **Auth over MQTT is enforced at the broker**, not by this service —
see [MQTT broker configuration](#mqtt-broker-configuration).

## MQTT ingestion

### Topic structure

```
{prefix}/{station_id}/readings    # prefix = MQTT_TOPIC_PREFIX, default "stations"
```

The server subscribes to `stations/+/readings` and infers `station_id` from
the topic — the payload never carries it, saving bytes on every publish.

### Payload format

CBOR map with integer keys, ~10-15 bytes per reading. See `codec.py` for
the full schema. Summary:

```
{
  0: base_timestamp_epoch_seconds,
  1: [
    { 1: temp*100, 2: turbidity*100, 0: offset_s, 3: ph*100?, 4: tds? },
    ...
  ]
}
```

Optional fields are omitted entirely (not `null`) when the sensor is absent.

Recommended QoS is **1** (at-least-once). InfluxDB writes with a fixed
`(station_id, timestamp)` key are idempotent, so redelivered duplicates are
harmless.

### MQTT broker configuration

Use Mosquitto (or any MQTT 5 broker). Per-station ACL example:

```
# /etc/mosquitto/conf.d/guarda-rios.conf
allow_anonymous false
password_file /etc/mosquitto/passwd
acl_file     /etc/mosquitto/acl
```

```
# /etc/mosquitto/acl
user station_001
topic write stations/station_001/readings

user station_002
topic write stations/station_002/readings

user guarda-rios-ingest
topic read stations/+/readings
```

This ensures station_001 cannot publish on station_002's topic even if its
password leaks.

### Test publisher

```bash
# One batch of 20 readings
python test_mqtt.py --station station_001 --count 20 \
  --mqtt-user station_001 --mqtt-pass <broker-password>

# Loop: 10 readings per batch, one reading per 60s
python test_mqtt.py --station station_001 --batch-size 10 --interval 60 --loop
```

## HTTP ingestion

Retained for admin/debug/backfill. Two endpoints:

```bash
# Single reading (legacy)
curl -X POST http://localhost:8000/ingest \
  -H "X-API-Key: <station-key>" -H "Content-Type: application/json" \
  -d '{ "temperature": 18.3, "turbidity": 12.0, "ph": 7.42 }'

# JSON batch
curl -X POST http://localhost:8000/ingest/batch \
  -H "X-API-Key: <station-key>" -H "Content-Type: application/json" \
  -d '{ "readings": [
        {"temperature": 18.3, "turbidity": 12.0, "timestamp": "2026-04-18T12:00:00Z"},
        {"temperature": 18.4, "turbidity": 12.2, "timestamp": "2026-04-18T12:01:00Z"}
      ] }'
```

## InfluxDB data model

- **Measurement**: `water_quality`
- **Tags**: `station_id`
- **Fields**: `temperature`, `turbidity`, `ph`, `tds`

Identical across both paths — downstream dashboards need no changes.

## Data budget

NBIOT plans are typically capped at 2 MB / month. Rough costs per upload:

| Path              | Per reading | 100-reading batch | Monthly budget @ 1 batch/h |
|-------------------|-------------|-------------------|-----------------------------|
| HTTP + JSON       | ~150 B      | ~15 KB + headers  | ~11 MB (over budget)        |
| MQTT + CBOR batch | ~12 B       | ~1.2 KB + headers | ~870 KB                     |

The MQTT path gives stations ~15× headroom against the NBIOT budget while
preserving full sampling granularity.

## Endpoints

| Method | Path            | Description                                  |
|--------|-----------------|----------------------------------------------|
| POST   | `/ingest`       | Submit a single reading (JSON)               |
| POST   | `/ingest/batch` | Submit a batch of readings (JSON)            |
| GET    | `/health`       | Liveness check                               |
| GET    | `/docs`         | Swagger UI                                   |
