"""Persistenz für Idempotenz: welches Ausgaben-Datum je Sektion zuletzt verschickt wurde.

Format von state.json:  {"ai": "2026-08-10", "data": "2026-08-07"}
Fehlt die Datei oder eine Sektion, gilt das als "noch nie verschickt".
"""

from __future__ import annotations

import json
from pathlib import Path

# state.json liegt im Repo-Root, eine Ebene über diesem Package.
_STATE_PATH = Path(__file__).resolve().parent.parent / "state.json"


def load_state() -> dict[str, str]:
    if not _STATE_PATH.exists():
        return {}
    return json.loads(_STATE_PATH.read_text(encoding="utf-8"))


def save_state(state: dict[str, str]) -> None:
    _STATE_PATH.write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
