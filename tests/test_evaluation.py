"""Evaluation suite: uv run pytest. Writes reports/evaluation_report.json."""

import pytest
from dotenv import load_dotenv

from salesops_agent.agent.runner import run_question
from salesops_agent.config import load_config
from salesops_agent.evaluation.scripted_model import (
    scripted_answer_model,
    scripted_tool_call_model,
)
from salesops_agent.evaluation.suite import load_tasks, score_run, write_report

load_dotenv(override=True)
CONFIG = load_config()
TASKS = load_tasks(CONFIG.paths.evaluation_tasks)


@pytest.fixture(scope="module")
def outcomes():
    collected = []
    yield collected
    write_report(CONFIG.paths.reports / "evaluation_report.json", collected)


@pytest.mark.parametrize("task", TASKS, ids=[task.task_id for task in TASKS])
def test_golden_task(task, outcomes):
    model = None
    if task.scripted_tool:
        model = scripted_tool_call_model(task.scripted_tool, task.scripted_args)
    elif task.scripted_answer:
        model = scripted_answer_model(task.scripted_answer)
    outcome = score_run(task, run_question(CONFIG, task.question, model))
    outcomes.append(outcome)
    assert outcome.passed, outcome.failure_reason
