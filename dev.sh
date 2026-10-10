#!/usr/bin/env sh
# Start backend (uvicorn :8000) and frontend (Vite :5173) together.
# Open http://localhost:5173/ ; Ctrl+C stops both. API_PORT overrides the backend port.
set -e
cd "$(dirname "$0")"
API_PORT="${API_PORT:-8000}"
export API_PORT

# Fail early with the owner of a busy port instead of a bare "Address already in use".
for port in "$API_PORT" 5173; do
  owner=$(lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | awk 'NR > 1 { print $2 }' | head -n 1)
  if [ -n "$owner" ]; then
    echo "Port $port is in use by PID $owner: $(ps -o command= -p "$owner")" >&2
    echo "Stop it (kill $owner) or pick another backend port: API_PORT=8011 ./dev.sh" >&2
    exit 1
  fi
done

need() {
  command -v "$1" >/dev/null || { echo "Chưa có $1. Cài: $2" >&2; exit 1; }
}
need uv "brew install uv"
need npm "brew install node"

uv sync --quiet
[ -d node_modules ] || npm install --no-fund --no-audit

# Run the binaries directly (not via uv run / npm run) so the PIDs below are the
# servers themselves and the trap stops them without leaving orphans.
.venv/bin/uvicorn exam_practice.server:app --host 127.0.0.1 --port "$API_PORT" \
  --reload --reload-dir src/exam_practice &
api=$!
node_modules/.bin/vite &
web=$!
trap 'trap - INT TERM EXIT; kill "$api" "$web" 2>/dev/null; wait' INT TERM EXIT
wait
