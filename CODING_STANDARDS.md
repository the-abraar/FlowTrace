# Coding standards (judgement calls a linter cannot enforce)

- **Disclose**: the dashboard shows an explicit demo/offline banner whenever data is mock, cached or the backend is unreachable. Never invent live numbers (hardcoded counts, random fallbacks) without that label. Why: a demo once presented fabricated figures as live.
- **Mark**: any accuracy, latency or coverage claim (docs, marketing, UI) that has no measurement behind it carries `UNVERIFIED`. Measured claims cite the run (`tools/evaluate_accuracy.py` output, date, setup).
- **Calibrate**: node positions, path-loss exponent, RSSI at 1 m and zone bounds come from calibrated config (output of `tools/calibrate_rssi.py`), never literals in code. Why: venue geometry changes; a literal silently breaks positioning.
- **Compare-and-set**: every state-changing write is `UPDATE ... WHERE id=? AND status=?`; check rowcount and return 409 on conflict.
- **Declare auth**: every endpoint states its auth decision (`INGEST_API_KEY` for write, read key for read); unauthenticated is a commented, deliberate choice.
- **Fail closed**: secrets (`INGEST_API_KEY`, firmware `API_KEY`) have no accepted default; the `CHANGE_ME` placeholder must be rejected outside `DEBUG`.
- **Cap**: unbounded input (query `limit`, batch size of readings, tracked devices, WebSocket clients) has an explicit cap.
- **Derive**: mocks, fixtures and the firmware payload shape come from the backend schema; a test fails when firmware JSON fields, ports or MQTT topics drift from `backend/ingestion`.
- **Own**: identity checks compare device owner/venue, not row ids.
- **Idempotent**: reading dedupe keys come from the node (`node_id`, `ts_ms`), never generated per request, so retries do not double count.
- **Honest scope**: do not edit `judge.md`; log new findings by adding an Update there only when asked.
