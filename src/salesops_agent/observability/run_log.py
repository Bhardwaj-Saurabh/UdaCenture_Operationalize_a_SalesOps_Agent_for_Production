"""Append one JSON line per agent run to logs/runs.jsonl."""

import json
from pathlib import Path
from typing import Any


def write_run_log(logs_dir: Path, record: dict[str, Any]) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)
    with (logs_dir / "runs.jsonl").open("a", encoding="utf-8") as file:
        file.write(json.dumps(record) + "\n")
