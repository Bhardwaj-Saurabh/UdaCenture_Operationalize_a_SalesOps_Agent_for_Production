"""Output guardrail: stop restricted content from reaching the user or a customer."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.messages import AIMessage, RemoveMessage, ToolMessage
from langgraph.runtime import Runtime

from salesops_agent.guardrails.input import GUARDRAIL_KEY, REFUSAL_KEY


@dataclass(frozen=True)
class OutputPolicy:
    policy_id: str
    customer_facing_tools: frozenset[str]
    response_message: str
    email_message: str
    categories: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...]


def load_output_policy(policy_dir: Path, version: str) -> OutputPolicy:
    """Load a versioned policy file. Invalid regular expressions raise re.error."""
    path = policy_dir / f"output_policy_{version}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"Output policy {version} not found at {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return OutputPolicy(
        policy_id=f"{raw['name']}_{raw['version']}",
        customer_facing_tools=frozenset(raw["customer_facing_tools"]),
        response_message=raw["response_message"],
        email_message=raw["email_message"],
        categories=tuple(
            (
                category["reason"],
                tuple(re.compile(p, re.IGNORECASE) for p in category["patterns"]),
            )
            for category in raw["categories"]
        ),
    )


def check_output(text: str, policy: OutputPolicy) -> str | None:
    """Return the reason to block the text, or None to allow it."""
    normalized = re.sub(r"\s+", " ", text.replace("’", "'"))
    for reason, patterns in policy.categories:
        if any(pattern.search(normalized) for pattern in patterns):
            return reason
    return None


class OutputGuardrail(AgentMiddleware):
    """Replace a restricted final response with a refusal, and stop unsafe emails."""

    def __init__(self, policy: OutputPolicy) -> None:
        super().__init__()
        self.policy = policy

    def _payload(self, reason: str, **extra: str) -> dict[str, str]:
        return {"status": "blocked", "reason": reason, "policy": self.policy.policy_id, **extra}

    def wrap_tool_call(self, request: Any, handler: Callable) -> Any:
        name = request.tool_call["name"]
        if name in self.policy.customer_facing_tools:
            reason = check_output(" ".join(map(str, request.tool_call["args"].values())), self.policy)
            if reason:
                return ToolMessage(
                    content=self.policy.email_message,
                    name=name,
                    tool_call_id=request.tool_call["id"],
                    additional_kwargs={GUARDRAIL_KEY: self._payload(reason, tool=name)},
                )
        return handler(request)

    def after_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        last = state["messages"][-1] if state["messages"] else None
        if not isinstance(last, AIMessage):
            return None
        # Refusals written by the guardrails are fixed text and are not checked again.
        if GUARDRAIL_KEY in last.additional_kwargs or REFUSAL_KEY in last.additional_kwargs:
            return None
        reason = check_output(str(last.content), self.policy)
        if reason is None:
            return None
        refusal = AIMessage(
            content=self.policy.response_message,
            additional_kwargs={GUARDRAIL_KEY: self._payload(reason)},
        )
        # Removing the original keeps the restricted text out of the run's state.
        return {"messages": [RemoveMessage(id=last.id), refusal]}
