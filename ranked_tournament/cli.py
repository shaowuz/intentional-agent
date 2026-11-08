"""Command-line interface for the ranked tournament."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional

from .config import load_config
from .tournament import TournamentRunner


def _build_overrides(args) -> dict:
    overrides: dict = {}
    if getattr(args, "mock", False):
        overrides.setdefault("llm", {}).update(
            {"provider": "mock", "model": "mock-ranked"}
        )
    if getattr(args, "output_dir", None):
        overrides["output_dir"] = args.output_dir
    if getattr(args, "name", None):
        overrides["name"] = args.name
    if getattr(args, "seed", None) is not None:
        overrides["seed"] = args.seed
    if getattr(args, "n_rounds", None) is not None:
        overrides["n_rounds"] = args.n_rounds
    if getattr(args, "continue_prob", None) is not None:
        overrides["continue_prob"] = args.continue_prob
    if getattr(args, "max_stages", None) is not None:
        overrides["max_stages"] = args.max_stages
    if getattr(args, "max_decision_retries", None) is not None:
        overrides["max_decision_retries"] = args.max_decision_retries
    if getattr(args, "max_reflection_retries", None) is not None:
        overrides["max_reflection_retries"] = args.max_reflection_retries
    if getattr(args, "provider", None):
        overrides.setdefault("llm", {})["provider"] = args.provider
    if getattr(args, "model", None):
        overrides.setdefault("llm", {})["model"] = args.model
    if getattr(args, "base_url", None):
        overrides.setdefault("llm", {})["base_url"] = args.base_url
    if getattr(args, "api_key_env", None):
        overrides.setdefault("llm", {})["api_key_env"] = args.api_key_env
    if getattr(args, "temperature", None) is not None:
        overrides.setdefault("llm", {})["temperature"] = args.temperature
    if getattr(args, "max_tokens", None) is not None:
        overrides.setdefault("llm", {})["max_tokens"] = args.max_tokens
    price_in = getattr(args, "price_in", None)
    price_out = getattr(args, "price_out", None)
    if price_in is not None or price_out is not None:
        pricing = overrides.setdefault("llm", {}).setdefault("pricing", {})
        if price_in is not None:
            pricing["input_per_1k_tokens"] = price_in
        if price_out is not None:
            pricing["output_per_1k_tokens"] = price_out
    return overrides


def cmd_run(args) -> int:
    config = load_config(args.config, _build_overrides(args))
    runner = TournamentRunner(
        config, resume=args.resume, verbose=not args.quiet
    )
    summary = runner.run()
    print(json.dumps(summary, indent=2))
    return 0


def cmd_analyze(args) -> int:
    from .analysis import analyze_all, write_report

    results_root = args.results
    figures_dir = args.figures or os.path.join(results_root, "figures")
    tables_dir = args.tables or os.path.join(results_root, "tables")
    report_path = args.report or os.path.join(results_root, "report.md")

    result = analyze_all(results_root, figures_dir, tables_dir)
    write_report(result, report_path, results_root)
    print(f"Analysis written to {tables_dir} and {figures_dir}")
    print(f"Report written to {report_path}")
    print(f"Machine-readable summary: {result['summary_path']}")
    return 0


def cmd_check(args) -> int:
    config = load_config(args.config, _build_overrides(args))
    print(json.dumps(config.to_dict(), indent=2))
    print(f"\nconfig fingerprint: {config.fingerprint()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ranked_tournament",
        description="Run a 4-agent ranked Prisoner's Dilemma tournament.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p):
        p.add_argument("--config", required=True, help="Path to YAML config.")
        p.add_argument(
            "--mock",
            action="store_true",
            help="Use the deterministic offline mock (pipeline tests only).",
        )
        p.add_argument("--output-dir", help="Override output directory.")
        p.add_argument("--name", help="Override experiment name.")
        p.add_argument("--seed", type=int, help="Override random seed.")
        p.add_argument("--n-rounds", type=int, help="Override number of rounds.")
        p.add_argument(
            "--continue-prob",
            type=float,
            help="Override continuation probability.",
        )
        p.add_argument(
            "--max-stages", type=int, help="Override the per-game stage cap."
        )
        p.add_argument(
            "--max-decision-retries",
            type=int,
            help="Override additional retries for malformed actions.",
        )
        p.add_argument(
            "--max-reflection-retries",
            type=int,
            help="Override additional retries for malformed reflections.",
        )
        p.add_argument("--provider", help="Override LLM provider.")
        p.add_argument("--model", help="Override LLM model.")
        p.add_argument(
            "--base-url",
            help="Override LLM base URL (e.g. https://openrouter.ai/api/v1).",
        )
        p.add_argument(
            "--api-key-env",
            help="Override the environment variable holding the API key.",
        )
        p.add_argument(
            "--temperature", type=float, help="Override sampling temperature."
        )
        p.add_argument(
            "--max-tokens", type=int, help="Override max output tokens."
        )
        p.add_argument(
            "--price-in",
            type=float,
            help="USD per 1k input tokens (for cost estimates).",
        )
        p.add_argument(
            "--price-out",
            type=float,
            help="USD per 1k output tokens (for cost estimates).",
        )

    p_run = sub.add_parser("run", help="Run a tournament.")
    add_common(p_run)
    p_run.add_argument(
        "--resume",
        action="store_true",
        help="Resume from the last completed round checkpoint.",
    )
    p_run.add_argument(
        "--quiet", action="store_true", help="Reduce per-round logging."
    )
    p_run.set_defaults(func=cmd_run)

    p_an = sub.add_parser("analyze", help="Analyse a recorded run.")
    p_an.add_argument("--results", required=True, help="Results directory.")
    p_an.add_argument("--figures", help="Figures output directory.")
    p_an.add_argument("--tables", help="Tables output directory.")
    p_an.add_argument("--report", help="Report output path.")
    p_an.set_defaults(func=cmd_analyze)

    p_chk = sub.add_parser("check", help="Print the resolved configuration.")
    add_common(p_chk)
    p_chk.set_defaults(func=cmd_check)

    return parser


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

