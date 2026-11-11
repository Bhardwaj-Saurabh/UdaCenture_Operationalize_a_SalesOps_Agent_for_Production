"""Create the SalesOps agent from configuration."""

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver

from salesops_agent.config import AppConfig
from salesops_agent.data_access.crm_store import CrmStore
from salesops_agent.guardrails.input import InputGuardrail, load_input_policy
from salesops_agent.guardrails.output import OutputGuardrail, load_output_policy
from salesops_agent.guardrails.tool import ToolGuardrail, load_tool_policy
from salesops_agent.prompts import load_prompt
from salesops_agent.tools.registry import build_tools


def create_salesops_agent(
    config: AppConfig,
    model: BaseChatModel | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
):
    """Build the agent. The API key and base URL come from the environment.

    Evaluation can pass its own model to script exact output. A checkpointer is
    required for approval pauses, because it holds the run's state until it resumes.
    """
    input_policy = load_input_policy(
        config.paths.guardrails, config.guardrails.input_policy_version
    )
    tool_policy = load_tool_policy(config.paths.guardrails, config.guardrails.tool_policy_version)
    output_policy = load_output_policy(
        config.paths.guardrails, config.guardrails.output_policy_version
    )
    return create_agent(
        model=model or ChatOpenAI(model=config.model.name, temperature=config.model.temperature),
        tools=build_tools(config, CrmStore.from_directory(config.paths.crm_data)),
        system_prompt=load_prompt(config.paths.prompts, config.agent.prompt),
        # The output guardrail wraps tool calls outside the tool guardrail, so an unsafe
        # email is rejected on its content before the approval check is reached.
        middleware=[
            InputGuardrail(input_policy),
            OutputGuardrail(output_policy),
            ToolGuardrail(tool_policy),
        ],
        checkpointer=checkpointer,
    )
