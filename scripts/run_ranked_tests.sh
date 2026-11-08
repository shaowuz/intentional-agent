#!/usr/bin/env bash
# Run the ranked-tournament test suite.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m unittest \
  tests.test_ranked_config \
  tests.test_ranked_scoring \
  tests.test_ranked_parsing \
  tests.test_ranked_engine \
  -v
