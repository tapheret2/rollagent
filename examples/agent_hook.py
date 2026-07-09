"""Minimal example: wrap a dangerous agent intent in rollagent.

Run from repo (after pip install -e .):

    python examples/agent_hook.py
"""

from __future__ import annotations

from pathlib import Path

from rollagent.engine import Engine
from rollagent.models import ExecMode
from rollagent.store import Store


def main() -> None:
    root = Path(__file__).resolve().parent / "_demo_data"
    root.mkdir(exist_ok=True)
    eng = Engine(Store(root / "hook.db"), effects_dir=root / "effects")

    # Agent "wants" to publish — we only open a receipt
    action = eng.propose(
        "publish_tip",
        {
            "match": "Bayern vs Dortmund",
            "pick": "Bayern ML",
            "stake": "1u",
            "source": "agent-v0",
        },
        window_seconds=300,
        mode=ExecMode.DECLARE,
        actor="example-agent",
    )
    print("proposed:", action.id, action.status.value)
    print("finalizes_at:", action.finalizes_at)
    print("→ human/bot can challenge; else finalize when window ends")


if __name__ == "__main__":
    main()
