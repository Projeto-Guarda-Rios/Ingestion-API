# Guarda-Rios UDP Ingestion Service

UDP listener that receives binary station packets and writes water-quality
samples into InfluxDB.

## Active transport

- UDP only
- Default bind: `0.0.0.0:40416/udp`
- Measurement: `water_quality`
- Tags: `station_id`
- Fields: `temperature`, `turbidity`

## Packet format

All integers are big-endian.

```text
1 byte  version
2 bytes station_id
4 bytes packet_counter
4 bytes start_timestamp
2 bytes interval_s
1 byte  sample_count
N x sensor sample
16 bytes auth tag
```

Each sensor sample is 4 bytes:

```text
2 bytes temperature  fixed-point signed int, scale 100
2 bytes turbidity    fixed-point signed int, scale 100
```

The server expands timestamps as:

```text
sample_timestamp = start_timestamp + (sample_index * interval_s)
```

## Authentication

The last 16 bytes are a truncated `HMAC-SHA256` over the whole packet except
the auth tag itself.

- Secret source: `STATION_KEYS`
- Matching station label source: `UDP_STATION_MAP`
- Current mapping in `.env`:
  - `1 -> test_station`
  - `2 -> I-Fest`

## Configuration

Example `.env`:

```env
INFLUX_URL=http://localhost:8086
INFLUX_TOKEN=
INFLUX_ORG=
INFLUX_BUCKET=

STATION_KEYS=secure_API_1:test_station,secure_API_2:I-Fest
UDP_HOST=0.0.0.0
UDP_PORT=40416
UDP_STATION_MAP=1:test_station,2:I-Fest
```

If `UDP_STATION_MAP` is omitted, station numbers fall back to the order of
`STATION_KEYS`: `1`, `2`, `3`, ...

## Running

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the listener:

```bash
python udp_server.py
```

Compatibility entrypoint:

```bash
python main.py
```

## Test sender

Use the built-in UDP simulator:

```bash
python test_udp.py --host 127.0.0.1 --port 40416 --station-id 1 --secret <station-secret>
```

## Removed

- HTTP ingestion endpoints
- FastAPI and Uvicorn runtime
- MQTT subscriber logic
- Mosquitto deployment config
