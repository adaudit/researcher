#!/bin/bash
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

echo "[session-start] Installing Python dependencies (editable + dev + llm)..."
pip install --no-cache-dir -e ".[dev,llm]"

if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo 'export PATH="/usr/local/bin:$PATH"' >> "$CLAUDE_ENV_FILE"
fi

if [ -d frontend ]; then
  echo "[session-start] Installing frontend npm dependencies..."
  (cd frontend && npm install --no-audit --no-fund)
fi

echo "[session-start] Setup complete."
