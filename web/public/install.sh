#!/usr/bin/env bash
# ghost-racer backend bootstrap
# Usage: curl -fsSL http://localhost:3000/install.sh | bash
#
# Creates ./.venv and installs uvicorn[standard] + fastapi so the dashboard
# can reach a Python backend on http://localhost:8000.

set -euo pipefail

# ── pretty output ───────────────────────────────────────────────────────────
if [ -t 1 ]; then
  BOLD=$'\033[1m'; DIM=$'\033[2m'; RED=$'\033[31m'
  GRN=$'\033[32m'; YLW=$'\033[33m'; CYN=$'\033[36m'; RST=$'\033[0m'
else
  BOLD=""; DIM=""; RED=""; GRN=""; YLW=""; CYN=""; RST=""
fi

say()  { printf "%s\n" "${CYN}▸${RST} $*"; }
ok()   { printf "%s\n" "${GRN}✓${RST} $*"; }
warn() { printf "%s\n" "${YLW}!${RST} $*"; }
die()  { printf "%s\n" "${RED}✗${RST} $*" >&2; exit 1; }

printf "%s\n" "${BOLD}ghost-racer backend installer${RST}"
printf "%s\n" "${DIM}venv + uvicorn + fastapi${RST}"
echo

# ── locate target dir ───────────────────────────────────────────────────────
TARGET="${GHOST_RACER_DIR:-$PWD}"
cd "$TARGET" || die "cannot cd into $TARGET"
say "installing into ${BOLD}$TARGET${RST}"

# ── python3 ─────────────────────────────────────────────────────────────────
if ! command -v python3 >/dev/null 2>&1; then
  die "python3 not found. install python 3.10+ first (https://www.python.org/downloads/)"
fi
PY_VER="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
ok "python3 → $PY_VER"

# ── venv module ─────────────────────────────────────────────────────────────
if ! python3 -c 'import venv' >/dev/null 2>&1; then
  warn "python3-venv missing. attempting to install…"
  if   command -v apt-get >/dev/null 2>&1; then sudo apt-get update && sudo apt-get install -y python3-venv
  elif command -v dnf     >/dev/null 2>&1; then sudo dnf install -y python3-virtualenv || true
  elif command -v pacman  >/dev/null 2>&1; then sudo pacman -Sy --noconfirm python-virtualenv || true
  elif command -v brew    >/dev/null 2>&1; then : # bundled with brew python
  else die "could not auto-install venv. install python3-venv manually."; fi
  python3 -c 'import venv' >/dev/null 2>&1 || die "venv still unavailable after install"
fi
ok "venv module available"

# ── create venv ─────────────────────────────────────────────────────────────
VENV=".venv"
if [ -d "$VENV" ] && [ -x "$VENV/bin/python" ]; then
  ok "reusing existing $VENV"
else
  say "creating $VENV"
  python3 -m venv "$VENV"
  ok "venv created"
fi

# ── install uvicorn ─────────────────────────────────────────────────────────
say "upgrading pip"
"$VENV/bin/python" -m pip install --quiet --upgrade pip

say "installing uvicorn[standard] + fastapi"
"$VENV/bin/python" -m pip install --quiet --upgrade 'uvicorn[standard]' fastapi

UVICORN_VER="$("$VENV/bin/python" -m uvicorn --version 2>&1 | head -n1)"
ok "$UVICORN_VER"

# ── how to run ──────────────────────────────────────────────────────────────
echo
printf "%s\n" "${BOLD}done.${RST} start the backend with:"
echo
printf "  %s\n" "${CYN}source $VENV/bin/activate${RST}"
printf "  %s\n" "${CYN}python -m uvicorn ghost_racer.server.app:app --host 0.0.0.0 --port 8000${RST}"
echo
printf "%s\n" "${DIM}then refresh the dashboard.${RST}"
