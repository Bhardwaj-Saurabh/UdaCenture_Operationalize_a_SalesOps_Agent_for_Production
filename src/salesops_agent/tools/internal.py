"""Restricted internal data tools carried over from the prototype.

These return raw HR and financial records, so they are disabled in
config/agent.yaml. Files are read only when a tool is called, which means a normal
run never loads restricted data. Step 5 adds the guardrails that block these calls.
"""

import json
from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool, tool


def build_internal_tools(restricted_dir: Path) -> list[BaseTool]:
    def read(file_name: str) -> Any:
        return json.loads((restricted_dir / file_name).read_text(encoding="utf-8"))

    @tool
    def lookup_internal_hr_data(query: str) -> dict[str, Any]:
        """Look up restricted internal HR data."""
        return {"query": query, "data": read("internal_hr_data.json")}

    @tool
    def lookup_internal_financial_data(query: str) -> dict[str, Any]:
        """Look up confidential internal financial data."""
        return {"query": query, "data": read("internal_financial_data.json")}

    return [lookup_internal_hr_data, lookup_internal_financial_data]
