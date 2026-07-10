# Contributing to rollagent

Thanks for helping improve optimistic rollups for agent actions.

## Setup

```bash
git clone https://github.com/tapheret2/rollagent.git
cd rollagent
pip install -e ".[dev]"
pytest -q
```

## Guidelines

- Prefer a **small PR** with tests for behavior changes.
- Keep the core state machine (`PENDING` → `FINAL` | `CHALLENGED` → `REVERTED`) explicit.
- Do not add network side-effects without an opt-in flag.
- Educational / finance-adjacent examples: keep “not financial advice” where relevant.

## PR checklist

- [ ] `pytest -q` passes
- [ ] CLI still works (`rollagent demo`)
- [ ] Docs updated if user-facing

## Ideas (good first issues)

- More effect adapters (git commit draft, HTTP webhook declare-mode)
- Policy: who may challenge / min evidence schema
- JSON export of the ledger for audits
