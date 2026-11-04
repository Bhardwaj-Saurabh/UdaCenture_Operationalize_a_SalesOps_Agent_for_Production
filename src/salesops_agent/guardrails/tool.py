"""Tool guardrail: inspect each proposed tool call before it executes."""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.runtime import Runtime

from salesops_agent.guardrails.input import GUARDRAIL_KEY


@dataclass(frozen=True)
class ToolPolicy:
    policy_id: str
    allowed_tools: frozenset[str]
    restricted_tools: frozenset[str]
    approval_required_tools: frozenset[str]
    restricted_argument_patterns: tuple[re.Pattern[str], ...]
    restricted_output_fields: tuple[str, ...]
    messages: dict[str, str]


def load_tool_policy(policy_dir: Path, version: str) -> ToolPolicy:
    """Load a versioned policy file. Invalid regular expressions raise re.error."""
    path = policy_dir / f"tool_policy_{version}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"Tool policy {version} not found at {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return ToolPolicy(
        policy_id=f"{raw['name']}_{raw['version']}",
        allowed_tools=frozenset(raw["allowed_tools"]),
        restricted_tools=frozenset(raw["restricted_tools"]),
        approval_required_tools=frozenset(raw["approval_required_tools"]),
        restricted_argument_patterns=tuple(
            re.compile(pattern, re.IGNORECASE) for pattern in raw["restricted_argument_patterns"]
        ),
        restricted_output_fields=tuple(raw["restricted_output_fields"]),
        messages=raw["messages"],
    )


def check_tool_call(name: str, args: dict[str, Any], policy: ToolPolicy) -> str | None:
    """Return the reason to block a proposed call, or None to allow it."""
    if name in policy.restricted_tools:
        return "restricted_internal_data"
    if name in policy.approval_required_tools:
        return "approval_required"
    if name not in policy.allowed_tools:
        return "tool_not_allowed"
    arguments = json.dumps(args)
    if any(pattern.search(arguments) for pattern in policy.restricted_argument_patterns):
        return "out_of_scope_request"
    return None


def has_restricted_field(output: str, policy: ToolPolicy) -> bool:
    return any(field in output for field in policy.restricted_output_fields)


class ToolGuardrail(AgentMiddleware):
    """Block tool calls by policy, then end the run before the model can try another route."""

    def __init__(self, policy: ToolPolicy) -> None:
        super().__init__()
        self.policy = policy

    def _blocked(self, name: str, call_id: str, reason: str) -> ToolMessage:
        message = self.policy.messages[reason]
        return ToolMessage(
            content=message,
            name=name,
            tool_call_id=call_id,
            additional_kwargs={
                GUARDRAIL_KEY: {
                    "status": "blocked",
                    "reason": reason,
                    "policy": self.policy.policy_id,
                    "tool": name,
                }
            },
        )

    def wrap_tool_call(self, request: Any, handler: Callable) -> Any:
        name = request.tool_call["name"]
        call_id = request.tool_call["id"]
        reason = check_tool_call(name, request.tool_call["args"], self.policy)
        if reason:
            return self._blocked(name, call_id, reason)

        result = handler(request)
        # A second check in case a permitted tool ever returns restricted data.
        if isinstance(result, ToolMessage) and has_restricted_field(
            str(result.content), self.policy
        ):
            return self._blocked(name, call_id, "restricted_output_field")
        return result

    @hook_config(can_jump_to=["end"])
    def before_model(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        for message in state["messages"]:
            if isinstance(message, ToolMessage) and GUARDRAIL_KEY in message.additional_kwargs:
                return {"messages": [AIMessage(content=message.content)], "jump_to": "end"}
        return None
