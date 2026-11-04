"""Build the agent's tool list from the configured allowlist."""

from langchain_core.tools import BaseTool

from salesops_agent.config import AppConfig
from salesops_agent.data_access.crm_store import CrmStore
from salesops_agent.tools.crm import build_crm_tools
from salesops_agent.tools.email import build_email_tools
from salesops_agent.tools.internal import build_internal_tools


def build_tools(config: AppConfig, store: CrmStore) -> list[BaseTool]:
    """Return the enabled tools in config order. Unknown names raise ValueError."""
    available = {
        built.name: built
        for built in [
            *build_crm_tools(store),
            *build_email_tools(store, config.paths.outbox),
            *build_internal_tools(config.paths.restricted_data),
        ]
    }
    unknown = [name for name in config.tools.enabled if name not in available]
    if unknown:
        raise ValueError(f"Unknown tools in config: {', '.join(unknown)}")
    return [available[name] for name in config.tools.enabled]
