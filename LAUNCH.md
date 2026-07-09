# Launch notes (Tap — push lúc 0h)

## Local (đã xong)

```bash
cd C:\Users\ADMIN\projects\rollagent
pip install -e ".[dev]"
pytest
rollagent demo
```

## Lúc 0h — GitHub

```bash
cd C:\Users\ADMIN\projects\rollagent
# nếu chưa có remote:
gh repo create tapheret2/rollagent --public --source=. --remote=origin --push
# hoặc:
git remote add origin https://github.com/tapheret2/rollagent.git
git push -u origin main
```

Topics gợi ý trên GitHub: `ai-agents`, `optimistic-rollup`, `human-in-the-loop`, `agent-safety`, `python`

## X / Twitter (copy khi sẵn sàng)

**Tweet 1 (main):**
```
built rollagent — optimistic rollups for AI agent actions

propose → PENDING (challenge window) → FINAL
or challenge → REVERTED

confirm-every-step doesn't scale. blind autonomy is unsafe.
this is the middle path.

pip install + rollagent demo
github.com/tapheret2/rollagent
```

**Tweet 2 (thread — why):**
```
agents will publish tips, push code, move money.

every side-effect should be a receipt with a challenge window — not a chat message that disappears.

declare mode (safe) or eager mode (reversible drafts).
local SQLite. MIT. alpha.
```

## Show HN title (sau khi có demo GIF / stars seed)

```
Show HN: Optimistic rollups for AI agent actions
```

## Chưa làm (cố ý)

- Không push giúp — Tap tự push 0h
- Chưa HN/X — báo Tap khi muốn
- Chưa HTTP API / on-chain (roadmap README)
