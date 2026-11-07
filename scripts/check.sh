#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if command -v uv >/dev/null 2>&1; then
  uv sync --extra dev --frozen
elif [ -x .venv/bin/python ]; then
  .venv/bin/python -m pip install -e '.[dev]'
else
  echo "Run ./scripts/dev.sh once, or install uv, to prepare the Python environment." >&2
  exit 1
fi

.venv/bin/python -m pytest -ra "$@"
npm --prefix frontend ci
npm --prefix frontend run build
