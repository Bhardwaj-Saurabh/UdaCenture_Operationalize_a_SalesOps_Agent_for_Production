"""Run one question through the agent and record the run."""

import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from salesops_agent.agent.factory import create_salesops_agent
from salesops_agent.config import AppConfig
from salesops_agent.observability.run_log import write_run_log
from salesops_agent.observability.trace import write_trace


@dataclass(frozen=True)
class RunResult:
    run_id: str
    status: str
    answer: str | None
    error: str | None


def run_question(config: AppConfig, question: str) -> RunResult:
    """Invoke the agent, then write the log and trace whether or not the run succeeded."""
    run_id = uuid.uuid4().hex
    timestamp = datetime.now(UTC).isoformat()
    started = time.perf_counter()
    messages = []
    answer = None
    error = None

    try:
        agent = create_salesops_agent(config)
        request = {"messages": [{"role": "user", "content": question}]}
        # Streaming keeps the messages from before a failure, so the trace shows them.
        for state in agent.stream(request, stream_mode="values"):
            messages = state["messages"]
        answer = messages[-1].content
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    latency_seconds = round(time.perf_counter() - started, 3)
    status = "failed" if error else "success"
    tool_calls = [
        {"name": call["name"], "args": call["args"]}
        for message in messages
        for call in getattr(message, "tool_calls", [])
    ]

    write_run_log(
        config.paths.logs,
        {
            "run_id": run_id,
            "timestamp": timestamp,
            "input": question,
            "status": status,
            "tools_called": [call["name"] for call in tool_calls],
            "latency_seconds": latency_seconds,
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
            "status": status,
            "final_output": answer,
            "error": error,
        },
    )
    return RunResult(run_id=run_id, status=status, answer=answer, error=error)
