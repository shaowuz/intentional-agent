"""Small, durable, owner-scoped storage for a single-server pilot."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connection() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );
                CREATE TABLE IF NOT EXISTS experiments (
                    id TEXT PRIMARY KEY, owner_id TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    state TEXT NOT NULL,
                    FOREIGN KEY(owner_id) REFERENCES users(id)
                );
                CREATE INDEX IF NOT EXISTS experiments_owner ON experiments(owner_id);
            """)
        self.path.chmod(0o600)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        finally:
            db.close()

    def create_user(self, user_id: str, username: str, password_hash: str) -> None:
        with self.connection() as db:
            db.execute("INSERT INTO users VALUES (?,?,?,?)", (user_id, username, password_hash, timestamp()))

    def find_user(self, username: str) -> dict | None:
        with self.connection() as db:
            row = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        return dict(row) if row else None

    def add_session(self, token_hash: str, user_id: str, expires_at: float) -> None:
        with self.connection() as db:
            db.execute("INSERT INTO sessions VALUES (?,?,?)", (token_hash, user_id, expires_at))

    def session_user(self, token_hash: str, now: float) -> dict | None:
        with self.connection() as db:
            row = db.execute(
                "SELECT users.id, users.username FROM sessions JOIN users ON users.id=sessions.user_id "
                "WHERE sessions.token_hash=? AND sessions.expires_at>?", (token_hash, now),
            ).fetchone()
        return dict(row) if row else None

    def delete_session(self, token_hash: str) -> None:
        with self.connection() as db:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))

    def create_experiment(self, owner_id: str, state: dict) -> dict:
        now = timestamp()
        state.update(created_at=now, updated_at=now)
        with self.connection() as db:
            db.execute("INSERT INTO experiments VALUES (?,?,?,?,?)", (
                state["id"], owner_id, now, now, json.dumps(state, allow_nan=False),
            ))
        return state

    def save_experiment(self, owner_id: str, state: dict) -> None:
        state["updated_at"] = timestamp()
        with self.connection() as db:
            cursor = db.execute(
                "UPDATE experiments SET updated_at=?,state=? WHERE id=? AND owner_id=?",
                (state["updated_at"], json.dumps(state, allow_nan=False), state["id"], owner_id),
            )
            if cursor.rowcount != 1:
                raise KeyError("Experiment not found")

    def get_experiment(self, owner_id: str, experiment_id: str) -> dict | None:
        with self.connection() as db:
            row = db.execute("SELECT state FROM experiments WHERE id=? AND owner_id=?", (experiment_id, owner_id)).fetchone()
        return json.loads(row["state"]) if row else None

    def list_experiments(self, owner_id: str) -> list[dict]:
        with self.connection() as db:
            rows = db.execute("SELECT state FROM experiments WHERE owner_id=? ORDER BY created_at DESC", (owner_id,)).fetchall()
        summaries = []
        for row in rows:
            state = json.loads(row["state"])
            summaries.append({
                "id": state["id"], "name": state["config"]["name"], "status": state["status"],
                "round": state["round"], "rounds": state["config"]["rounds"], "mode": state["config"]["mode"],
                "created_at": state["created_at"], "updated_at": state["updated_at"],
                "cost_usd": state["usage"].get("cost_usd", 0), "error": state.get("error"),
            })
        return summaries

    def recover_interrupted(self) -> None:
        """A process restart pauses runs; it must never silently replay paid requests."""
        with self.connection() as db:
            rows = db.execute("SELECT id,state FROM experiments").fetchall()
            for row in rows:
                state = json.loads(row["state"])
                if state["status"] == "running":
                    state["status"] = "paused"
                    state["error"] = "Server restarted. Review the checkpoint and API usage before resuming."
                    usage = state.get("usage", {})
                    if usage.get("reserved_usd", 0) > 0:
                        usage["unknown_cost_requests"] = max(1, usage.get("unknown_cost_requests", 0))
                        usage["reserved_usd"] = 0
                        state["error"] += " An in-flight API charge needs reconciliation."
                    state["updated_at"] = timestamp()
                    db.execute("UPDATE experiments SET state=?,updated_at=? WHERE id=?", (
                        json.dumps(state), state["updated_at"], row["id"],
                    ))
