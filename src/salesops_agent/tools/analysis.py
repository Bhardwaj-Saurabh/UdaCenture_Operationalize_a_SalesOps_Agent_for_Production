"""Sandboxed analysis tool over approved CRM data."""

from typing import Any

from langchain_core.tools import BaseTool, tool

from salesops_agent.config import SandboxSettings
from salesops_agent.data_access.crm_store import CrmStore
from salesops_agent.sandbox import APPROVED_DATASETS, run_sandboxed
from salesops_agent.schemas.v1 import CrmAnalysisInput


def build_analysis_tools(store: CrmStore, settings: SandboxSettings) -> list[BaseTool]:
    # Only approved CRM tables go in. Contacts are left out because no analysis needs
    # personal details, and restricted HR and financial data never reaches the store.
    datasets = {name: getattr(store, name) for name in APPROVED_DATASETS}

    @tool(args_schema=CrmAnalysisInput)
    def run_crm_analysis(code: str) -> dict[str, Any]:
        """Run Python analysis code over CRM data and return what it prints.

        Use this for counts, sums, averages, and other calculations instead of
        working them out yourself. Print the results you need.

        Available pandas DataFrames:
        - accounts: account_id, name, account_status, segment, industry, region,
          account_owner, health_score, contract_start, contract_end, arr_usd, created_at, notes
        - opportunities: opportunity_id, account_id, name, type, stage, amount_usd,
          close_date, probability, next_step, notes
        - activities: activity_id, account_id, date, type, owner, summary, sentiment
        - support_tickets: ticket_id, account_id, created_at, severity, status, category, summary
        - product_usage: usage_id, account_id, period, active_users, monthly_logins,
          usage_trend, feature_adoption_score

        Also available: to_datetime, Timestamp, and basic built-ins such as len, sum,
        round, and sorted. Imports, files, and network access are not allowed.
        Open stages are every stage except "Closed Won" and "Closed Lost".
        """
        return run_sandboxed(
            code,
            datasets,
            timeout_seconds=settings.timeout_seconds,
            max_output_chars=settings.max_output_chars,
        )

    return [run_crm_analysis]
