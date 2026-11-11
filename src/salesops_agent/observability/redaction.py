"""Redact sensitive data before it is written to logs or traces.

Text is checked against the output guardrail's patterns, so anything the agent may
not say is also kept out of logs and traces. Values of restricted fields (from the
tool policy and `observability.redact_fields` in the config) are replaced, and email addresses are masked.
"""

import json
import re
from typing import Any

from salesops_agent.config import AppConfig
from salesops_agent.guardrails.output import OutputPolicy, load_output_policy
from salesops_agent.guardrails.tool import load_tool_policy

EMAIL = re.compile(r"\b([A-Za-z0-9])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")


class Redactor:
    def __init__(self, output_policy: OutputPolicy, restricted_fields: tuple[str, ...]) -> None:
        self.policy_id = output_policy.policy_id
        self.categories = output_policy.categories
        self.restricted_fields = restricted_fields

    def _restricted_key(self, key: str) -> bool:
        if any(key == field or key.startswith(field) for field in self.restricted_fields):
            return True
        # A field whose name is itself restricted, such as CONFIDENTIAL_M_AND_A.
        return self.text(key) != key

    def text(self, value: str) -> str:
        for reason, patterns in self.categories:
            for pattern in patterns:
                value = pattern.sub(f"[REDACTED:{reason}]", value)
        return EMAIL.sub(r"\1***@\2", value)

    def value(self, value: Any) -> Any:
        """Redact nested data: restricted keys lose their values, and strings are scanned."""
        if isinstance(value, dict):
            return {
                key: "[REDACTED]" if self._restricted_key(str(key)) else self.value(item)
                for key, item in value.items()
            }
        if isinstance(value, list | tuple):
            return [self.value(item) for item in value]
        if isinstance(value, str):
            return self.text(value)
        return value

    def tool_output(self, content: str) -> str:
        """Tool results arrive as text; JSON results are redacted field by field."""
        try:
            return json.dumps(self.value(json.loads(content)))
        except (json.JSONDecodeError, TypeError):
            return self.text(content)


def build_redactor(config: AppConfig) -> Redactor:
    output_policy = load_output_policy(
        config.paths.guardrails, config.guardrails.output_policy_version
    )
    tool_policy = load_tool_policy(config.paths.guardrails, config.guardrails.tool_policy_version)
    fields = (*tool_policy.restricted_output_fields, *config.observability.redact_fields)
    return Redactor(output_policy, tuple(dict.fromkeys(fields)))
