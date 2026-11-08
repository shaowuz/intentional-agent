#!/usr/bin/env python3
"""Convenience wrapper for the ranked tournament CLI.

Usage:
  python3 scripts/run_ranked_tournament.py --config config/ranked_tournament.yaml
  python3 scripts/run_ranked_tournament.py --config config/ranked_tournament_mock.yaml
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ranked_tournament.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(["run"] + sys.argv[1:]))
