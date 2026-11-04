"""Run one question through the agent and record the run."""

import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from langchain_core.language_models import BaseChatModel

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


def run_question(
    config: AppConfig, question: str, model: BaseChatModel | None = None
) -> RunResult:
    """Invoke the agent, then write the log and trace whether or not the run succeeded."""
    run_id = uuid.uuid4().hex
    timestamp = datetime.now(UTC).isoformat()
    started = time.perf_counter()
    messages = []
    answer = None
    error = None

    try:
        agent = create_salesops_agent(config, model)
        request = {"messages": [{"role": "user", "content": question}]}
        # Streaming keeps the messages from before a failure, so the trace shows them.
        for state in agent.stream(request, stream_mode="values"):
            messages = state["messages"]
        answer = messages[-1].content
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    latency_seconds = round(time.perf_counter() - started, 3)
    guarded = [message for message in messages if GUARDRAIL_KEY in message.additional_kwargs]
    interventions = [message.additional_kwargs[GUARDRAIL_KEY] for message in guarded]
    blocked_call_ids = {getattr(message, "tool_call_id", None) for message in guarded}
    status = "failed" if error else "blocked" if interventions else "success"
    tool_calls = [
        {"name": call["name"], "args": call["args"], "blocked": call["id"] in blocked_call_ids}
        for message in messages
        for call in getattr(message, "tool_calls", [])
    ]

    # Proposed calls that a guardrail stopped never ran, so they aren't counted as called.
    tools_called = [call["name"] for call in tool_calls if not call["blocked"]]
    tools_blocked = tuple(call["name"] for call in tool_calls if call["blocked"])

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
    )
