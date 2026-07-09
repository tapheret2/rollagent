from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class ActionStatus(str, Enum):
    PENDING = "pending"
    CHALLENGED = "challenged"
    FINAL = "final"
    REVERTED = "reverted"


class ChallengeStatus(str, Enum):
    OPEN = "open"
    ACCEPTED = "accepted"  # challenge wins → action reverted
    REJECTED = "rejected"  # challenge fails → action can finalize


class ExecMode(str, Enum):
    """How side effects are applied.

    declare: intent only until FINAL (safe default).
    eager: mark executed_at on propose (for reversible / draft side effects).
    """

    DECLARE = "declare"
    EAGER = "eager"


@dataclass
class Action:
    id: str
    type: str
    payload: dict[str, Any]
    status: ActionStatus
    mode: ExecMode
    window_seconds: int
    created_at: str  # ISO UTC
    finalizes_at: str  # ISO UTC
    actor: str = "agent"
    summary: str = ""
    executed_at: str | None = None
    finalized_at: str | None = None
    revert_reason: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_row(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        d["mode"] = self.mode.value
        d["payload_json"] = __import__("json").dumps(self.payload, ensure_ascii=False)
        d["meta_json"] = __import__("json").dumps(self.meta, ensure_ascii=False)
        del d["payload"]
        del d["meta"]
        return d

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> Action:
        import json

        return cls(
            id=row["id"],
            type=row["type"],
            payload=json.loads(row["payload_json"]),
            status=ActionStatus(row["status"]),
            mode=ExecMode(row["mode"]),
            window_seconds=int(row["window_seconds"]),
            created_at=row["created_at"],
            finalizes_at=row["finalizes_at"],
            actor=row.get("actor") or "agent",
            summary=row.get("summary") or "",
            executed_at=row.get("executed_at"),
            finalized_at=row.get("finalized_at"),
            revert_reason=row.get("revert_reason"),
            meta=json.loads(row["meta_json"] or "{}"),
        )


@dataclass
class Challenge:
    id: str
    action_id: str
    evidence: str
    challenger: str
    status: ChallengeStatus
    created_at: str
    resolved_at: str | None = None
    resolution_note: str | None = None

    def to_row(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> Challenge:
        return cls(
            id=row["id"],
            action_id=row["action_id"],
            evidence=row["evidence"],
            challenger=row.get("challenger") or "human",
            status=ChallengeStatus(row["status"]),
            created_at=row["created_at"],
            resolved_at=row.get("resolved_at"),
            resolution_note=row.get("resolution_note"),
        )
