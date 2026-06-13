#!/usr/bin/env bash
# Create a portable tarball of the project (without the machine-specific .venv
# or Python caches) so you can copy it to another Linux machine.
cd "$(dirname "$0")" || exit 1
dir="$(basename "$(pwd)")"
out="../predator-prey-evolution.tar.gz"
tar --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc' \
    --exclude='build' --exclude='dist' --exclude='*.spec' \
    --exclude='*.tar.gz' -czf "$out" -C .. "$dir"
echo "Created: $(cd .. && pwd)/predator-prey-evolution.tar.gz"
echo
echo "On the new machine:"
echo "  tar -xzf predator-prey-evolution.tar.gz"
echo "  cd $dir"
echo "  ./setup.sh   # one-time (installs deps), then:"
echo "  ./run.sh"
