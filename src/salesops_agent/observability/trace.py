"""Write one JSON trace file per agent run, recording each step of the run."""

import json
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from salesops_agent.guardrails.input import GUARDRAIL_KEY
from salesops_agent.observability.redaction import Redactor


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}... [truncated {len(text) - limit} characters]"


def build_steps(messages: list[BaseMessage], redactor: Redactor, limit: int) -> list[dict[str, Any]]:
    """Turn the run's messages into an ordered, redacted list of steps."""
    steps: list[dict[str, Any]] = []
    for message in messages:
        guardrail = message.additional_kwargs.get(GUARDRAIL_KEY)
        if isinstance(message, HumanMessage):
            step = {"type": "user", "content": redactor.text(str(message.content))}
        elif isinstance(message, AIMessage):
            step = {
                "type": "model",
                "content": _truncate(redactor.text(str(message.content)), limit),
                "tool_calls": [
                    {"id": call["id"], "name": call["name"], "args": redactor.value(call["args"])}
                    for call in message.tool_calls
                ],
            }
        elif isinstance(message, ToolMessage):
            step = {
                "type": "tool_result",
                "tool": message.name,
                "tool_call_id": message.tool_call_id,
                "outcome": "blocked" if guardrail else "ran",
                "output": _truncate(redactor.tool_output(str(message.content)), limit),
            }
        else:
            continue
        if guardrail:
            step["guardrail"] = guardrail
        steps.append(step)
    return steps


def write_trace(traces_dir: Path, run_id: str, trace: dict[str, Any]) -> None:
    traces_dir.mkdir(parents=True, exist_ok=True)
    (traces_dir / f"{run_id}.json").write_text(json.dumps(trace, indent=2), encoding="utf-8")
