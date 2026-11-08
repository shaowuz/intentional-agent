#!/usr/bin/env python3
"""Convenience wrapper for ranked-tournament analysis.

Usage:
  python3 scripts/analyze_ranked_tournament.py --results results/ranked_tournament
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ranked_tournament.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(["analyze"] + sys.argv[1:]))
