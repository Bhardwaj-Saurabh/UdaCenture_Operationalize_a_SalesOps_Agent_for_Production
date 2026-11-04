"""CRM tools."""

from typing import Any

from langchain_core.tools import BaseTool, tool

from salesops_agent.data_access.crm_store import CrmStore


def account_context(store: CrmStore, account_name_or_id: str) -> dict[str, Any]:
    """Return an account with its related records, or an error if it isn't found."""
    account = store.resolve_account(account_name_or_id)
    if not account:
        return {"error": f"No account found for {account_name_or_id}"}

    account_id = account["account_id"]
    return {
        "account": account,
        "contacts": store.contacts_for(account_id),
        "opportunities": store.opportunities_for(account_id),
        "activities": store.activities_for(account_id),
        "support_tickets": store.tickets_for(account_id),
        "product_usage": store.usage_for(account_id),
    }


def build_crm_tools(store: CrmStore) -> list[BaseTool]:
    @tool
    def lookup_account(account_name_or_id: str) -> dict[str, Any]:
        """Look up a B2B account by account ID or account name."""
        account = store.resolve_account(account_name_or_id)
        if not account:
            return {"error": f"No account found for {account_name_or_id}"}
        return account

    @tool
    def lookup_account_context(account_name_or_id: str) -> dict[str, Any]:
        """Return account context including contacts, opportunities, activities, tickets, and product usage."""
        return account_context(store, account_name_or_id)

    @tool
    def list_open_opportunities(stage: str | None = None) -> list[dict[str, Any]]:
        """List open opportunities, optionally filtered by stage."""
        closed_stages = {"Closed Won", "Closed Lost"}
        results = [o for o in store.opportunities if o["stage"] not in closed_stages]
        if stage:
            results = [o for o in results if o["stage"].lower() == stage.lower()]
        return results

    @tool
    def summarize_pipeline() -> dict[str, Any]:
        """Summarize opportunity count and value by stage."""
        summary: dict[str, dict[str, Any]] = {}
        for opp in store.opportunities:
            stage = opp["stage"]
            if stage not in summary:
                summary[stage] = {"count": 0, "amount_usd": 0}
            summary[stage]["count"] += 1
            summary[stage]["amount_usd"] += opp["amount_usd"]
        return summary

    return [lookup_account, lookup_account_context, list_open_opportunities, summarize_pipeline]
