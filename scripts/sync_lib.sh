#!/usr/bin/env bash
# Sync the vendored copy of rowxplorer-lib into the custom component.
#
# Usage:
#   scripts/sync_lib.sh [path-to-rowxplorer-lib]
#
# The path defaults to ../rowxplorer-lib (sibling checkout of the library).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LIB_DIR="${1:-$ROOT/../rowxplorer-lib}"
DEST="$ROOT/custom_components/rowxplorer/rowxplorer_lib"

if [[ ! -d "$LIB_DIR/src/rowxplorer_lib" ]]; then
  echo "error: $LIB_DIR/src/rowxplorer_lib not found" >&2
  exit 1
fi

rm -rf "$DEST"
mkdir -p "$DEST"
cp "$LIB_DIR"/src/rowxplorer_lib/*.py "$DEST"/
rm -f "$DEST/cli.py"
find "$DEST" -name '__pycache__' -type d -exec rm -rf {} +

LIB_VERSION="$(grep -oP '__version__ = "\K[^"]+' "$DEST/__init__.py")"
MANIFEST_VERSION="$(python3 -c "import json;print(json.load(open('$ROOT/custom_components/rowxplorer/manifest.json'))['version'])")"
if [[ "$LIB_VERSION" != "$MANIFEST_VERSION" ]]; then
  echo "warning: library $LIB_VERSION != integration manifest $MANIFEST_VERSION" >&2
fi

echo "Synced rowxplorer-lib $LIB_VERSION into $DEST"
