# rollagent

**Optimistic rollups for AI agent actions** — act (or declare) first, challenge within a window, then finalize.

```text
propose → PENDING (challenge window) → FINAL
                    ↘ CHALLENGED → REVERTED  (if challenge accepted)
```

Confirm-every-step does not scale.  
Blind autonomy is unsafe.  
**rollagent** is the middle path — the same idea as optimistic rollups, applied to agent side-effects.

[![PyPI style](https://img.shields.io/badge/python-3.10%2B-blue)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-alpha-orange)](#)

---

## Why

| Model | Default | Human cost | Failure mode |
|-------|---------|------------|--------------|
| Confirm every step | Block | Exhaustion → approve-all | Still unsafe |
| Full autonomy | Trust | Zero | One bad tool call burns you |
| **Optimistic rollup** | Proceed under window | Intervene only on error | Challenge + evidence |

When agents publish tips, push code, or move money, every side-effect should be a **receipt** with a **challenge window** — not a chat message that disappears.

---

## Quickstart

```bash
pip install -e ".[dev]"   # from repo root
rollagent init
rollagent demo            # 30s walkthrough
```

### Manual happy path

```bash
rollagent propose publish_tip \
  --match "Man City vs Arsenal" \
  --pick "City -0.5" \
  --stake 2u \
  --window 120

rollagent list
rollagent finalize act_XXXXXXXXXX --force   # skip wait (demo)
```

### Challenge path

```bash
rollagent challenge act_XXXXXXXXXX \
  -e "Lineup leak; edge negative after odds move"

rollagent accept chg_XXXXXXXXXX   # → REVERTED
# or: rollagent reject chg_XXXXXXXXXX
```

---

## How it works

```text
  [Agent]
     │  propose(type, payload, window)
     ▼
 ┌─────────┐    challenge(evidence)    ┌────────────┐
 │ PENDING │ ────────────────────────► │ CHALLENGED │
 └────┬────┘                           └──────┬─────┘
      │                                       │
      │ window elapsed / finalize             │ accept → REVERTED
      │                                       │ reject → back to PENDING
      ▼                                       ▼
  ┌───────┐                            (or FINAL if window done)
  │ FINAL │
  └───────┘
```

### Execution modes

| Mode | Behavior |
|------|----------|
| `declare` (default) | Intent only until **FINAL** — safe default |
| `eager` | Apply reversible effect immediately (e.g. `*.pending` draft file); **REVERT** undoes it |

Built-in effect types for demos: `publish_tip`, `write_file`, plus generic receipts for any custom type.

---

## CLI

| Command | Purpose |
|---------|---------|
| `rollagent init` | Create `~/.rollagent` store |
| `rollagent propose <type>` | Open a PENDING action |
| `rollagent list` | Table of actions |
| `rollagent show <id>` | Action + challenges |
| `rollagent challenge <id> -e "..."` | Open challenge |
| `rollagent accept <chg_id>` | Challenge wins → REVERTED |
| `rollagent reject <chg_id>` | Challenge fails |
| `rollagent finalize <id> [--force]` | Close window → FINAL |
| `rollagent tick` | Auto-finalize expired PENDING |
| `rollagent demo` | Full narrative demo |

Data dir: `~/.rollagent/` (override with `--home` or `ROLLAGENT_HOME`).

---

## Python API

```python
from pathlib import Path
from rollagent.engine import Engine
from rollagent.store import Store
from rollagent.models import ExecMode

store = Store(Path("rollagent.db"))
eng = Engine(store, effects_dir=Path("effects"))

action = eng.propose(
    "publish_tip",
    {"match": "A vs B", "pick": "A -0.5", "stake": "1u"},
    window_seconds=900,
    mode=ExecMode.DECLARE,
)
# eng.challenge(action.id, "evidence...")
# eng.accept_challenge(chg_id)
# eng.finalize(action.id, force=True)
```

---

## Status

**Alpha (v0.1)** — local SQLite state machine + CLI.  
Not a full agent framework. Not on-chain (yet).  
The point is a **clear protocol** others can embed: `propose → challenge → finalize|revert`.

### Roadmap (honest)

- [ ] JSON-RPC / HTTP for agent runtimes to plug in
- [ ] Policy packs (who may challenge, min evidence schema)
- [ ] Reputation for challengers (anti-spam)
- [ ] Optional content-addressed receipts / chain attest
- [ ] Integrations (skill wrappers for common agent CLIs)

---

## Show HN / X one-liner

> Optimistic rollups for AI agents: actions go pending under a challenge window — intervene only when wrong, then finalize or revert.

---

## License

MIT — see [LICENSE](LICENSE).

Built by [tapheret2](https://github.com/tapheret2).
