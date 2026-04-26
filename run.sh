#!/usr/bin/env bash
# ghost-racer — start the python backend (uvicorn) and the dashboard (next dev)
# together. Ctrl-C cleans up both.
#
# Usage:  ./run.sh

set -euo pipefail
cd "$(dirname "$0")"

if [ -t 1 ]; then
  BOLD=$'\033[1m'; DIM=$'\033[2m'; RED=$'\033[31m'
  GRN=$'\033[32m'; YLW=$'\033[33m'; CYN=$'\033[36m'; RST=$'\033[0m'
else
  BOLD=""; DIM=""; RED=""; GRN=""; YLW=""; CYN=""; RST=""
fi

die() { printf "%s\n" "${RED}✗${RST} $*" >&2; exit 1; }

[ -d "ghost_racer" ] || die "run from the ghost-racer repo root."
[ -d "web" ]         || die "no web/ dir found."
[ -x ".venv/bin/python" ] || die ".venv is missing. run install.sh first."
[ -d "web/node_modules" ] || die "web/node_modules missing. run install.sh first."

PY="$PWD/.venv/bin/python"
PORT_API="${GHOST_RACER_API_PORT:-8000}"
PORT_WEB="${GHOST_RACER_WEB_PORT:-3000}"

printf "%s\n" "${BOLD}ghost-racer${RST} ${DIM}— starting backend + dashboard${RST}"
printf "  ${CYN}backend${RST}   http://localhost:%s\n" "$PORT_API"
printf "  ${CYN}dashboard${RST} http://localhost:%s\n" "$PORT_WEB"
echo

# start uvicorn in the background. --reload picks up server-side edits.
"$PY" -m uvicorn ghost_racer.server.app:app \
  --host 0.0.0.0 --port "$PORT_API" --reload \
  2>&1 | sed -u "s/^/${GRN}[api]${RST} /" &
API_PID=$!

# start next dev. inherits PORT via env var.
( cd web && PORT="$PORT_WEB" npm run dev ) \
  2>&1 | sed -u "s/^/${CYN}[web]${RST} /" &
WEB_PID=$!

cleanup() {
  printf "\n%s\n" "${YLW}stopping…${RST}"
  # kill the whole process groups so child workers die too.
  kill "$API_PID" "$WEB_PID" 2>/dev/null || true
  wait "$API_PID" "$WEB_PID" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

# if either process dies, tear the other down.
wait -n "$API_PID" "$WEB_PID" || true
cleanup
