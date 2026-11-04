"""Input guardrail: block restricted requests before the model sees them."""

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langchain_core.messages import AIMessage
from langgraph.runtime import Runtime

GUARDRAIL_KEY = "guardrail"


@dataclass(frozen=True)
class PolicyCategory:
    reason: str
    message: str
    patterns: tuple[re.Pattern[str], ...]


@dataclass(frozen=True)
class InputPolicy:
    policy_id: str
    categories: tuple[PolicyCategory, ...]


@dataclass(frozen=True)
class BlockDecision:
    reason: str
    policy: str
    message: str


def load_input_policy(policy_dir: Path, version: str) -> InputPolicy:
    """Load a versioned policy file. Invalid regular expressions raise re.error."""
    path = policy_dir / f"input_policy_{version}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"Input policy {version} not found at {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return InputPolicy(
        policy_id=f"{raw['name']}_{raw['version']}",
        categories=tuple(
            PolicyCategory(
                reason=category["reason"],
                message=category["message"],
                patterns=tuple(re.compile(p, re.IGNORECASE) for p in category["patterns"]),
            )
            for category in raw["categories"]
        ),
    )


def _normalize(text: str) -> str:
    """Remove formatting tricks: odd Unicode forms, invisible characters, extra whitespace."""
    text = unicodedata.normalize("NFKC", text).replace("’", "'")
    text = "".join(char for char in text if unicodedata.category(char) != "Cf")
    return re.sub(r"\s+", " ", text).strip()


def check_input(text: str, policy: InputPolicy) -> BlockDecision | None:
    """Return a block decision for the first matching category, or None to allow."""
    normalized = _normalize(text)
    for category in policy.categories:
        if any(pattern.search(normalized) for pattern in category.patterns):
            return BlockDecision(category.reason, policy.policy_id, category.message)
    return None


class InputGuardrail(AgentMiddleware):
    """End the run with a refusal before the model is called if the input is restricted."""

    def __init__(self, policy: InputPolicy) -> None:
        super().__init__()
        self.policy = policy

    @hook_config(can_jump_to=["end"])
    def before_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        user_messages = [m for m in state["messages"] if m.type == "human"]
        if not user_messages:
            return None
        decision = check_input(str(user_messages[-1].content), self.policy)
        if decision is None:
            return None
        # The decision travels in message metadata, so model text can't imitate a block.
        refusal = AIMessage(
            content=decision.message,
            additional_kwargs={
                GUARDRAIL_KEY: {
                    "status": "blocked",
                    "reason": decision.reason,
                    "policy": decision.policy,
                }
            },
        )
        return {"messages": [refusal], "jump_to": "end"}
