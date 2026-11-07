#!/usr/bin/env bash
# Run the ipd/ experiment test suite.
#
# NOTE: after merging the dashboard (backend/frontend), tests/ also contains
# pytest-based dashboard tests that require extra dependencies. To keep this
# script self-contained we list the ipd/ test modules explicitly.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m unittest \
  tests.test_game \
  tests.test_pairing \
  tests.test_memory \
  tests.test_termination \
  tests.test_simultaneous \
  tests.test_parsing \
  tests.test_config \
  tests.test_tournament_records \
  tests.test_recorder_resume \
  tests.test_analysis \
  tests.test_usage \
  -v
