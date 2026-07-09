from __future__ import annotations

import os
from pathlib import Path


def default_home() -> Path:
    env = os.environ.get("ROLLAGENT_HOME")
    if env:
        return Path(env)
    return Path.home() / ".rollagent"


def db_path(home: Path | None = None) -> Path:
    return (home or default_home()) / "rollagent.db"


def effects_dir(home: Path | None = None) -> Path:
    return (home or default_home()) / "effects"
