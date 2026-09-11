#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-.venv/bin/python}"
"$PYTHON" -m pip install -r requirements.txt pyinstaller
"$PYTHON" -m playwright install chromium
"$PYTHON" -m PyInstaller build/linkpilot.spec --noconfirm
./build/create_dmg.sh
echo "Built dist/LinkPilot.app and dist/LinkPilot.dmg"
