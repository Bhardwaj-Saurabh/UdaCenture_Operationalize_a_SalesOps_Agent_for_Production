import pytest
import yaml
from pydantic import ValidationError

from salesops_agent.config import DEFAULT_CONFIG_PATH, PROJECT_ROOT, PromptRef, load_config
from salesops_agent.prompts import load_prompt


def test_default_config_resolves_paths_from_the_project_root():
    config = load_config()
    assert config.paths.crm_data == PROJECT_ROOT / "data" / "crm"


def test_unknown_config_keys_are_rejected(tmp_path):
    raw = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    raw["model"]["temprature"] = 0.5
    path = tmp_path / "agent.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_config(path)


def test_configured_prompt_loads_without_the_prototype_internal_tools_line():
    config = load_config()
    prompt = load_prompt(config.paths.prompts, config.agent.prompt)
    assert prompt.startswith("You are a SalesOps Agent")
    assert "internal tools" not in prompt


def test_missing_prompt_version_raises_a_clear_error():
    config = load_config()
    with pytest.raises(FileNotFoundError, match="salesops_system/v999"):
        load_prompt(config.paths.prompts, PromptRef(name="salesops_system", version="v999"))
