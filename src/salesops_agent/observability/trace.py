"""Write one JSON trace file per agent run."""

import json
from pathlib import Path
from typing import Any


def write_trace(traces_dir: Path, run_id: str, trace: dict[str, Any]) -> None:
    traces_dir.mkdir(parents=True, exist_ok=True)
    (traces_dir / f"{run_id}.json").write_text(json.dumps(trace, indent=2), encoding="utf-8")
