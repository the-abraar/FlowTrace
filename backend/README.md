# FlowTrace backend

> **Python:** use 3.11 or 3.12. On 3.14, `scipy==1.13.1` has no wheel and `pip install -r requirements.txt` fails.


## How to run
```
cd backend
python3.11 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt        # optional LLM agent: pip install -r requirements-agent.txt
uvicorn main:app --port 8000           # firmware posts to :8000/api/v1/readings
pytest tests                           # end-to-end ingest -> position test (sqlite)
```
MQTT topic: `flowtrace/nodes/<NODE_ID>/readings`. Broker end-to-end test: `docker compose up -d mosquitto` then `MQTT_E2E_BROKER=localhost:1883 pytest tests/test_mqtt_broker_e2e.py` (skipped without the env var). Unknown node IDs are reported in `unknown_nodes` of the POST response.

## Auth
- `INGEST_API_KEY`: required for `POST /api/v1/readings` (header `X-API-Key`, constant-time compare). If unset, writes are **refused (503)** and a startup warning is logged, unless env `DEBUG` (or `DEV`) is `1`/`true`, which keeps them open for local dev.
- `READ_API_KEY`: optional. If set, all GETs and `/ws` need it (`X-API-Key` header, or `?key=` for the websocket/browser). If unset, reads are open and startup logs a warning.
- MQTT: set `MQTT_USERNAME`/`MQTT_PASSWORD` (applied to the client; broker ACLs enforce who may publish). The node ID is taken from the topic `flowtrace/nodes/<id>/readings`; a payload `node_id` that differs is dropped.
- Dashboard: set `VITE_READ_API_KEY` (same value as `READ_API_KEY`) at build/dev time; it is sent as `X-API-Key` on REST and `?key=` on `/ws`. It is baked into the JS bundle, so anyone who can load the dashboard can read it.
- `GET /api/v1/nodes/{id}/readings` caps `limit` at 1..1000.
- Device tracking: devices idle > `DEVICE_TTL_SECONDS` (600) are evicted from the position loop; beyond `MAX_TRACKED_DEVICES` (5000) new devices are rejected (no Device row, counted warning). Device DB rows unseen for `DEVICE_RETENTION_DAYS` (30) are deleted hourly with their readings, positions and sessions.
- Dedupe: a reading with the firmware's `ts_ms` is stored once per (node, device, `ts_ms`); a retried batch reports them as `duplicates`. Readings without `ts_ms` are not deduped.
