"""Create the SalesOps agent from configuration."""

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from salesops_agent.config import AppConfig
from salesops_agent.data_access.crm_store import CrmStore
from salesops_agent.guardrails.input import InputGuardrail, load_input_policy
from salesops_agent.prompts import load_prompt
from salesops_agent.tools.registry import build_tools


def create_salesops_agent(config: AppConfig):
    """Build the agent. The API key and base URL come from the environment."""
    input_policy = load_input_policy(
        config.paths.guardrails, config.guardrails.input_policy_version
    )
    return create_agent(
        model=ChatOpenAI(model=config.model.name, temperature=config.model.temperature),
        tools=build_tools(config, CrmStore.from_directory(config.paths.crm_data)),
        system_prompt=load_prompt(config.paths.prompts, config.agent.prompt),
        middleware=[InputGuardrail(input_policy)],
    )
