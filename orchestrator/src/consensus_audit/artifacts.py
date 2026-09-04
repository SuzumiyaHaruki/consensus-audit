from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_run_directory(run_root: Path, property_id: str) -> Path:
    run_root.mkdir(parents=True, exist_ok=True)
    safe_property = "".join(
        character if character.isalnum() or character in "-_" else "_"
        for character in property_id
    )
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    candidate = run_root / f"{timestamp}-{safe_property}"
    suffix = 2
    while candidate.exists():
        candidate = run_root / f"{timestamp}-{safe_property}-{suffix}"
        suffix += 1
    candidate.mkdir()
    return candidate


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


class EventLog:
    def __init__(self, path: Path):
        self.path = path

    def append(self, event_type: str, **fields: Any) -> None:
        event = {"timestamp": utc_now(), "event_type": event_type, **fields}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            handle.flush()

