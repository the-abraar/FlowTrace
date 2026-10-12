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
MQTT topic: `flowtrace/nodes/<NODE_ID>/readings`. Unknown node IDs are reported in `unknown_nodes` of the POST response.

## Auth
- `INGEST_API_KEY`: required for `POST /api/v1/readings` (header `X-API-Key`, constant-time compare). If unset, writes are **refused (503)** and a startup warning is logged, unless env `DEBUG` (or `DEV`) is `1`/`true`, which keeps them open for local dev.
- `READ_API_KEY`: optional. If set, all GETs and `/ws` need it (`X-API-Key` header, or `?key=` for the websocket/browser). If unset, reads are open and startup logs a warning.
- MQTT: set `MQTT_USERNAME`/`MQTT_PASSWORD` (applied to the client; broker ACLs enforce who may publish). The node ID is taken from the topic `flowtrace/nodes/<id>/readings`; a payload `node_id` that differs is dropped.
- Dashboard (not changed here): it must be given the read key, e.g. a Vite env var appended as `?key=` on `/ws` and sent as `X-API-Key`.
- `GET /api/v1/nodes/{id}/readings` caps `limit` at 1..1000.
- Device tracking: devices idle > `DEVICE_TTL_SECONDS` (600) are evicted from the position loop; beyond `MAX_TRACKED_DEVICES` (5000) new devices are rejected (no Device row, counted warning). Existing Device DB rows are not purged.
