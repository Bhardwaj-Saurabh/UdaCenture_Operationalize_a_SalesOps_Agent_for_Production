"""Read-only tools over approved CRM data."""

from typing import Any

from langchain_core.tools import BaseTool, tool

from salesops_agent.data_access.crm_store import CLOSED_STAGES, CrmStore, Record


def resolve_single_account(
    store: CrmStore, name_or_id: str
) -> tuple[Record | None, dict[str, Any] | None]:
    """Return (account, None) for one match, or (None, error) for none or several."""
    matches = store.find_accounts(name_or_id)
    if not matches:
        return None, {"error": f"No account found for {name_or_id}"}
    if len(matches) > 1:
        return None, {
            "error": f"Several accounts match {name_or_id}. Ask which one was meant.",
            "candidates": [{"account_id": a["account_id"], "name": a["name"]} for a in matches],
        }
    return matches[0], None


def build_crm_tools(store: CrmStore) -> list[BaseTool]:
    @tool
    def lookup_account(account_name_or_id: str) -> dict[str, Any]:
        """Look up a B2B account by account ID or account name."""
        account, error = resolve_single_account(store, account_name_or_id)
        return error or account

    @tool
    def lookup_account_context(account_name_or_id: str) -> dict[str, Any]:
        """Return an account with its contacts, opportunities, activities, tickets, and usage."""
        account, error = resolve_single_account(store, account_name_or_id)
        if error:
            return error
        account_id = account["account_id"]
        return {
            "account": account,
            "contacts": store.contacts_for(account_id),
            "opportunities": store.opportunities_for(account_id),
            "activities": store.activities_for(account_id),
            "support_tickets": store.tickets_for(account_id),
            "product_usage": store.usage_for(account_id),
        }

    @tool
    def list_open_opportunities(stage: str | None = None) -> list[dict[str, Any]]:
        """List open opportunities, optionally filtered by stage."""
        results = [o for o in store.opportunities if o["stage"] not in CLOSED_STAGES]
        if stage:
            results = [o for o in results if o["stage"].lower() == stage.lower()]
        return results

    @tool
    def summarize_pipeline() -> dict[str, Any]:
        """Summarize opportunity count and value by stage, with open pipeline totals.

        Closed Won and Closed Lost appear in by_stage but not in open_pipeline.
        """
        by_stage: dict[str, dict[str, Any]] = {}
        open_pipeline = {"count": 0, "amount_usd": 0}
        for opportunity in store.opportunities:
            stage = opportunity["stage"]
            is_open = stage not in CLOSED_STAGES
            entry = by_stage.setdefault(stage, {"count": 0, "amount_usd": 0, "is_open": is_open})
            entry["count"] += 1
            entry["amount_usd"] += opportunity["amount_usd"]
            if is_open:
                open_pipeline["count"] += 1
                open_pipeline["amount_usd"] += opportunity["amount_usd"]
        return {"by_stage": by_stage, "open_pipeline": open_pipeline}

    return [lookup_account, lookup_account_context, list_open_opportunities, summarize_pipeline]
