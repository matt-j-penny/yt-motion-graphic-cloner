#!/bin/bash
set -euo pipefail

LABEL="com.ytmotioncapture.helper"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"

launchctl bootout "gui/$(id -u)/${LABEL}" >/dev/null 2>&1 || true
rm -f "$PLIST"
osascript -e 'display notification "The capture helper will no longer start with your Mac." with title "YT Motion Capture"'
