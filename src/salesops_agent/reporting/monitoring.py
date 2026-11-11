"""Aggregate logs/runs.jsonl into a Markdown monitoring report.

Run with: uv run generate-monitoring-report
"""

import argparse
import json
import statistics
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from salesops_agent.config import load_config

STATUSES = ("success", "blocked", "failed", "awaiting_approval")
# Which guardrail layer a block came from, by policy name.
LAYERS = {
    "salesops_input_policy": "input",
    "salesops_data_access_policy": "tool",
    "salesops_output_policy": "output",
}
REVIEWER_REJECTION = "approval_rejected"


@dataclass(frozen=True)
class RunRecord:
    """One log line, normalized so older log formats can be read too."""

    run_id: str
    timestamp: str
    task_id: str | None
    status: str
    failure_reason: str | None
    tools_called: list[str]
    tools_blocked: list[str]
    latency_seconds: float
    interventions: list[dict[str, Any]]
    approval_requested: bool
    hitl_decision: str | None
    cost_usd: float | None
    input_tokens: int | None
    output_tokens: int | None
    legacy: bool


@dataclass
class LoadResult:
    records: list[RunRecord] = field(default_factory=list)
    skipped_lines: int = 0


def _record(raw: dict[str, Any]) -> RunRecord:
    hitl = raw.get("hitl") or {}
    return RunRecord(
        run_id=raw["run_id"],
        timestamp=raw["timestamp"],
        task_id=raw.get("task_id"),
        status=raw["status"],
        # Logs written before Step 6 used "error" and had no token counts.
        failure_reason=raw.get("failure_reason", raw.get("error")),
        tools_called=list(raw.get("tools_called", [])),
        tools_blocked=list(raw.get("tools_blocked", [])),
        latency_seconds=float(raw["latency_seconds"]),
        interventions=list(raw.get("guardrail_interventions", [])),
        approval_requested=bool(hitl.get("approval_requested")),
        hitl_decision=hitl.get("decision"),
        cost_usd=raw.get("estimated_cost_usd"),
        input_tokens=raw.get("input_tokens"),
        output_tokens=raw.get("output_tokens"),
        legacy="failure_reason" not in raw,
    )


def load_runs(log_path: Path) -> LoadResult:
    result = LoadResult()
    if not log_path.exists():
        return result
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            result.records.append(_record(json.loads(line)))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            result.skipped_lines += 1
    return result


def _pct(part: int, whole: int) -> str:
    return f"{part / whole:.1%}" if whole else "n/a"


def _runs(count: int) -> str:
    return f"{count} run" if count == 1 else f"{count} runs"


def _p95(values: list[float]) -> float:
    """95th percentile, using the largest value when there are fewer than 20 runs."""
    ordered = sorted(values)
    if len(ordered) < 20:
        return ordered[-1]
    return ordered[max(0, int(len(ordered) * 0.95) - 1)]


def _guardrail_blocks(record: RunRecord) -> list[dict[str, Any]]:
    """Blocks made by a guardrail, as opposed to a reviewer rejecting an action."""
    return [i for i in record.interventions if i.get("reason") != REVIEWER_REJECTION]


def compute_metrics(records: list[RunRecord]) -> dict[str, Any]:
    total = len(records)
    statuses = Counter(r.status for r in records)
    latencies = [r.latency_seconds for r in records]
    model_latencies = [r.latency_seconds for r in records if r.status == "success"]
    costed = [r for r in records if r.cost_usd is not None]
    total_cost = sum(r.cost_usd or 0 for r in costed)

    tools_ran = Counter(tool for r in records for tool in r.tools_called)
    tools_blocked = Counter(tool for r in records for tool in r.tools_blocked)
    blocked_runs = [r for r in records if _guardrail_blocks(r)]
    block_reasons = Counter(i["reason"] for r in records for i in _guardrail_blocks(r))
    block_layers = Counter(
        LAYERS.get(i.get("policy", "").rsplit("_v", 1)[0], "unknown")
        for r in records
        for i in _guardrail_blocks(r)
    )
    failures = Counter(r.failure_reason for r in records if r.status == "failed")

    return {
        "total": total,
        "first": min((r.timestamp for r in records), default=None),
        "last": max((r.timestamp for r in records), default=None),
        "evaluation_runs": sum(r.task_id is not None for r in records),
        "statuses": {status: statuses.get(status, 0) for status in STATUSES},
        "success_rate": _pct(statuses.get("success", 0), total),
        "failure_rate": _pct(statuses.get("failed", 0), total),
        "latency": {
            "average": statistics.fmean(latencies) if latencies else 0.0,
            "median": statistics.median(latencies) if latencies else 0.0,
            "p95": _p95(latencies) if latencies else 0.0,
            "max": max(latencies, default=0.0),
            "average_success": statistics.fmean(model_latencies) if model_latencies else 0.0,
        },
        "cost": {
            "runs_with_cost": len(costed),
            "total": total_cost,
            "average": total_cost / len(costed) if costed else 0.0,
            "average_model_run": (
                total_cost / sum(1 for r in costed if r.cost_usd) if any(r.cost_usd for r in costed) else 0.0
            ),
            "input_tokens": sum(r.input_tokens or 0 for r in costed),
            "output_tokens": sum(r.output_tokens or 0 for r in costed),
        },
        "tools_ran": tools_ran,
        "tools_blocked": tools_blocked,
        "guardrail_blocked_runs": len(blocked_runs),
        "block_reasons": block_reasons,
        "block_layers": block_layers,
        "hitl": {
            "requested": sum(r.approval_requested for r in records),
            "approved": sum(r.hitl_decision == "approve" for r in records),
            "rejected": sum(r.hitl_decision == "reject" for r in records),
            "pending": statuses.get("awaiting_approval", 0),
        },
        "failures": failures,
        "legacy_runs": sum(r.legacy for r in records),
    }


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def _highlights(m: dict[str, Any], cost_alert_usd: float) -> list[str]:
    """Plain-language observations, so the reader does not have to work them out."""
    notes = []
    total, statuses = m["total"], m["statuses"]
    if statuses["failed"]:
        reason, count = m["failures"].most_common(1)[0]
        notes.append(
            f"{_runs(statuses['failed'])} failed ({m['failure_rate']}). The most common cause "
            f"({_runs(count)}) was `{reason}`."
        )
    if m["guardrail_blocked_runs"]:
        reason, count = m["block_reasons"].most_common(1)[0]
        notes.append(
            f"Guardrails stopped {m['guardrail_blocked_runs']} runs "
            f"({_pct(m['guardrail_blocked_runs'], total)}). The most frequent reason was "
            f"`{reason}` ({count}). A high share is expected when evaluation runs include "
            "many attack scenarios."
        )
    lat = m["latency"]
    if lat["average_success"] and lat["average"] < lat["average_success"]:
        notes.append(
            f"Average latency ({lat['average']:.2f}s) is pulled down by blocked runs that "
            f"never call the model; answered runs averaged {lat['average_success']:.2f}s."
        )
    if m["hitl"]["requested"]:
        h = m["hitl"]
        notes.append(
            f"{h['requested']} runs asked for approval: {h['approved']} approved, "
            f"{h['rejected']} rejected, {h['pending']} left without a decision."
        )
    model_run_cost = m["cost"]["average_model_run"]
    if model_run_cost > cost_alert_usd:
        notes.append(
            f"Cost alert: runs that call the model average ${model_run_cost:.4f}, above the "
            f"${cost_alert_usd:.2f} threshold set in `config/agent.yaml`."
        )
    else:
        notes.append(
            f"Runs that call the model average ${model_run_cost:.6f}, within the "
            f"${cost_alert_usd:.2f} cost threshold."
        )
    if m["cost"]["runs_with_cost"] < total:
        notes.append(
            f"Cost covers {m['cost']['runs_with_cost']} of {total} runs; the rest were "
            "logged before cost tracking existed."
        )
    return notes


def render_report(
    m: dict[str, Any], log_path: Path, skipped: int, cost_alert_usd: float = 0.05
) -> str:
    total = m["total"]
    generated = datetime.now(UTC).isoformat(timespec="seconds")
    if total == 0:
        return f"# Monitoring Report\n\nGenerated {generated}. No runs found in `{log_path}`.\n"

    lat, cost, hitl = m["latency"], m["cost"], m["hitl"]
    status_labels = {
        "success": "Answered",
        "blocked": "Blocked (guardrail or rejected approval)",
        "failed": "Failed (error)",
        "awaiting_approval": "Awaiting approval",
    }
    sections = [
        "# Monitoring Report",
        f"Generated {generated} from `{log_path}`. Covers {total} runs from "
        f"{m['first'][:19]} to {m['last'][:19]} UTC. {m['evaluation_runs']} of them have a task "
        "ID (evaluation suite runs, or CLI runs with `--task-id`).",
        "## Highlights\n\n" + "\n".join(f"- {note}" for note in _highlights(m, cost_alert_usd)),
        "## Summary\n\n"
        + _table(
            ["Metric", "Value"],
            [
                ["Total runs", total],
                ["Success rate", m["success_rate"]],
                ["Failure rate", m["failure_rate"]],
                ["Average latency", f"{lat['average']:.2f}s"],
                ["Estimated total cost", f"${cost['total']:.4f}"],
                ["Estimated average cost per run", f"${cost['average']:.6f}"],
                ["Guardrail blocks", m["guardrail_blocked_runs"]],
                ["HITL approvals", hitl["approved"]],
                ["HITL rejections", hitl["rejected"]],
            ],
        ),
        "## Outcomes\n\nEvery run ends in exactly one status. A block is the system working "
        "as intended, so it is counted separately from a failure.\n\n"
        + _table(
            ["Status", "Runs", "Share"],
            [[status_labels[s], n, _pct(n, total)] for s, n in m["statuses"].items()],
        ),
        "## Latency\n\n"
        + _table(
            ["Measure", "Seconds"],
            [
                ["Average (all runs)", f"{lat['average']:.2f}"],
                ["Average (answered runs)", f"{lat['average_success']:.2f}"],
                ["Median", f"{lat['median']:.2f}"],
                ["95th percentile", f"{lat['p95']:.2f}"],
                ["Slowest", f"{lat['max']:.2f}"],
            ],
        ),
        "## Cost\n\nEstimated from token counts and the rates in `config/agent.yaml`. "
        f"Covers {cost['runs_with_cost']} of {total} runs that recorded token usage.\n\n"
        + _table(
            ["Measure", "Value"],
            [
                ["Estimated total cost", f"${cost['total']:.4f}"],
                ["Average per run", f"${cost['average']:.6f}"],
                ["Average per run that called the model", f"${cost['average_model_run']:.6f}"],
                ["Input tokens", f"{cost['input_tokens']:,}"],
                ["Output tokens", f"{cost['output_tokens']:,}"],
            ],
        ),
        "## Tool calls\n\n`Ran` counts calls that executed. `Blocked` counts calls the "
        "model proposed that a guardrail or reviewer stopped.\n\n"
        + _table(
            ["Tool", "Ran", "Blocked"],
            [
                [f"`{tool}`", m["tools_ran"].get(tool, 0), m["tools_blocked"].get(tool, 0)]
                for tool in sorted(
                    set(m["tools_ran"]) | set(m["tools_blocked"]),
                    key=lambda t: -(m["tools_ran"].get(t, 0) + m["tools_blocked"].get(t, 0)),
                )
            ],
        ),
        "## Guardrail blocks\n\n"
        f"{m['guardrail_blocked_runs']} runs were stopped by a guardrail. Reviewer "
        "rejections are counted under HITL instead.\n\n"
        + _table(
            ["Layer", "Blocks"],
            [[layer, n] for layer, n in m["block_layers"].most_common()],
        )
        + "\n\n"
        + _table(
            ["Reason", "Blocks"],
            [[f"`{reason}`", n] for reason, n in m["block_reasons"].most_common()],
        ),
        "## Human-in-the-loop\n\n"
        + _table(
            ["Measure", "Runs"],
            [
                ["Approval requested", hitl["requested"]],
                ["Approved", hitl["approved"]],
                ["Rejected", hitl["rejected"]],
                ["Pending (no decision given)", hitl["pending"]],
            ],
        ),
        "## Common failure reasons\n\n"
        + (
            _table(
                ["Reason", "Runs"],
                [[f"`{reason}`", n] for reason, n in m["failures"].most_common(5)],
            )
            if m["failures"]
            else "No failed runs."
        ),
        "## Data notes\n\n"
        f"- {m['legacy_runs']} runs were logged in an older format, before cost and "
        "redaction were added. They count toward outcomes, latency, tools, and guardrails, "
        "but not cost.\n"
        f"- {skipped} unreadable log lines were skipped.",
    ]
    return "\n\n".join(sections) + "\n"


def main() -> int:
    config = load_config()
    parser = argparse.ArgumentParser(
        prog="generate-monitoring-report", description="Aggregate the run log into a report."
    )
    parser.add_argument("--log", type=Path, default=config.paths.logs / "runs.jsonl")
    parser.add_argument(
        "--output", type=Path, default=config.paths.reports / "monitoring_report.md"
    )
    args = parser.parse_args()

    loaded = load_runs(args.log)
    metrics = compute_metrics(loaded.records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = render_report(
        metrics, args.log, loaded.skipped_lines, config.observability.cost_alert_per_run_usd
    )
    args.output.write_text(report, encoding="utf-8")
    print(f"Wrote {args.output} from {metrics['total']} runs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
