"""Persist the two-stop contract unlock in the user's local data folder."""
import os
from pathlib import Path


def _unlock_path():
    local_data = os.environ.get("LOCALAPPDATA")
    directory = Path(local_data) if local_data else Path.home() / ".local" / "share"
    return directory / "DeadRoute" / "two-stop.unlocked"


def load_two_stop_unlock():
    try:
        return _unlock_path().is_file()
    except OSError:
        return False


def save_two_stop_unlock():
    try:
        path = _unlock_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    except OSError:
        # The current session can still use the unlocked contract.
        return
