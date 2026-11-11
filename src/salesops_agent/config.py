"""Load and validate the agent configuration."""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "agent.yaml"


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PromptRef(_Section):
    name: str
    version: str


class AgentSettings(_Section):
    prompt: PromptRef


class ModelSettings(_Section):
    name: str
    temperature: float = 0


class ToolSettings(_Section):
    version: str
    schema_version: str
    enabled: tuple[str, ...]


class GuardrailSettings(_Section):
    input_policy_version: str
    tool_policy_version: str
    output_policy_version: str


class PathSettings(_Section):
    crm_data: Path
    restricted_data: Path
    outbox: Path
    prompts: Path
    guardrails: Path
    logs: Path
    traces: Path
    reports: Path
    evaluation_tasks: Path


class AppConfig(_Section):
    version: str
    agent: AgentSettings
    model: ModelSettings
    tools: ToolSettings
    guardrails: GuardrailSettings
    paths: PathSettings


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> AppConfig:
    """Read a YAML config file and resolve its paths from the project root."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    raw["paths"] = {name: PROJECT_ROOT / value for name, value in raw["paths"].items()}
    return AppConfig.model_validate(raw)
