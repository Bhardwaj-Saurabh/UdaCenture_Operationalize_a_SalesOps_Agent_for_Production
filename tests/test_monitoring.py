"""Cost estimation and monitoring report checks, following the reference test_monitor.py."""

import json

import pytest

from salesops_agent.config import load_config
from salesops_agent.observability.cost import estimate_cost_usd
from salesops_agent.reporting.monitoring import compute_metrics, load_runs, render_report

RATES = load_config().observability


def run(**overrides):
    record = {
        "run_id": "r1",
        "timestamp": "2026-11-11T10:00:00+00:00",
        "task_id": None,
        "input": "q",
        "status": "success",
        "failure_reason": None,
        "tools_called": ["lookup_account"],
        "tools_blocked": [],
        "latency_seconds": 2.0,
        "input_tokens": 1000,
        "output_tokens": 100,
        "estimated_cost_usd": estimate_cost_usd(1000, 100, RATES),
        "guardrail_interventions": [],
        "hitl": {"approval_requested": False, "action": None, "decision": None},
    }
    return {**record, **overrides}


def write_log(tmp_path, records):
    path = tmp_path / "runs.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return path


def test_cost_uses_the_configured_rates():
    expected = 1000 / 1000 * RATES.cost_per_1k_input_tokens + 100 / 1000 * RATES.cost_per_1k_output_tokens
    assert estimate_cost_usd(1000, 100, RATES) == pytest.approx(expected)
    assert estimate_cost_usd(0, 0, RATES) == 0


def test_load_returns_empty_when_no_file(tmp_path):
    assert load_runs(tmp_path / "missing.jsonl").records == []


def test_load_reads_older_log_format(tmp_path):
    legacy = {
        "run_id": "old", "timestamp": "2026-11-04T10:00:00+00:00", "input": "q",
        "status": "failed", "tools_called": [], "latency_seconds": 1.0, "error": "NameError: x",
    }  # fmt: skip
    record = load_runs(write_log(tmp_path, [legacy])).records[0]
    assert record.failure_reason == "NameError: x"
    assert record.cost_usd is None
    assert record.legacy


def test_cost_totals_and_averages(tmp_path):
    blocked = run(run_id="r2", status="blocked", input_tokens=0, output_tokens=0, estimated_cost_usd=0.0)
    metrics = compute_metrics(load_runs(write_log(tmp_path, [run(), run(run_id="r3"), blocked])).records)
    one = estimate_cost_usd(1000, 100, RATES)
    assert metrics["cost"]["total"] == pytest.approx(2 * one)
    assert metrics["cost"]["average"] == pytest.approx(2 * one / 3)
    assert metrics["cost"]["average_model_run"] == pytest.approx(one)
    assert metrics["cost"]["input_tokens"] == 2000


def test_legacy_runs_are_left_out_of_cost(tmp_path):
    legacy = {k: v for k, v in run(run_id="old").items() if k not in ("input_tokens", "output_tokens", "estimated_cost_usd", "failure_reason")}  # fmt: skip
    metrics = compute_metrics(load_runs(write_log(tmp_path, [run(), legacy])).records)
    assert metrics["cost"]["runs_with_cost"] == 1
    assert metrics["total"] == 2


def test_counts_rates_latency_and_tools(tmp_path):
    records = [
        run(),
        run(run_id="r2", status="failed", failure_reason="NameError: x", latency_seconds=4.0),
        run(run_id="r3", status="blocked", tools_called=[], tools_blocked=["send_email"],
            guardrail_interventions=[{"reason": "approval_rejected", "policy": "salesops_data_access_policy_v2"}],
            hitl={"approval_requested": True, "action": "send_email", "decision": "reject"}),
    ]  # fmt: skip
    m = compute_metrics(load_runs(write_log(tmp_path, records)).records)
    assert (m["success_rate"], m["failure_rate"]) == ("33.3%", "33.3%")
    assert m["latency"]["average"] == pytest.approx(8 / 3)
    assert m["latency"]["p95"] == 4.0
    assert m["tools_ran"]["lookup_account"] == 2
    assert m["tools_blocked"]["send_email"] == 1
    assert m["hitl"]["rejected"] == 1
    assert m["guardrail_blocked_runs"] == 0  # a reviewer rejection is not a guardrail block
    assert m["failures"].most_common(1) == [("NameError: x", 1)]


def test_report_flags_cost_above_threshold(tmp_path):
    metrics = compute_metrics(load_runs(write_log(tmp_path, [run()])).records)
    assert "Cost alert" in render_report(metrics, tmp_path, 0, cost_alert_usd=0.0001)
    assert "within the $0.05 cost threshold" in render_report(metrics, tmp_path, 0, cost_alert_usd=0.05)


def test_cost_note_appears_alongside_approval_notes(tmp_path):
    approved = run(hitl={"approval_requested": True, "action": "send_email", "decision": "approve"})
    report = render_report(compute_metrics(load_runs(write_log(tmp_path, [approved])).records), tmp_path, 0)
    assert "asked for approval" in report
    assert "cost threshold" in report
