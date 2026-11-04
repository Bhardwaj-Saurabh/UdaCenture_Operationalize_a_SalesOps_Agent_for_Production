"""Email drafting and fake sending through a local JSON outbox."""

import json
from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool, tool

from salesops_agent.data_access.crm_store import CrmStore
from salesops_agent.tools.crm import account_context


def build_email_tools(store: CrmStore, outbox_path: Path) -> list[BaseTool]:
    @tool
    def draft_email(account_name_or_id: str, purpose: str) -> dict[str, Any]:
        """Draft a follow-up email for an account's primary contact."""
        context = account_context(store, account_name_or_id)
        if "error" in context:
            return context

        account = context["account"]
        account_contacts = context["contacts"]
        primary_contact = next(
            (c for c in account_contacts if c.get("is_primary")),
            account_contacts[0] if account_contacts else None,
        )

        if not primary_contact:
            return {"error": f"No contact found for account {account['name']}"}

        return {
            "to": primary_contact["email"],
            "subject": f"Following up on {account['name']}",
            "body": (
                f"Hi {primary_contact['first_name']},\n\n"
                f"I wanted to follow up regarding {purpose}.\n\n"
                "Best,\nUdaCenture SalesOps Agent\n"
            ),
            "status": "drafted",
        }

    @tool
    def send_email(to: str, subject: str, body: str) -> dict[str, Any]:
        """Fake-send an email by appending it to a local JSON outbox."""
        outbox = (
            json.loads(outbox_path.read_text(encoding="utf-8")) if outbox_path.exists() else []
        )
        message = {"to": to, "subject": subject, "body": body, "status": "sent"}
        outbox.append(message)
        outbox_path.parent.mkdir(parents=True, exist_ok=True)
        outbox_path.write_text(json.dumps(outbox, indent=2), encoding="utf-8")
        return {"status": "sent", "message": message}

    return [draft_email, send_email]
