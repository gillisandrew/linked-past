#!/usr/bin/env bash
# Runs once after the container is created (postCreateCommand).
# Installs dependencies and pulls datasets so the server is ready on first start.
set -euo pipefail

echo "==> Installing uv..."
pip install --quiet uv

echo "==> Installing workspace packages..."
uv sync

echo "==> Pulling datasets (this may take a minute on first run)..."
uv run linked-past-server init --all || {
  echo "    Dataset pull failed (network issue?). You can retry later with:"
  echo "    uv run linked-past-server init --all"
}

echo "==> Installing Claude Code..."
if ! command -v claude &>/dev/null; then
  curl -fsSL https://claude.ai/install.sh | bash
  echo "    Run 'claude login' to authenticate."
else
  echo "    Claude Code already installed."
fi

echo "==> Setup complete."
