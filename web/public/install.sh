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

# ── locate project root ─────────────────────────────────────────────────────
# Walk up from $PWD looking for the ghost_racer/ package. If we don't find it
# anywhere up the tree, clone the repo into ./ghost-racer.
REPO_URL="${GHOST_RACER_REPO:-https://github.com/ArushNo1/ghost-racer.git}"

find_project_root() {
  local d="${GHOST_RACER_DIR:-$PWD}"
  while [ "$d" != "/" ]; do
    if [ -d "$d/ghost_racer" ] && [ -f "$d/requirements.txt" ]; then
      printf '%s\n' "$d"
      return 0
    fi
    d="$(dirname "$d")"
  done
  return 1
}

if TARGET="$(find_project_root)"; then
  say "found existing checkout at ${BOLD}$TARGET${RST}"
else
  command -v git >/dev/null 2>&1 || die "git not found. install git or cd into an existing checkout."
  CLONE_DIR="${GHOST_RACER_DIR:-$PWD/ghost-racer}"
  if [ -d "$CLONE_DIR/.git" ]; then
    say "updating existing clone at ${BOLD}$CLONE_DIR${RST}"
    git -C "$CLONE_DIR" pull --ff-only || warn "git pull failed; continuing with current checkout"
  else
    say "cloning ${BOLD}$REPO_URL${RST} → ${BOLD}$CLONE_DIR${RST}"
    git clone --depth 1 "$REPO_URL" "$CLONE_DIR" || die "git clone failed"
  fi
  TARGET="$CLONE_DIR"
fi
cd "$TARGET" || die "cannot cd into $TARGET"
[ -d "ghost_racer" ] || die "$TARGET doesn't look like the ghost-racer repo (no ghost_racer/ dir)"

# ── pick a python ───────────────────────────────────────────────────────────
# Pin to 3.12 — mediapipe 0.10.21 + torch don't have 3.13/3.14 wheels.
# Override with GHOST_RACER_PYTHON=/path/to/python if you know better.
PIN_VER="3.12"

pick_python() {
  if [ -n "${GHOST_RACER_PYTHON:-}" ]; then
    command -v "$GHOST_RACER_PYTHON" >/dev/null 2>&1 || return 1
    printf '%s\n' "$GHOST_RACER_PYTHON"
    return 0
  fi
  for cand in "python$PIN_VER" python3.12 python3.11; do
    if command -v "$cand" >/dev/null 2>&1; then
      printf '%s\n' "$cand"
      return 0
    fi
  done
  return 1
}

if ! PY="$(pick_python)"; then
  warn "python$PIN_VER not found. attempting to install…"
  if   command -v dnf     >/dev/null 2>&1; then sudo dnf install -y "python$PIN_VER" || true
  elif command -v apt-get >/dev/null 2>&1; then sudo apt-get update && sudo apt-get install -y "python$PIN_VER" "python$PIN_VER-venv" || true
  elif command -v pacman  >/dev/null 2>&1; then sudo pacman -Sy --noconfirm python312 || true
  elif command -v brew    >/dev/null 2>&1; then brew install "python@$PIN_VER" || true
  else die "no supported package manager. install python$PIN_VER manually."; fi
  PY="$(pick_python)" || die "python$PIN_VER still unavailable after install. set GHOST_RACER_PYTHON=/path/to/python3.12 and re-run."
fi
PY_VER="$("$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
ok "python → $PY ($PY_VER)"

# ── venv module ─────────────────────────────────────────────────────────────
if ! "$PY" -c 'import venv' >/dev/null 2>&1; then
  warn "$PY-venv missing. attempting to install…"
  if   command -v dnf     >/dev/null 2>&1; then sudo dnf install -y "python$PIN_VER" || true
  elif command -v apt-get >/dev/null 2>&1; then sudo apt-get update && sudo apt-get install -y "python$PIN_VER-venv" || true
  elif command -v pacman  >/dev/null 2>&1; then sudo pacman -Sy --noconfirm python312 || true
  elif command -v brew    >/dev/null 2>&1; then : # bundled
  else die "could not auto-install venv. install python$PIN_VER-venv manually."; fi
  "$PY" -c 'import venv' >/dev/null 2>&1 || die "venv still unavailable after install"
fi
ok "venv module available"

# ── create venv ─────────────────────────────────────────────────────────────
# If an existing venv has the wrong python version, recreate it — installing
# 3.14-incompatible deps into it will fail otherwise.
VENV=".venv"
recreate_venv=0
if [ -d "$VENV" ] && [ -x "$VENV/bin/python" ]; then
  EXISTING_VER="$("$VENV/bin/python" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo "?")"
  if [ "$EXISTING_VER" = "$PY_VER" ]; then
    ok "reusing existing $VENV (python $EXISTING_VER)"
  else
    warn "existing $VENV uses python $EXISTING_VER, want $PY_VER — recreating"
    recreate_venv=1
  fi
else
  recreate_venv=1
fi

if [ "$recreate_venv" = "1" ]; then
  rm -rf "$VENV"
  say "creating $VENV with $PY"
  "$PY" -m venv "$VENV"
  ok "venv created"
fi

# ── install deps ────────────────────────────────────────────────────────────
say "upgrading pip"
"$VENV/bin/python" -m pip install --quiet --upgrade pip

if [ -f requirements.txt ]; then
  say "installing requirements.txt (uvicorn, fastapi, opencv, mediapipe, torch, …)"
  printf "%s\n" "${DIM}  this can take a few minutes on first run.${RST}"
  "$VENV/bin/python" -m pip install --upgrade -r requirements.txt
else
  warn "no requirements.txt — installing minimal uvicorn[standard] + fastapi only"
  "$VENV/bin/python" -m pip install --quiet --upgrade 'uvicorn[standard]' fastapi
fi

UVICORN_VER="$("$VENV/bin/python" -m uvicorn --version 2>&1 | head -n1)"
ok "$UVICORN_VER"

# ── place run.sh at repo root ───────────────────────────────────────────────
# Source of truth lives in web/public/run.sh (so it ships with the dashboard).
# Copy/symlink it to the repo root for convenience.
if [ -f "web/public/run.sh" ]; then
  cp web/public/run.sh ./run.sh
  chmod +x ./run.sh
  ok "installed run.sh"
fi

# ── npm deps for the dashboard ──────────────────────────────────────────────
if [ -d "web" ] && [ -f "web/package.json" ]; then
  if ! command -v npm >/dev/null 2>&1; then
    warn "npm not found. attempting to install node…"
    if   command -v dnf     >/dev/null 2>&1; then sudo dnf install -y nodejs npm || true
    elif command -v apt-get >/dev/null 2>&1; then sudo apt-get update && sudo apt-get install -y nodejs npm || true
    elif command -v pacman  >/dev/null 2>&1; then sudo pacman -Sy --noconfirm nodejs npm || true
    elif command -v brew    >/dev/null 2>&1; then brew install node || true
    else warn "no supported package manager for node. install node 20+ manually."; fi
  fi
  if command -v npm >/dev/null 2>&1; then
    NODE_VER="$(node -v 2>/dev/null || echo unknown)"
    ok "node → $NODE_VER"
    if [ -d "web/node_modules" ]; then
      say "updating dashboard npm deps"
    else
      say "installing dashboard npm deps (web/)"
    fi
    ( cd web && npm install --no-audit --no-fund --loglevel=error )
    ok "npm deps installed"
  else
    warn "skipping npm install — node not available"
  fi
else
  warn "no web/ dir — skipping dashboard install"
fi

# ── how to run ──────────────────────────────────────────────────────────────
# Pick the activate script for the user's shell. SHELL is set by login;
# fish/csh need their own activate variants.
case "${SHELL:-}" in
  *fish) ACTIVATE="source $VENV/bin/activate.fish" ;;
  *csh)  ACTIVATE="source $VENV/bin/activate.csh" ;;
  *)     ACTIVATE="source $VENV/bin/activate" ;;
esac

echo
printf "%s\n" "${BOLD}done.${RST} start everything (backend + dashboard) with:"
echo
printf "  %s\n" "${CYN}cd $TARGET${RST}"
printf "  %s\n" "${CYN}./run.sh${RST}"
echo
printf "%s\n" "${DIM}then open ${BOLD}http://localhost:3000${RST}${DIM} in your browser.${RST}"
printf "%s\n" "${DIM}prefer running them separately?${RST}"
printf "  %s\n" "${DIM}$ACTIVATE  &&  python -m uvicorn ghost_racer.server.app:app --host 0.0.0.0 --port 8000${RST}"
printf "  %s\n" "${DIM}cd web  &&  npm run dev${RST}"
