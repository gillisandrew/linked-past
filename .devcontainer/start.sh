#!/usr/bin/env bash
# Runs each time the container starts (postStartCommand).
# Starts the MCP server in the background and waits for it to be ready.
set -euo pipefail

SERVER_LOG="/tmp/linked-past-server.log"

# Kill any leftover server from a previous session
if lsof -ti :8000 &>/dev/null; then
  echo "==> Stopping previous server..."
  kill $(lsof -ti :8000) 2>/dev/null || true
  sleep 1
fi

echo "==> Starting linked-past MCP server..."
nohup uv run linked-past-server --host 0.0.0.0 --port 8000 > "$SERVER_LOG" 2>&1 &
SERVER_PID=$!

# Wait for server to become ready (up to 60s)
echo -n "    Waiting for server"
for i in $(seq 1 60); do
  if curl -sf http://localhost:8000/mcp -o /dev/null 2>/dev/null; then
    echo " ready! (PID $SERVER_PID)"
    break
  fi
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo " failed!"
    echo "    Server exited. Check $SERVER_LOG for details."
    exit 1
  fi
  echo -n "."
  sleep 1
done

echo ""
echo "==> Server running at http://localhost:8000/mcp"
echo "    Logs: tail -f $SERVER_LOG"
echo ""

cat .devcontainer/WELCOME.md
