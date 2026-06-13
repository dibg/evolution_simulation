#!/usr/bin/env bash
# Build ONE self-contained executable of the game. It bundles Python, pygame and
# SDL inside a single file, so the result runs with NO Python/pip/venv on the
# target machine — just click it (or run it) and it works.
#
#   ./build.sh   ->   dist/predator-prey-evolution
#
# Note: a binary built here runs on this machine and any Linux with the same or
# newer glibc. For an older distro (e.g. Linux Mint), run ./build.sh on that
# machine to get a native single file there.
cd "$(dirname "$0")" || exit 1
PY=./.venv/bin/python

if [ ! -x "$PY" ]; then
    echo "Setting up .venv first…"
    python3 -m venv .venv && ./.venv/bin/pip install --quiet -r requirements.txt \
        || { echo "venv setup failed (need python3-venv + internet)"; exit 1; }
fi

echo "Installing PyInstaller…"
"$PY" -m pip install --upgrade pip >/dev/null 2>&1
"$PY" -m pip install --quiet pyinstaller || { echo "could not install pyinstaller"; exit 1; }

echo "Building single-file executable…"
rm -rf build dist ./*.spec
"$PY" -m PyInstaller --onefile --clean --noconfirm \
    --name predator-prey-evolution \
    --add-data "config.json:." \
    --hidden-import gui \
    --hidden-import ui \
    main.py || { echo "build failed"; exit 1; }

echo
echo "Done  ->  $(pwd)/dist/predator-prey-evolution"
echo "Run it with ./dist/predator-prey-evolution (or double-click it in your file manager)."
