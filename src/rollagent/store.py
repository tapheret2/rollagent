from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable

from rollagent.models import Action, Challenge


SCHEMA = """
CREATE TABLE IF NOT EXISTS actions (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL,
    mode TEXT NOT NULL,
    window_seconds INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    finalizes_at TEXT NOT NULL,
    actor TEXT,
    summary TEXT,
    executed_at TEXT,
    finalized_at TEXT,
    revert_reason TEXT,
    meta_json TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS challenges (
    id TEXT PRIMARY KEY,
    action_id TEXT NOT NULL,
    evidence TEXT NOT NULL,
    challenger TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    resolution_note TEXT,
    FOREIGN KEY (action_id) REFERENCES actions(id)
);

CREATE INDEX IF NOT EXISTS idx_actions_status ON actions(status);
CREATE INDEX IF NOT EXISTS idx_challenges_action ON challenges(action_id);
"""


class Store:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def insert_action(self, action: Action) -> None:
        row = action.to_row()
        cols = ", ".join(row.keys())
        placeholders = ", ".join("?" for _ in row)
        self._conn.execute(
            f"INSERT INTO actions ({cols}) VALUES ({placeholders})",
            tuple(row.values()),
        )
        self._conn.commit()

    def update_action(self, action: Action) -> None:
        row = action.to_row()
        action_id = row.pop("id")
        sets = ", ".join(f"{k}=?" for k in row)
        self._conn.execute(
            f"UPDATE actions SET {sets} WHERE id=?",
            (*row.values(), action_id),
        )
        self._conn.commit()

    def get_action(self, action_id: str) -> Action | None:
        cur = self._conn.execute("SELECT * FROM actions WHERE id=?", (action_id,))
        row = cur.fetchone()
        return Action.from_row(dict(row)) if row else None

    def list_actions(self, status: str | None = None, limit: int = 50) -> list[Action]:
        if status:
            cur = self._conn.execute(
                "SELECT * FROM actions WHERE status=? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            )
        else:
            cur = self._conn.execute(
                "SELECT * FROM actions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        return [Action.from_row(dict(r)) for r in cur.fetchall()]

    def insert_challenge(self, challenge: Challenge) -> None:
        row = challenge.to_row()
        cols = ", ".join(row.keys())
        placeholders = ", ".join("?" for _ in row)
        self._conn.execute(
            f"INSERT INTO challenges ({cols}) VALUES ({placeholders})",
            tuple(row.values()),
        )
        self._conn.commit()

    def update_challenge(self, challenge: Challenge) -> None:
        row = challenge.to_row()
        challenge_id = row.pop("id")
        sets = ", ".join(f"{k}=?" for k in row)
        self._conn.execute(
            f"UPDATE challenges SET {sets} WHERE id=?",
            (*row.values(), challenge_id),
        )
        self._conn.commit()

    def get_challenge(self, challenge_id: str) -> Challenge | None:
        cur = self._conn.execute("SELECT * FROM challenges WHERE id=?", (challenge_id,))
        row = cur.fetchone()
        return Challenge.from_row(dict(row)) if row else None

    def list_challenges(self, action_id: str) -> list[Challenge]:
        cur = self._conn.execute(
            "SELECT * FROM challenges WHERE action_id=? ORDER BY created_at ASC",
            (action_id,),
        )
        return [Challenge.from_row(dict(r)) for r in cur.fetchall()]

    def open_challenges(self, action_id: str) -> list[Challenge]:
        return [c for c in self.list_challenges(action_id) if c.status.value == "open"]
