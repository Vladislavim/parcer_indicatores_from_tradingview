from __future__ import annotations

import os
import shutil
from pathlib import Path


APP_DIR_NAME = "LocalSignalsPro"


def get_app_home_dir() -> Path:
    override = os.environ.get("LOCAL_SIGNALS_HOME", "").strip()
    if override:
        base = Path(override)
    elif os.name == "nt":
        drive = os.environ.get("SystemDrive", "C:").rstrip("\\/")
        base = Path(f"{drive}\\{APP_DIR_NAME}")
    else:
        base = Path.home() / f".{APP_DIR_NAME.lower()}"
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_data_dir() -> Path:
    data = get_app_home_dir() / "data"
    data.mkdir(parents=True, exist_ok=True)
    return data


def get_journal_file() -> Path:
    return get_app_home_dir() / "trade_journal.json"


def get_runtime_events_file() -> Path:
    return get_data_dir() / "runtime_events.jsonl"


def get_equity_file() -> Path:
    return get_data_dir() / "equity_snapshots.csv"


def migrate_if_missing(new_path: Path, legacy_path: Path) -> None:
    """
    One-time non-destructive migration from old project-local paths.
    """
    try:
        if new_path.exists():
            return
        if legacy_path.exists() and legacy_path.is_file():
            new_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(legacy_path, new_path)
    except Exception:
        # Never break app start because of migration.
        pass

