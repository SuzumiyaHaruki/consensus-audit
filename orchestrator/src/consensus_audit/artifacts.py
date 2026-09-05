from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_run_directory(run_root: Path, label: str) -> Path:
    run_root.mkdir(parents=True, exist_ok=True)
    safe_label = "".join(
        character if character.isalnum() or character in "-_" else "_"
        for character in label
    )
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    candidate = run_root / f"{timestamp}-{safe_label}"
    suffix = 2
    while candidate.exists():
        candidate = run_root / f"{timestamp}-{safe_label}-{suffix}"
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



def add_usage(total: dict[str, int], current: dict[str, int]) -> None:
    for key, value in current.items():
        total[key] = total.get(key, 0) + value


def cost_summary(usage: dict[str, int], model: dict[str, Any]) -> dict[str, Any]:
    prices = model.get("prices_per_million") or {}
    required = ("input", "output")
    if not all(isinstance(prices.get(k), (int, float)) for k in required):
        return {"usage": usage, "estimated_cost": None, "reason": "No explicit pricing supplied."}
    if not all(k in usage for k in ("prompt_tokens", "completion_tokens")):
        return {"usage": usage, "estimated_cost": None, "reason": "Provider token breakdown unavailable."}
    cached = usage.get("prompt_cache_hit_tokens", 0)
    if cached and prices.get("cached_input") is None:
        return {"usage": usage, "estimated_cost": None, "reason": "Cached input price unavailable."}
    amount = ((usage["prompt_tokens"] - cached) * prices["input"]
              + cached * (prices.get("cached_input") or 0)
              + usage["completion_tokens"] * prices["output"]) / 1_000_000
    return {"usage": usage, "estimated_cost": amount, "prices_per_million": prices}
