#!/bin/bash
# Serves the Everything Library browser locally (the 3D viewer can't load models from file://) and opens it.
cd "$(dirname "$0")"
PORT=8765
while lsof -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; do PORT=$((PORT + 1)); done
echo "Everything Library running at http://localhost:$PORT  (close this window to stop)"
(sleep 1 && open "http://localhost:$PORT/") &
exec python3 -m http.server $PORT --bind 127.0.0.1
