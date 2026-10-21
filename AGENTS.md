# AGENTS.md

Run `scripts/check.sh` before declaring done; `--fast` (lint, stray files, firmware config, HTML sinks) is the pre-commit hook (`core.hooksPath` is set to `.githooks` locally; re-run `git config core.hooksPath .githooks` on a fresh clone). Standards: `CODING_STANDARDS.md`.

- Python 3.11 or 3.12 only (3.14 breaks scipy). Venvs live outside the repo: `~/.cache/flow-trace-check-venv` (core) and `...-agent` (core + `backend/requirements-agent.txt`). Override with `$PYTHON`, `$CHECK_VENV`.
- `backend/requirements.txt` holds pytest and everything tests need; `requirements-agent.txt` (langchain/openai) is optional. check.sh runs backend tests core-only, so backend code must not import `agent` at module level.
- Backend tests need `INGEST_API_KEY` or `DEBUG`; `backend/tests/conftest.py` sets `INGEST_API_KEY=test-ingest`. Run pytest from `backend/` (and `tools/` for `tools/tests`).
- Dashboard has no ESLint or test framework: check.sh runs `node --check` on `.js`, `npm run build`, and `node --test` on `dashboard/src/utils/*.test.js`.
- Firmware (`firmware/*`, Arduino) cannot be compiled here; check.sh only greps `config.h` (BACKEND_URL on :8000, API_KEY) and rejects a literal `8080` in `.ino`. Beacon has no backend link, so it is exempt.
- Known failing: `ruff` lint (~30 pre-existing default-rule hits: E401, E702, F401, F841, E712). Left visible on purpose; fix, do not loosen `ruff.toml`.
- Claims about product state: `judge.md` (read when changing scope, demo data or accuracy claims; never edit it).
