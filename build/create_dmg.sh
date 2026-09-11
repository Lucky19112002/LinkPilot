#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
rm -f dist/LinkPilot.dmg
hdiutil create -volname "LinkPilot" -srcfolder dist/LinkPilot.app -ov -format UDZO dist/LinkPilot.dmg
echo "Built dist/LinkPilot.dmg"
