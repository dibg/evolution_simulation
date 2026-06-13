#!/usr/bin/env bash
# Launch the Predator-Prey Evolution simulation.
# On a new machine (or if the bundled .venv is missing/stale) this rebuilds the
# local virtualenv and installs dependencies automatically — then runs the game.
cd "$(dirname "$0")" || exit 1
PY="${PYTHON:-python3}"

# Does the local venv exist AND actually work on this machine?
need_setup() {
    if [ ! -x ".venv/bin/python" ]; then return 0; fi
    if ! ./.venv/bin/python -c "import pygame" >/dev/null 2>&1; then return 0; fi
    return 1
}

if need_setup; then
    echo "First-time setup: building local .venv and installing dependencies…"
    if ! command -v "$PY" >/dev/null 2>&1; then
        echo "ERROR: '$PY' not found. Install Python 3 first." >&2
        exit 1
    fi
    if ! "$PY" -c "import ensurepip, venv" >/dev/null 2>&1; then
        cat >&2 <<'EOF'
ERROR: Python's venv/pip support is missing.
  Linux Mint / Ubuntu / Debian:  sudo apt install python3-venv python3-pip
  Fedora:                        sudo dnf install python3 python3-pip
  Arch / Manjaro:                sudo pacman -S python python-pip
Then re-run ./run.sh   (or run ./setup.sh for a guided install).
EOF
        exit 1
    fi
    rm -rf .venv
    "$PY" -m venv .venv || { echo "ERROR: could not create .venv" >&2; exit 1; }
    ./.venv/bin/python -m pip install --upgrade pip >/dev/null 2>&1
    if ! ./.venv/bin/python -m pip install -r requirements.txt; then
        echo "ERROR: dependency install failed (internet needed on first run)." >&2
        exit 1
    fi
    echo "Setup complete."
fi

exec ./.venv/bin/python main.py "$@"
