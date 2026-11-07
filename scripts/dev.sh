#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo "Node.js 22 or later and npm are required." >&2
  exit 1
fi
if ! node -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 22 ? 0 : 1)'; then
  echo "Please use Node.js 22 or later." >&2
  exit 1
fi

echo "Preparing the Python environment..."
if command -v uv >/dev/null 2>&1; then
  uv sync --extra dev --frozen
else
  if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3.11 or later is required. Install Python or uv first." >&2
    exit 1
  fi
  python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else "Python 3.11 or later is required.")'
  if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv
  fi
  .venv/bin/python -m pip install -e '.[dev]'
fi

echo "Preparing the dashboard..."
npm --prefix frontend ci
npm --prefix frontend run build

echo "Opening a local server at http://127.0.0.1:8000"
echo "Press Ctrl+C to stop. API keys must be re-entered after a server restart."
exec .venv/bin/python -m uvicorn intentional_agent.main:app --host 127.0.0.1 --port 8000
