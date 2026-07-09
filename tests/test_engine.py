from __future__ import annotations

from pathlib import Path

import pytest

from rollagent.engine import Engine, EngineError
from rollagent.models import ActionStatus, ChallengeStatus, ExecMode
from rollagent.store import Store


@pytest.fixture
def eng(tmp_path: Path) -> Engine:
    store = Store(tmp_path / "t.db")
    return Engine(store, effects_dir=tmp_path / "effects")


def test_propose_pending(eng: Engine) -> None:
    a = eng.propose("publish_tip", {"match": "A vs B", "pick": "A", "stake": "1u"}, window_seconds=60)
    assert a.status == ActionStatus.PENDING
    assert a.id.startswith("act_")
    assert eng.store.get_action(a.id) is not None


def test_challenge_and_accept_reverts(eng: Engine) -> None:
    a = eng.propose("publish_tip", {"match": "X", "pick": "Y", "stake": "1"}, window_seconds=120)
    a, ch = eng.challenge(a.id, "bad edge", challenger="bot")
    assert a.status == ActionStatus.CHALLENGED
    assert ch.status == ChallengeStatus.OPEN

    a = eng.accept_challenge(ch.id)
    assert a.status == ActionStatus.REVERTED
    assert a.revert_reason == "bad edge"


def test_reject_challenge_returns_pending(eng: Engine) -> None:
    a = eng.propose("shell", {"command": "echo hi"}, window_seconds=9999)
    _, ch = eng.challenge(a.id, "nope")
    a = eng.reject_challenge(ch.id)
    assert a.status == ActionStatus.PENDING


def test_finalize_force_declare_writes_tip(eng: Engine, tmp_path: Path) -> None:
    a = eng.propose(
        "publish_tip",
        {"match": "LFC vs CFC", "pick": "Over 2.5", "stake": "1u"},
        window_seconds=9999,
        mode=ExecMode.DECLARE,
    )
    a = eng.finalize(a.id, force=True)
    assert a.status == ActionStatus.FINAL
    assert a.executed_at is not None
    tips = tmp_path / "effects" / "tips.jsonl"
    assert tips.exists()
    assert a.id in tips.read_text(encoding="utf-8")


def test_cannot_finalize_with_open_challenge(eng: Engine) -> None:
    a = eng.propose("shell", {"command": "rm"}, window_seconds=1)
    eng.challenge(a.id, "dangerous")
    with pytest.raises(EngineError, match="open challenge"):
        eng.finalize(a.id, force=True)


def test_eager_write_file_revert(eng: Engine, tmp_path: Path) -> None:
    rel = "note.txt"
    a = eng.propose(
        "write_file",
        {"path": rel, "content": "hello"},
        window_seconds=60,
        mode=ExecMode.EAGER,
    )
    assert a.executed_at is not None
    draft = tmp_path / "effects" / "note.txt.pending"
    assert draft.exists()

    _, ch = eng.challenge(a.id, "wrong content")
    a = eng.accept_challenge(ch.id)
    assert a.status == ActionStatus.REVERTED
    assert not draft.exists()


def test_tick_finalizes_expired(eng: Engine) -> None:
    a = eng.propose("publish_tip", {"match": "A", "pick": "B", "stake": "1"}, window_seconds=1)
    # Force window into the past
    from rollagent.engine import iso, utcnow
    from datetime import timedelta

    a.finalizes_at = iso(utcnow() - timedelta(seconds=5))
    eng.store.update_action(a)

    done = eng.tick()
    assert len(done) == 1
    assert done[0].status == ActionStatus.FINAL
