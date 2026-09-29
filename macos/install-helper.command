#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$(command -v python3)"

if [[ -z "$PYTHON" ]]; then
  osascript -e 'display dialog "Python 3 is missing, so the capture helper can’t be installed." buttons {"OK"} default button 1 with title "YT Motion Capture"' >/dev/null
  exit 1
fi

if "$PYTHON" "$ROOT/scripts/setup.py" --helper-only >/tmp/yt-motion-capture-setup.json; then
  osascript -e 'display notification "You can capture clips from YouTube now." with title "YT Motion Capture is ready"'
  exit 0
fi

osascript -e 'display dialog "The helper was installed but didn’t start. Ask your agent to run setup, or try Install Helper again." buttons {"OK"} default button 1 with title "YT Motion Capture"' >/dev/null
exit 1
