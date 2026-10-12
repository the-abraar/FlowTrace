#!/usr/bin/env bash
# One command for lint, build, tests, stray files, firmware config. `--fast` = lint + stray files only.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
FAST=0; [ "${1:-}" = "--fast" ] && FAST=1

PY=${PYTHON:-}
[ -n "$PY" ] || PY=$(command -v python3.11 || command -v python3.12 || true)
[ -n "$PY" ] || { echo "Python 3.11 or 3.12 required (3.14 breaks scipy); set \$PYTHON" >&2; exit 2; }
VENV=${CHECK_VENV:-$HOME/.cache/flow-trace-check-venv}      # core deps + ruff
AVENV=${CHECK_VENV_AGENT:-$HOME/.cache/flow-trace-check-venv-agent}  # core + agent extras

mkvenv() { [ -x "$1/bin/python" ] || "$PY" -m venv "$1"; "$1/bin/pip" -q install "${@:2}" 2>&1 | grep -v notice || true; }

NAMES=(); RES=()
step() { # name cmd...
  local n=$1; shift; echo "=== $n"
  if "$@"; then RES+=(pass); else RES+=(FAIL); fi; NAMES+=("$n")
}

stray() { local f; f=$(find . \( -name node_modules -o -name .venv -o -name .git -o -name dist -o -name build \) -prune -o \
  \( -name '*-e' -o -name '*.orig' -o -name '*.rej' -o -name '*.bak' \) -type f -print); [ -z "$f" ] || { echo "$f"; return 1; }; }

fw_config() { local bad=0 f
  for f in firmware/scanner/config.h firmware/gateway/config.h; do # beacon is a BLE transmitter: no backend link
    grep -Eq '^#define[[:space:]]+BACKEND_URL[[:space:]]+"[^"]*:8000/' "$f" || { echo "$f: BACKEND_URL on port 8000 missing"; bad=1; }
    grep -Eq '^#define[[:space:]]+API_KEY[[:space:]]' "$f" || { echo "$f: API_KEY missing"; bad=1; }
  done
  if grep -rnE '\b8080\b' --include='*.ino' firmware; then echo "literal 8080 in .ino"; bad=1; fi
  return $bad; }

backend_tests() { (cd backend && INGEST_API_KEY=${INGEST_API_KEY:-test-ingest} "$VENV/bin/python" -m pytest -q tests &&
  INGEST_API_KEY=${INGEST_API_KEY:-test-ingest} "$VENV/bin/python" -m pytest -q $(ls tests/test_*.py | sort -r)); }
tools_tests() { (cd tools && "$VENV/bin/python" -m pytest -q tests && "$VENV/bin/python" -m pytest -q $(ls tests/test_*.py | sort -r)); }
agent_import() { (cd backend && "$AVENV/bin/python" -c "import agent.flowtrace_agent"); }
node_check() { local f rc=0; for f in $(find dashboard -name '*.js' -not -path '*/node_modules/*' -not -path '*/dist/*'); do node --check "$f" || rc=1; done; return $rc; }
dash_build() { (cd dashboard && { [ -d node_modules ] || npm ci --silent; } && npm run build --silent); }

mkvenv "$VENV" ruff -r backend/requirements.txt
step "lint (ruff)" "$VENV/bin/ruff" check --config ruff.toml .
step "stray files" stray
step "firmware config" fw_config
if [ -n "$(find . -name node_modules -prune -o \( -name '*.html' -o -name '*.js' -o -name '*.jsx' -o -name '*.tsx' \) -print -quit)" ]; then
  step "unsafe html" scripts/lint-innerhtml.sh
  step "node --check" node_check
fi
if [ "$FAST" = 0 ]; then
  step "dashboard build" dash_build
  step "backend tests (core only, fwd+rev)" backend_tests
  step "tools tests (fwd+rev)" tools_tests
  mkvenv "$AVENV" -r backend/requirements-agent.txt
  step "agent import (extras)" agent_import
fi

echo; printf '%-40s | %s\n' step result; printf -- '-----------------------------------------+-------\n'
rc=0; for i in "${!NAMES[@]}"; do printf '%-40s | %s\n' "${NAMES[$i]}" "${RES[$i]}"; [ "${RES[$i]}" = pass ] || rc=1; done
exit $rc
