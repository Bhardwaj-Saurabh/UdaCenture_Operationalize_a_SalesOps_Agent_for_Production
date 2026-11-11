"""Fake models that return exact output, so guardrails can be tested repeatably."""

from typing import Any

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage


class _ScriptedModel(GenericFakeChatModel):
    def bind_tools(self, tools: Any, **kwargs: Any) -> "_ScriptedModel":
        return self


def scripted_tool_call_model(tool: str, args: dict[str, Any]) -> _ScriptedModel:
    """Propose the tool call, then answer if the run is allowed to continue."""
    call = {"name": tool, "args": args, "id": "scripted_call", "type": "tool_call"}
    return _ScriptedModel(
        messages=iter([AIMessage(content="", tool_calls=[call]), AIMessage(content="Done.")])
    )


def scripted_answer_model(answer: str) -> _ScriptedModel:
    """Return this final answer without calling any tools."""
    return _ScriptedModel(messages=iter([AIMessage(content=answer)]))
