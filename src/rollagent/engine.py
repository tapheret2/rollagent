from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from rollagent.models import (
    Action,
    ActionStatus,
    Challenge,
    ChallengeStatus,
    ExecMode,
)
from rollagent.store import Store


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(s: str) -> datetime:
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"



def seconds_until_finalize(finalizes_at: str, now: datetime | None = None) -> float:
    """Seconds remaining until finalize (negative if past)."""
    now = now or utcnow()
    return (parse_iso(finalizes_at) - now).total_seconds()


def is_past_finalize(finalizes_at: str, now: datetime | None = None) -> bool:
    return seconds_until_finalize(finalizes_at, now=now) <= 0


class EngineError(Exception):
    """Domain error with a short message for the CLI."""


class Engine:
    """Optimistic rollup state machine for agent actions."""

    def __init__(self, store: Store, effects_dir: Path | None = None) -> None:
        self.store = store
        self.effects_dir = Path(effects_dir) if effects_dir else store.db_path.parent / "effects"
        self.effects_dir.mkdir(parents=True, exist_ok=True)

    # --- propose ---------------------------------------------------------

    def propose(
        self,
        action_type: str,
        payload: dict[str, Any] | None = None,
        *,
        window_seconds: int = 900,
        mode: ExecMode | str = ExecMode.DECLARE,
        actor: str = "agent",
        summary: str = "",
        meta: dict[str, Any] | None = None,
    ) -> Action:
        if window_seconds < 1:
            raise EngineError("window_seconds must be >= 1")

        mode = ExecMode(mode) if not isinstance(mode, ExecMode) else mode
        payload = payload or {}
        now = utcnow()
        action = Action(
            id=new_id("act"),
            type=action_type,
            payload=payload,
            status=ActionStatus.PENDING,
            mode=mode,
            window_seconds=window_seconds,
            created_at=iso(now),
            finalizes_at=iso(now + timedelta(seconds=window_seconds)),
            actor=actor,
            summary=summary or self._default_summary(action_type, payload),
            meta=meta or {},
        )

        if mode == ExecMode.EAGER:
            self._apply_effect(action, phase="eager")
            action.executed_at = iso(now)

        self.store.insert_action(action)
        return action

    # --- challenge -------------------------------------------------------

    def challenge(
        self,
        action_id: str,
        evidence: str,
        *,
        challenger: str = "human",
    ) -> tuple[Action, Challenge]:
        if not evidence.strip():
            raise EngineError("evidence is required")

        action = self._require_action(action_id)
        if action.status not in (ActionStatus.PENDING, ActionStatus.CHALLENGED):
            raise EngineError(f"action {action_id} is {action.status.value}, cannot challenge")

        ch = Challenge(
            id=new_id("chg"),
            action_id=action_id,
            evidence=evidence.strip(),
            challenger=challenger,
            status=ChallengeStatus.OPEN,
            created_at=iso(utcnow()),
        )
        self.store.insert_challenge(ch)

        action.status = ActionStatus.CHALLENGED
        self.store.update_action(action)
        return action, ch

    # --- resolve challenge -----------------------------------------------

    def accept_challenge(
        self,
        challenge_id: str,
        *,
        note: str = "challenge accepted",
    ) -> Action:
        """Challenge wins → action REVERTED."""
        ch, action = self._require_open_challenge(challenge_id)
        now = iso(utcnow())

        ch.status = ChallengeStatus.ACCEPTED
        ch.resolved_at = now
        ch.resolution_note = note
        self.store.update_challenge(ch)

        # Reject other open challenges on same action
        for other in self.store.open_challenges(action.id):
            if other.id == ch.id:
                continue
            other.status = ChallengeStatus.REJECTED
            other.resolved_at = now
            other.resolution_note = "superseded by accepted challenge"
            self.store.update_challenge(other)

        if action.mode == ExecMode.EAGER and action.executed_at:
            self._revert_effect(action)

        action.status = ActionStatus.REVERTED
        action.finalized_at = now
        action.revert_reason = ch.evidence
        self.store.update_action(action)
        return action

    def reject_challenge(
        self,
        challenge_id: str,
        *,
        note: str = "challenge rejected",
        finalize_if_window_elapsed: bool = True,
    ) -> Action:
        """Challenge fails → action returns to pending or finalizes if window elapsed."""
        ch, action = self._require_open_challenge(challenge_id)
        now_dt = utcnow()
        now = iso(now_dt)

        ch.status = ChallengeStatus.REJECTED
        ch.resolved_at = now
        ch.resolution_note = note
        self.store.update_challenge(ch)

        still_open = self.store.open_challenges(action.id)
        if still_open:
            action.status = ActionStatus.CHALLENGED
            self.store.update_action(action)
            return action

        # No open challenges left
        if finalize_if_window_elapsed and parse_iso(action.finalizes_at) <= now_dt:
            return self._finalize(action, now=now_dt)

        action.status = ActionStatus.PENDING
        self.store.update_action(action)
        return action

    # --- finalize / tick -------------------------------------------------

    def finalize(self, action_id: str, *, force: bool = False) -> Action:
        action = self._require_action(action_id)
        if action.status == ActionStatus.FINAL:
            return action
        if action.status == ActionStatus.REVERTED:
            raise EngineError(f"action {action_id} already reverted")
        if action.status == ActionStatus.CHALLENGED:
            open_ch = self.store.open_challenges(action_id)
            if open_ch:
                raise EngineError(
                    f"action {action_id} has {len(open_ch)} open challenge(s); resolve first"
                )

        now = utcnow()
        if not force and parse_iso(action.finalizes_at) > now:
            raise EngineError(
                f"window still open until {action.finalizes_at} (use --force to skip wait)"
            )
        return self._finalize(action, now=now)

    def tick(self) -> list[Action]:
        """Auto-finalize pending actions whose window elapsed (no open challenges)."""
        finalized: list[Action] = []
        now = utcnow()
        for action in self.store.list_actions(status=ActionStatus.PENDING.value, limit=500):
            if parse_iso(action.finalizes_at) <= now:
                if self.store.open_challenges(action.id):
                    continue
                finalized.append(self._finalize(action, now=now))
        return finalized

    # --- internals -------------------------------------------------------

    def _finalize(self, action: Action, *, now: datetime) -> Action:
        if action.mode == ExecMode.DECLARE and not action.executed_at:
            self._apply_effect(action, phase="final")
            action.executed_at = iso(now)

        action.status = ActionStatus.FINAL
        action.finalized_at = iso(now)
        self.store.update_action(action)

        # Close any leftover open challenges as rejected (window ended without accept)
        for ch in self.store.open_challenges(action.id):
            ch.status = ChallengeStatus.REJECTED
            ch.resolved_at = action.finalized_at
            ch.resolution_note = "window closed; action finalized"
            self.store.update_challenge(ch)

        return action

    def _require_action(self, action_id: str) -> Action:
        action = self.store.get_action(action_id)
        if not action:
            raise EngineError(f"unknown action: {action_id}")
        return action

    def _require_open_challenge(self, challenge_id: str) -> tuple[Challenge, Action]:
        ch = self.store.get_challenge(challenge_id)
        if not ch:
            raise EngineError(f"unknown challenge: {challenge_id}")
        if ch.status != ChallengeStatus.OPEN:
            raise EngineError(f"challenge {challenge_id} is {ch.status.value}")
        action = self._require_action(ch.action_id)
        return ch, action

    def _default_summary(self, action_type: str, payload: dict[str, Any]) -> str:
        if action_type == "publish_tip":
            match = payload.get("match") or payload.get("fixture") or "?"
            pick = payload.get("pick") or payload.get("selection") or "?"
            stake = payload.get("stake", "?")
            return f"publish tip: {match} → {pick} (stake {stake})"
        if action_type == "shell":
            return f"shell: {payload.get('command', '?')}"
        if action_type == "write_file":
            return f"write_file: {payload.get('path', '?')}"
        if action_type == "git_commit":
            return f"git_commit: {payload.get('message', '?')}"
        return f"{action_type}: {json.dumps(payload, ensure_ascii=False)[:80]}"

    def _effect_path(self, action: Action) -> Path:
        return self.effects_dir / f"{action.id}.json"

    def _apply_effect(self, action: Action, *, phase: str) -> None:
        """Record side-effect artifacts. Real world hooks can plug in later."""
        record = {
            "action_id": action.id,
            "type": action.type,
            "payload": action.payload,
            "phase": phase,
            "mode": action.mode.value,
            "applied_at": iso(utcnow()),
            "summary": action.summary,
        }

        # Built-in reversible effects for demo types
        if action.type == "write_file":
            path = Path(action.payload.get("path", self.effects_dir / f"{action.id}.txt"))
            if not path.is_absolute():
                path = self.effects_dir / path
            path.parent.mkdir(parents=True, exist_ok=True)
            content = action.payload.get("content", "")
            if phase == "eager":
                draft = path.with_suffix(path.suffix + ".pending")
                draft.write_text(content, encoding="utf-8")
                record["draft_path"] = str(draft)
            else:
                path.write_text(content, encoding="utf-8")
                draft = path.with_suffix(path.suffix + ".pending")
                if draft.exists():
                    draft.unlink()
                record["path"] = str(path)
        elif action.type == "publish_tip":
            tips_log = self.effects_dir / "tips.jsonl"
            line = json.dumps(
                {
                    "action_id": action.id,
                    "phase": phase,
                    "tip": action.payload,
                    "at": iso(utcnow()),
                },
                ensure_ascii=False,
            )
            with tips_log.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
            record["tips_log"] = str(tips_log)
        else:
            # Generic receipt — safe no-op beyond audit trail
            pass

        self._effect_path(action).write_text(
            json.dumps(record, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _revert_effect(self, action: Action) -> None:
        if action.type == "write_file":
            path = Path(action.payload.get("path", self.effects_dir / f"{action.id}.txt"))
            if not path.is_absolute():
                path = self.effects_dir / path
            draft = path.with_suffix(path.suffix + ".pending")
            for p in (path, draft):
                if p.exists():
                    p.unlink()
        # publish_tip: append revert marker
        if action.type == "publish_tip":
            tips_log = self.effects_dir / "tips.jsonl"
            with tips_log.open("a", encoding="utf-8") as f:
                f.write(
                    json.dumps(
                        {
                            "action_id": action.id,
                            "phase": "reverted",
                            "at": iso(utcnow()),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )

        receipt = self._effect_path(action)
        if receipt.exists():
            data = json.loads(receipt.read_text(encoding="utf-8"))
            data["reverted_at"] = iso(utcnow())
            receipt.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def age_seconds(created_iso: str, now: datetime | None = None) -> float:
    """Seconds since an ISO timestamp (non-negative)."""
    now = now or utcnow()
    created = parse_iso(created_iso)
    return max(0.0, (now - created).total_seconds())
