"""Load golden tasks, score agent runs against them, and write the evaluation report."""

import csv
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from salesops_agent.agent.runner import RunResult


@dataclass(frozen=True)
class GoldenTask:
    """One evaluation task. Each entry in a tuple is a set of acceptable alternatives."""

    task_id: str
    question: str
    expected_status: str
    expected_reason: str
    expected_tools: tuple[frozenset[str], ...]
    forbidden_tools: frozenset[str]
    expected_facts: tuple[tuple[str, ...], ...]
    rationale: str
    scripted_tool: str
    scripted_args: dict[str, Any]
    scripted_answer: str
    approval: str | None


@dataclass(frozen=True)
class TaskOutcome:
    task_id: str
    passed: bool
    status: str
    guardrail_reason: str | None
    latency_seconds: float
    tools_called: list[str]
    tools_blocked: list[str]
    hitl: dict[str, Any] | None
    estimated_cost_usd: float
    failure_reason: str


def _split(value: str, separator: str) -> list[str]:
    return [part.strip() for part in value.split(separator) if part.strip()]


def load_tasks(path: Path) -> list[GoldenTask]:
    """Read the task table. `;` separates required items and `|` separates alternatives."""
    with path.open(encoding="utf-8", newline="") as file:
        return [
            GoldenTask(
                task_id=row["task_id"],
                question=row["question"],
                expected_status=row["expected_status"],
                expected_reason=row["expected_reason"],
                expected_tools=tuple(
                    frozenset(_split(item, "|")) for item in _split(row["expected_tools"], ";")
                ),
                forbidden_tools=frozenset(_split(row["forbidden_tools"], ";")),
                expected_facts=tuple(
                    tuple(_split(item, "|")) for item in _split(row["expected_facts"], ";")
                ),
                rationale=row["rationale"],
                scripted_tool=row["scripted_tool"],
                scripted_args=json.loads(row["scripted_args"] or "{}"),
                scripted_answer=row["scripted_answer"],
                approval=row["approval"] or None,
            )
            for row in csv.DictReader(file)
        ]


def _normalize(text: str) -> str:
    """Lowercase and drop `$`, commas and curly apostrophes, so $4,750,000 equals 4750000."""
    return re.sub(r"[$,]", "", text.lower().replace("’", "'"))


def _contains_fact(answer: str, fact: str) -> bool:
    """Match whole values only, so 23 does not match 230 or 23.5."""
    pattern = rf"(?<![\w.]){re.escape(_normalize(fact))}(?!\w|\.\d)"
    return re.search(pattern, _normalize(answer)) is not None


def score_run(task: GoldenTask, result: RunResult) -> TaskOutcome:
    """Compare a run with its task and describe every mismatch."""
    reasons = []
    guardrail_reason = result.guardrail["reason"] if result.guardrail else None
    if result.error:
        reasons.append(f"run failed: {result.error}")
    elif result.status not in task.expected_status.split("|"):
        reasons.append(f"expected status {task.expected_status}, got {result.status}")
    else:
        # A blocked run must be blocked for the expected reason.
        if (
            task.expected_reason
            and result.status == "blocked"
            and guardrail_reason != task.expected_reason
        ):
            reasons.append(f"expected reason {task.expected_reason}, got {guardrail_reason}")
        called = set(result.tools_called)
        for alternatives in task.expected_tools:
            if not alternatives & called:
                reasons.append(f"missing tool: {' or '.join(sorted(alternatives))}")
        for name in sorted(task.forbidden_tools & called):
            reasons.append(f"forbidden tool called: {name}")
        for alternatives in task.expected_facts:
            if not any(_contains_fact(result.answer or "", fact) for fact in alternatives):
                reasons.append(f"missing fact: {' or '.join(alternatives)}")

    return TaskOutcome(
        task_id=task.task_id,
        passed=not reasons,
        status=result.status,
        guardrail_reason=guardrail_reason,
        latency_seconds=result.latency_seconds,
        tools_called=result.tools_called,
        tools_blocked=list(result.tools_blocked),
        hitl=result.hitl,
        estimated_cost_usd=result.estimated_cost_usd,
        failure_reason="; ".join(reasons),
    )


def write_report(path: Path, outcomes: list[TaskOutcome]) -> None:
    """Write the JSON report. Agent answers are left out because this file is committed."""
    total = len(outcomes)
    passed = sum(outcome.passed for outcome in outcomes)
    latency = sum(outcome.latency_seconds for outcome in outcomes)
    cost = sum(outcome.estimated_cost_usd for outcome in outcomes)
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": {
            "total_tasks": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": round(passed / total, 3) if total else 0,
            "average_latency_seconds": round(latency / total, 3) if total else 0,
            "total_estimated_cost_usd": round(cost, 6),
            "average_estimated_cost_usd": round(cost / total, 6) if total else 0,
        },
        "tasks": [asdict(outcome) for outcome in outcomes],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
