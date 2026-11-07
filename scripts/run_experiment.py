#!/usr/bin/env python3
"""Convenience wrapper: ``python scripts/run_experiment.py --config ...``.

Equivalent to ``python -m ipd.cli run ...`` from the repository root.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ipd.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(["run"] + sys.argv[1:]))
