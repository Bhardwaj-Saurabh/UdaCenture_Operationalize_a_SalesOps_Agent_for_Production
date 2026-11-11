"""Run one question through the agent and record the run."""

import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from salesops_agent.agent.factory import create_salesops_agent
from salesops_agent.config import AppConfig
from salesops_agent.guardrails.input import GUARDRAIL_KEY
from salesops_agent.observability.run_log import write_run_log
from salesops_agent.observability.trace import write_trace


@dataclass(frozen=True)
class RunResult:
    run_id: str
    status: str
    answer: str | None
    error: str | None
    tools_called: list[str]
    latency_seconds: float
    guardrail: dict[str, str] | None = None
    tools_blocked: tuple[str, ...] = ()
    hitl: dict[str, Any] | None = None


APPROVAL_DECISIONS = ("approve", "reject")
AWAITING_APPROVAL_MESSAGE = (
    "This action needs human approval and was not completed. "
    "Re-run with --approval approve or --approval reject."
)


def run_question(
    config: AppConfig,
    question: str,
    model: BaseChatModel | None = None,
    approval: str | None = None,
) -> RunResult:
    """Invoke the agent, then write the log and trace whether or not the run succeeded.

    If the agent pauses for approval, `approval` ("approve" or "reject") resumes it.
    With no decision the action stays pending and is not completed.
    """
    if approval not in (None, *APPROVAL_DECISIONS):
        raise ValueError(f"approval must be one of {APPROVAL_DECISIONS} or None")
    run_id = uuid.uuid4().hex
    timestamp = datetime.now(UTC).isoformat()
    started = time.perf_counter()
    messages = []
    answer = None
    error = None
    hitl: dict[str, Any] = {"approval_requested": False, "request": None, "decision": None}
    awaiting_approval = False

    try:
        agent = create_salesops_agent(config, model, checkpointer=InMemorySaver())
        thread = {"configurable": {"thread_id": run_id}}
        request: Any = {"messages": [{"role": "user", "content": question}]}
        # Streaming keeps the messages from before a failure, so the trace shows them.
        for state in agent.stream(request, thread, stream_mode="values"):
            messages = state.get("messages", messages)
        pending = agent.get_state(thread).interrupts
        if pending:
            hitl.update(approval_requested=True, request=pending[0].value, decision=approval)
            if approval:
                resume = Command(resume={"type": approval})
                for state in agent.stream(resume, thread, stream_mode="values"):
                    messages = state.get("messages", messages)
            # One decision covers one action; a second request stays pending.
            awaiting_approval = bool(agent.get_state(thread).interrupts)
        answer = AWAITING_APPROVAL_MESSAGE if awaiting_approval else messages[-1].content
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    latency_seconds = round(time.perf_counter() - started, 3)
    guarded = [message for message in messages if GUARDRAIL_KEY in message.additional_kwargs]
    interventions = [message.additional_kwargs[GUARDRAIL_KEY] for message in guarded]
    blocked_call_ids = {getattr(message, "tool_call_id", None) for message in guarded}
    if error:
        status = "failed"
    elif interventions:
        status = "blocked"
    elif awaiting_approval:
        status = "awaiting_approval"
    else:
        status = "success"
    hitl_summary = {
        "approval_requested": hitl["approval_requested"],
        "action": (hitl["request"] or {}).get("action"),
        "decision": hitl["decision"],
    }
    answered_call_ids = {getattr(message, "tool_call_id", None) for message in messages}

    def outcome(call_id: str) -> str:
        if call_id in blocked_call_ids:
            return "blocked"
        if awaiting_approval and call_id not in answered_call_ids:
            return "pending"
        return "ran"

    tool_calls = [
        {"name": call["name"], "args": call["args"], "outcome": outcome(call["id"])}
        for message in messages
        for call in getattr(message, "tool_calls", [])
    ]

    # Calls a guardrail stopped, or that still wait for approval, never ran.
    tools_called = [call["name"] for call in tool_calls if call["outcome"] == "ran"]
    tools_blocked = tuple(call["name"] for call in tool_calls if call["outcome"] == "blocked")

    write_run_log(
        config.paths.logs,
        {
            "run_id": run_id,
            "timestamp": timestamp,
            "input": question,
            "status": status,
            "tools_called": tools_called,
            "tools_blocked": tools_blocked,
            "latency_seconds": latency_seconds,
            "guardrail_interventions": interventions,
            "hitl": hitl_summary,
            "error": error,
        },
    )
    # Tool outputs are left out until Step 6 adds redaction, as they can hold restricted data.
    write_trace(
        config.paths.traces,
        run_id,
        {
            "run_id": run_id,
            "timestamp": timestamp,
            "versions": {
                "config": config.version,
                "prompt": f"{config.agent.prompt.name}/{config.agent.prompt.version}",
                "tools": config.tools.version,
                "schemas": config.tools.schema_version,
            },
            "model": config.model.name,
            "input": question,
            "tool_calls": tool_calls,
            "guardrail_interventions": interventions,
            # The full approval request, including the email the reviewer was asked about.
            "hitl": hitl,
            "status": status,
            "final_output": answer,
            "error": error,
        },
    )
    return RunResult(
        run_id=run_id,
        status=status,
        answer=answer,
        error=error,
        tools_called=tools_called,
        latency_seconds=latency_seconds,
        guardrail=interventions[0] if interventions else None,
        tools_blocked=tools_blocked,
        hitl=hitl_summary,
    )
