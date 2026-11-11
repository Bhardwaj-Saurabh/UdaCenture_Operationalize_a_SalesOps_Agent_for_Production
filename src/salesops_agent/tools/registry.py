"""Build the agent's tool list from the configured allowlist."""

from langchain_core.tools import BaseTool

from salesops_agent.config import AppConfig
from salesops_agent.data_access.crm_store import CrmStore
from salesops_agent.schemas.v1 import SCHEMA_VERSION
from salesops_agent.tools import TOOLS_VERSION
from salesops_agent.tools.analysis import build_analysis_tools
from salesops_agent.tools.crm import build_crm_tools
from salesops_agent.tools.email import build_email_tools
from salesops_agent.tools.internal import build_internal_tools


def build_tools(config: AppConfig, store: CrmStore) -> list[BaseTool]:
    """Return the enabled tools in config order.

    Raises ValueError for unknown tool names, or if the config pins a tool or schema
    version that differs from the code.
    """
    if config.tools.version != TOOLS_VERSION:
        raise ValueError(
            f"Config pins tools {config.tools.version}, but the code provides {TOOLS_VERSION}"
        )
    if config.tools.schema_version != SCHEMA_VERSION:
        raise ValueError(
            f"Config pins schemas {config.tools.schema_version}, "
            f"but the code provides {SCHEMA_VERSION}"
        )

    available = {
        built.name: built
        for built in [
            *build_crm_tools(store),
            *build_analysis_tools(store, config.sandbox),
            *build_email_tools(store, config.paths.outbox),
            *build_internal_tools(config.paths.restricted_data),
        ]
    }
    unknown = [name for name in config.tools.enabled if name not in available]
    if unknown:
        raise ValueError(f"Unknown tools in config: {', '.join(unknown)}")
    return [available[name] for name in config.tools.enabled]
