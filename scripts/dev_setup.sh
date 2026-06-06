#!/usr/bin/env bash
# Lokales Entwickler-Setup (ohne Docker).
# Idempotent — kann beliebig oft aufgerufen werden.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo ">>> Backend-Venv (uv)…"
cd "$ROOT/backend"
if [ ! -d .venv ]; then
  uv venv --python 3.12 .venv 2>/dev/null || uv venv --python 3.13 .venv
fi
uv pip install -e ".[dev,exports]"

echo ">>> Frontend-Deps…"
cd "$ROOT/frontend"
npm install --no-audit --no-fund

echo ">>> Pre-Commit-Hooks…"
cd "$ROOT"
if command -v pre-commit >/dev/null 2>&1; then
  pre-commit install --install-hooks
else
  echo "    pre-commit nicht installiert — überspringe (pip install pre-commit)."
fi

echo ">>> Fertig. Tests starten:"
echo "    backend:  (cd backend && .venv/bin/pytest)"
echo "    frontend: (cd frontend && npm test)"
