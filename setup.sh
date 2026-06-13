#!/usr/bin/env bash
# One-time setup for a fresh Linux system (tested with Linux Mint / Ubuntu).
# Installs the Python venv/pip system packages if missing, builds the local
# .venv, and optionally adds a desktop menu entry. Run once, then use ./run.sh.
cd "$(dirname "$0")" || exit 1
PY="${PYTHON:-python3}"

echo "== Predator-Prey Evolution — setup =="

if ! command -v "$PY" >/dev/null 2>&1; then
    echo "python3 is not installed."
    if command -v apt-get >/dev/null 2>&1; then
        echo "Install it with:  sudo apt install python3"
    fi
    exit 1
fi

# Ensure venv + pip support. On apt/dnf systems, offer to install it.
if ! "$PY" -c "import ensurepip, venv" >/dev/null 2>&1; then
    echo "Python venv/pip support is missing — installing system packages…"
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update && sudo apt-get install -y python3-venv python3-pip
    elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y python3 python3-pip
    elif command -v pacman >/dev/null 2>&1; then
        sudo pacman -S --needed python python-pip
    else
        echo "Please install your distro's python3-venv and python3-pip packages, then re-run." >&2
        exit 1
    fi
fi

echo "Building .venv and installing dependencies…"
rm -rf .venv
"$PY" -m venv .venv || { echo "venv creation failed" >&2; exit 1; }
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt

echo
echo "Setup complete. Launch with:  ./run.sh"

# Optional desktop menu entry (Mint/Cinnamon, GNOME, KDE, …).
printf "Add a desktop menu entry? [y/N] "
read -r ans
if [ "$ans" = "y" ] || [ "$ans" = "Y" ]; then
    apps="$HOME/.local/share/applications"
    here="$(pwd)"
    mkdir -p "$apps"
    cat > "$apps/predator-prey-evolution.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Predator–Prey Evolution
Comment=Watch creatures hunt, flee, breed and evolve
Exec=$here/run.sh
Path=$here
Terminal=false
Categories=Science;Education;
EOF
    chmod +x "$apps/predator-prey-evolution.desktop"
    command -v update-desktop-database >/dev/null 2>&1 && \
        update-desktop-database "$apps" >/dev/null 2>&1
    echo "Added 'Predator–Prey Evolution' to your applications menu."
fi
