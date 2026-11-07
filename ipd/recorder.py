"""Recording of raw data (JSONL) with checkpointing."""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from .utils import atomic_write_text, ensure_dir


def _append_jsonl(path: str, records: List[dict]) -> None:
    if not records:
        return
    with open(path, "a", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def _write_jsonl_atomic(path: str, records: List[dict]) -> None:
    text = "".join(json.dumps(rec, ensure_ascii=False) + "\n" for rec in records)
    atomic_write_text(path, text)


def read_jsonl(path: str) -> List[dict]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


class ConditionRecorder:
    """Writes round/game/belief/usage records for one condition.

    Records are buffered per ``game_index`` batch and flushed together.  Only
    after a successful flush is the checkpoint advanced, so an interrupted batch
    is simply re-run on resume (deterministically for the mock backend).
    """

    def __init__(
        self,
        base_dir: str,
        condition: str,
        experiment_name: str,
        seed: int,
        fingerprint: str,
    ):
        self.dir = ensure_dir(os.path.join(base_dir, condition))
        self.condition = condition
        self.experiment_name = experiment_name
        self.seed = seed
        self.fingerprint = fingerprint

        self.rounds_path = os.path.join(self.dir, "rounds.jsonl")
        self.games_path = os.path.join(self.dir, "games.jsonl")
        self.beliefs_path = os.path.join(self.dir, "beliefs.jsonl")
        self.usage_path = os.path.join(self.dir, "usage.jsonl")
        self.checkpoint_path = os.path.join(self.dir, "checkpoint.json")

        self._round_buf: List[dict] = []
        self._game_buf: List[dict] = []
        self._belief_buf: List[dict] = []
        self._usage_buf: List[dict] = []

    # ------------------------------------------------------------------ #
    def initialize(self, resume: bool) -> Optional[dict]:
        """Prepare files.  Returns the existing checkpoint when resuming."""
        if not resume:
            for path in (
                self.rounds_path,
                self.games_path,
                self.beliefs_path,
                self.usage_path,
            ):
                open(path, "w", encoding="utf-8").close()
            if os.path.exists(self.checkpoint_path):
                os.remove(self.checkpoint_path)
            return None
        return self.read_checkpoint()

    def read_checkpoint(self) -> Optional[dict]:
        if not os.path.exists(self.checkpoint_path):
            return None
        with open(self.checkpoint_path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def load_games(self) -> List[dict]:
        return read_jsonl(self.games_path)

    def truncate_to_game_index(self, max_exclusive: int) -> None:
        """Drop any records at or beyond ``max_exclusive`` (crash-window guard).

        Interaction files are appended before the checkpoint is advanced; if a
        process dies in that window a batch may be partially written.  On resume
        we discard everything from ``max_exclusive`` onward and re-run it.
        """
        for path in (self.games_path, self.rounds_path, self.beliefs_path):
            records = read_jsonl(path)
            kept = [r for r in records if r.get("game_index", 0) < max_exclusive]
            if len(kept) != len(records):
                _write_jsonl_atomic(path, kept)

    # ------------------------------------------------------------------ #
    def buffer_round(self, rec: dict) -> None:
        self._round_buf.append(rec)

    def buffer_game(self, rec: dict) -> None:
        self._game_buf.append(rec)

    def buffer_belief(self, rec: dict) -> None:
        self._belief_buf.append(rec)

    def buffer_usage(self, records: List[dict]) -> None:
        self._usage_buf.extend(records)

    def commit_batch(self, next_game_index: int, extra: Optional[dict] = None) -> None:
        """Flush all buffered records and advance the checkpoint."""
        _append_jsonl(self.rounds_path, self._round_buf)
        _append_jsonl(self.games_path, self._game_buf)
        _append_jsonl(self.beliefs_path, self._belief_buf)
        _append_jsonl(self.usage_path, self._usage_buf)
        self._round_buf = []
        self._game_buf = []
        self._belief_buf = []
        self._usage_buf = []

        checkpoint = {
            "experiment": self.experiment_name,
            "condition": self.condition,
            "seed": self.seed,
            "config_fingerprint": self.fingerprint,
            "next_game_index": next_game_index,
            "games_completed": next_game_index,
        }
        if extra:
            checkpoint.update(extra)
        atomic_write_text(
            self.checkpoint_path, json.dumps(checkpoint, indent=2)
        )
