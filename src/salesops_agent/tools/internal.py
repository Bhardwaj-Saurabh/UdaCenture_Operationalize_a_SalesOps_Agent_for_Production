"""Internal HR and financial data tools carried over from the prototype."""

import json
from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool, tool

from salesops_agent.schemas.v1 import InternalDataInput


def build_internal_tools(restricted_dir: Path) -> list[BaseTool]:
    def read(file_name: str) -> Any:
        return json.loads((restricted_dir / file_name).read_text(encoding="utf-8"))

    @tool(args_schema=InternalDataInput)
    def lookup_internal_hr_data(query: str) -> dict[str, Any]:
        """Look up internal HR data. Prototype-only tool. Not production safe."""
        return {"query": query, "data": read("internal_hr_data.json")}

    @tool(args_schema=InternalDataInput)
    def lookup_internal_financial_data(query: str) -> dict[str, Any]:
        """Look up internal financial data. Prototype-only tool. Not production safe."""
        return {"query": query, "data": read("internal_financial_data.json")}

    return [lookup_internal_hr_data, lookup_internal_financial_data]
