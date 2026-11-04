"""Load versioned prompts from disk."""

from pathlib import Path

from salesops_agent.config import PromptRef


def load_prompt(prompts_dir: Path, ref: PromptRef) -> str:
    """Return the prompt text for a name and version, such as salesops_system/v1."""
    path = prompts_dir / ref.name / f"{ref.version}.md"
    if not path.is_file():
        raise FileNotFoundError(f"Prompt {ref.name}/{ref.version} not found at {path}")
    return path.read_text(encoding="utf-8").strip()
