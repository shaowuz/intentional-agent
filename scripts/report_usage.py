#!/usr/bin/env python3
"""Report token usage and estimated cost for a results directory.

Reads every ``<condition>/usage.jsonl`` and sums tokens.  Cost is computed from
per-1k-token prices supplied on the command line (or 0 if omitted).

Usage:
  python scripts/report_usage.py --results results/pilot_openrouter \
      --price-in 0.00015 --price-out 0.0006
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ipd.recorder import read_jsonl  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True)
    parser.add_argument("--price-in", type=float, default=0.0, help="USD per 1k input tokens")
    parser.add_argument("--price-out", type=float, default=0.0, help="USD per 1k output tokens")
    args = parser.parse_args()

    total_in = total_out = total_calls = 0
    per_cond = {}
    for cond in sorted(os.listdir(args.results)):
        path = os.path.join(args.results, cond, "usage.jsonl")
        if not os.path.exists(path):
            continue
        recs = read_jsonl(path)
        cin = sum(int(r.get("input_tokens", 0)) for r in recs)
        cout = sum(int(r.get("output_tokens", 0)) for r in recs)
        per_cond[cond] = (cin, cout, len(recs))
        total_in += cin
        total_out += cout
        total_calls += len(recs)

    cost = total_in / 1000.0 * args.price_in + total_out / 1000.0 * args.price_out
    for cond, (cin, cout, n) in per_cond.items():
        print(
            f"{cond:8s} calls={n:6d} input_tokens={cin:9d} output_tokens={cout:8d}"
        )
    print(
        f"{'TOTAL':8s} calls={total_calls:6d} input_tokens={total_in:9d} "
        f"output_tokens={total_out:8d}"
    )
    print(f"total_tokens={total_in + total_out}")
    print(
        f"estimated_cost_usd={cost:.6f} "
        f"(prices per 1k: input={args.price_in}, output={args.price_out})"
    )


if __name__ == "__main__":
    main()
