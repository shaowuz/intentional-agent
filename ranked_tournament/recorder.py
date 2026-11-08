"""Raw JSONL recording, per-round checkpoints and memory snapshots."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ipd.config import save_config_snapshot
from ipd.recorder import read_jsonl
from ipd.utils import atomic_write_text, ensure_dir

from .config import TournamentConfig

KINDS = (
    "pairings",
    "stages",
    "games",
    "rounds",
    "reflections",
    "strategies",
    "usage",
    "calls",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_jsonl(path: str, records: List[dict]) -> None:
    if not records:
        return
    ensure_dir(os.path.dirname(os.path.abspath(path)))
    with open(path, "a", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


class ResultsRecorder:
    """Writes all raw experiment records for one tournament run."""

    def __init__(self, base_dir: str, config: TournamentConfig):
        self.base_dir = ensure_dir(base_dir)
        self.config = config
        self.paths = {
            kind: os.path.join(self.base_dir, f"{kind}.jsonl")
            for kind in KINDS
        }
        self.memory_dir = ensure_dir(os.path.join(self.base_dir, "memory"))
        self.checkpoint_path = os.path.join(
            self.base_dir, "checkpoint.json"
        )
        self.meta_path = os.path.join(
            self.base_dir, "experiment_meta.json"
        )
        self.status_path = os.path.join(self.base_dir, "run_status.json")
        self.config_snapshot_path = os.path.join(
            self.base_dir, "config_snapshot.yaml"
        )
        self._buffers: Dict[str, List[dict]] = {
            kind: [] for kind in KINDS
        }

    # ------------------------------------------------------------------ #
    # Setup / resume
    # ------------------------------------------------------------------ #
    def initialize(self, resume: bool) -> Optional[dict]:
        if not resume:
            for path in self.paths.values():
                ensure_dir(os.path.dirname(os.path.abspath(path)))
                open(path, "w", encoding="utf-8").close()
            if os.path.exists(self.checkpoint_path):
                os.remove(self.checkpoint_path)
            return None
        checkpoint = self.read_checkpoint()
        if checkpoint:
            self._truncate_to_round(int(checkpoint["next_round"]))
        return checkpoint

    def read_checkpoint(self) -> Optional[dict]:
        if not os.path.exists(self.checkpoint_path):
            return None
        with open(self.checkpoint_path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def _truncate_to_round(self, next_round: int) -> None:
        """Drop any records at or beyond ``next_round`` (crash-window guard)."""
        for path in self.paths.values():
            records = read_jsonl(path)
            kept = [
                r
                for r in records
                if int(r.get("round", 0)) < next_round
            ]
            if len(kept) != len(records):
                text = "".join(
                    json.dumps(r, ensure_ascii=False) + "\n" for r in kept
                )
                atomic_write_text(path, text)

    # ------------------------------------------------------------------ #
    # Buffers
    # ------------------------------------------------------------------ #
    def buffer(self, kind: str, record: dict) -> None:
        if kind not in self._buffers:
            raise ValueError(f"Unknown record kind {kind!r}.")
        self._buffers[kind].append(record)

    def buffer_call(self, record: dict) -> None:
        self.buffer("calls", record)

    def flush(self) -> None:
        for kind in KINDS:
            records = self._buffers[kind]
            if records:
                _append_jsonl(self.paths[kind], records)
                self._buffers[kind] = []

    def _flush_usage(self, usage) -> None:
        records = usage.drain()
        _append_jsonl(self.paths["usage"], records)

    # ------------------------------------------------------------------ #
    # Rounds and snapshots
    # ------------------------------------------------------------------ #
    def memory_snapshot_path(self, agent_id: str, round_index: int) -> str:
        return os.path.join(
            self.memory_dir, f"agent_{agent_id}_round_{round_index}.json"
        )

    def write_memory_snapshots(self, round_index: int, agents) -> None:
        for agent_id, agent in agents.items():
            path = self.memory_snapshot_path(agent_id, round_index)
            atomic_write_text(
                path,
                json.dumps(agent.memory.to_dict(), indent=2, ensure_ascii=False),
            )

    def load_memory_snapshot(
        self, agent_id: str, round_index: int
    ) -> Optional[dict]:
        path = self.memory_snapshot_path(agent_id, round_index)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def commit_round(self, round_index: int, agents, usage) -> None:
        self.flush()
        self._flush_usage(usage)
        self.write_memory_snapshots(round_index, agents)
        checkpoint = {
            "next_round": round_index + 1,
            "completed_rounds": round_index,
            "updated_at": _now(),
        }
        atomic_write_text(
            self.checkpoint_path, json.dumps(checkpoint, indent=2)
        )

    # ------------------------------------------------------------------ #
    # Metadata and status
    # ------------------------------------------------------------------ #
    def write_meta(
        self,
        mode: str,
        status: str,
        started_at: str,
        finished_at: Optional[str] = None,
        usage_summary: Optional[dict] = None,
        extra: Optional[dict] = None,
    ) -> None:
        config = self.config
        meta = {
            "experiment": config.name,
            "seed": config.seed,
            "config_fingerprint": config.fingerprint(),
            "n_rounds": config.n_rounds,
            "agents": list(config.agents),
            "continue_prob": config.continue_prob,
            "max_stages": config.max_stages,
            "ranking_points": list(config.ranking_points),
            "max_decision_retries": config.max_decision_retries,
            "max_reflection_retries": config.max_reflection_retries,
            "llm_provider": config.llm.provider,
            "llm_model": config.llm.model,
            "llm_base_url": config.llm.base_url,
            "api_key_env": config.llm.api_key_env,
            "temperature": config.llm.temperature,
            "top_p": config.llm.top_p,
            "max_tokens": config.llm.max_tokens,
            "pricing": {
                "input_per_1k_tokens": (
                    config.llm.pricing.input_per_1k_tokens
                ),
                "output_per_1k_tokens": (
                    config.llm.pricing.output_per_1k_tokens
                ),
            },
            "mode": mode,
            "status": status,
            "started_at": started_at,
            "finished_at": finished_at,
        }
        if usage_summary is not None:
            meta["usage_summary"] = usage_summary
        if extra:
            meta.update(extra)
        atomic_write_text(
            self.meta_path, json.dumps(meta, indent=2, ensure_ascii=False)
        )
        save_config_snapshot(config, self.config_snapshot_path)

    def write_status(
        self,
        status: str,
        error: Optional[str] = None,
        usage_summary: Optional[dict] = None,
        completed_rounds: Optional[int] = None,
        extra: Optional[dict] = None,
    ) -> None:
        checkpoint = self.read_checkpoint() or {}
        payload = {
            "status": status,
            "error": error,
            "completed_rounds": (
                completed_rounds
                if completed_rounds is not None
                else checkpoint.get("completed_rounds", 0)
            ),
            "next_round": checkpoint.get("next_round"),
            "updated_at": _now(),
        }
        if usage_summary is not None:
            payload["usage_summary"] = usage_summary
        if extra:
            payload.update(extra)
        atomic_write_text(
            self.status_path,
            json.dumps(payload, indent=2, ensure_ascii=False),
        )

