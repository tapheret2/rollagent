# Changelog

All notable changes to this project are documented in this file.

## [0.1.0] - 2026-07-10

### Added

- Core state machine: `PENDING` → `FINAL` or `CHALLENGED` → `REVERTED`
- SQLite store under `~/.rollagent` (override with `ROLLAGENT_HOME` / `--home`)
- CLI: `init`, `propose`, `list`, `show`, `challenge`, `accept`, `reject`, `finalize`, `tick`, `demo`
- Execution modes: `declare` (default) and `eager` (reversible draft effects)
- Built-in demos: `publish_tip`, `write_file`
- Python API via `Engine` + `Store`
- Tests for engine transitions and terminal states
- GitHub Actions CI (pytest + CLI smoke on Python 3.10/3.12)

### Notes

Alpha protocol library — not an agent framework and not on-chain.
