"""Sandbox checks: safe analysis runs, and unsafe code is rejected or stopped."""

import pytest

from salesops_agent.config import load_config
from salesops_agent.data_access.crm_store import CrmStore
from salesops_agent.sandbox import APPROVED_DATASETS, run_sandboxed, validate_code

CONFIG = load_config()
STORE = CrmStore.from_directory(CONFIG.paths.crm_data)
DATASETS = {name: getattr(STORE, name) for name in APPROVED_DATASETS}


def run(code: str, timeout: float = 10) -> dict[str, str]:
    return run_sandboxed(code, DATASETS, timeout_seconds=timeout, max_output_chars=4000)


def test_counts_open_opportunities():
    result = run(
        "open_opps = opportunities[~opportunities['stage'].isin(['Closed Won', 'Closed Lost'])]\n"
        "print(len(open_opps))"
    )
    assert result == {"status": "ok", "output": "133"}


def test_aggregates_tickets_by_severity():
    result = run("print(support_tickets['severity'].value_counts().to_dict())")
    assert result["status"] == "ok"
    assert "'critical': 7" in result["output"]


@pytest.mark.parametrize(
    ("code", "reason"),
    [
        ("import os", "imports are not allowed"),
        ("from subprocess import run", "imports are not allowed"),
        ("open('data/restricted/internal_hr_data.json').read()", "blocked name: open"),
        ("eval('1 + 1')", "blocked name: eval"),
        ("exec('x = 1')", "blocked name: exec"),
        ("__import__('os')", "blocked name: __import__"),
        ("getattr(accounts, 'to_csv')('leak.csv')", "blocked name: getattr"),
        ("().__class__.__bases__[0].__subclasses__()", "blocked attribute: __subclasses__"),
        ("(x for x in []).gi_frame.f_back", "blocked attribute: f_back"),
        ("accounts.to_csv('leak.csv')", "blocked attribute: to_csv"),
        ("accounts.read_json('http://example.com')", "blocked attribute: read_json"),
        ("accounts.query('health_score > 50')", "blocked attribute: query"),
        ("'{0.__class__}'.format(accounts)", "blocked attribute: format"),
    ],
)
def test_unsafe_code_is_rejected_before_running(code, reason):
    assert validate_code(code) == (False, reason)
    assert run(code) == {"status": "error", "error": f"code rejected: {reason}"}


def test_timeout_stops_runaway_code():
    result = run("while True:\n    pass", timeout=3)
    assert result == {"status": "error", "error": "execution timed out after 3s"}


def test_builtins_outside_the_safe_set_are_missing():
    assert run("print(hash(1))")["error"] == "NameError: name 'hash' is not defined"


def test_output_is_capped():
    result = run_sandboxed("print('x' * 50)", DATASETS, timeout_seconds=10, max_output_chars=10)
    assert result["output"] == "xxxxxxxxxx\n[output truncated]"


def test_only_approved_crm_tables_are_provided():
    assert set(DATASETS) == {
        "accounts", "opportunities", "activities", "support_tickets", "product_usage"
    }  # fmt: skip
    assert "salary_usd" not in str(DATASETS)
    assert "CONFIDENTIAL" not in str(DATASETS)
    with pytest.raises(ValueError, match="contacts"):
        run_sandboxed("print(1)", {"contacts": []}, timeout_seconds=10, max_output_chars=100)
