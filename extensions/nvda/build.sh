#!/usr/bin/env bash
# Package the EYEWAZ NVDA add-on into eyewaz-<version>.nvda-addon
# (a .nvda-addon is just a zip with manifest.ini at the root). Run from this dir.
set -e
cd "$(dirname "$0")"
VER=$(grep -E '^version' manifest.ini | sed 's/.*=[[:space:]]*//')
OUT="eyewaz-${VER}.nvda-addon"
rm -f "$OUT"
zip -r "$OUT" manifest.ini synthDrivers eyewaz.json \
  -x '*.pyc' -x '*/__pycache__/*' >/dev/null
echo "Built $OUT"
echo "Install: double-click it on Windows, or NVDA menu > Tools > Add-on store > Install from external source."
