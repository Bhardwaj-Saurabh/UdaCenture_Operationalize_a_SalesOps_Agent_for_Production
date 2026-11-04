"""In-memory access to the approved CRM data files."""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

Record = dict[str, Any]


def normalize_lookup_text(value: str) -> str:
    """Normalize names and IDs for forgiving lookups."""
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\b(incorporated|inc|corp|corporation|ltd|limited|llc|co|company)\b", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _load_records(path: Path) -> list[Record]:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


@dataclass(frozen=True)
class CrmStore:
    accounts: list[Record]
    contacts: list[Record]
    opportunities: list[Record]
    activities: list[Record]
    support_tickets: list[Record]
    product_usage: list[Record]

    @classmethod
    def from_directory(cls, directory: Path) -> "CrmStore":
        return cls(
            accounts=_load_records(directory / "accounts.json"),
            contacts=_load_records(directory / "contacts.json"),
            opportunities=_load_records(directory / "opportunities.json"),
            activities=_load_records(directory / "activities.json"),
            support_tickets=_load_records(directory / "support_tickets.json"),
            product_usage=_load_records(directory / "product_usage.json"),
        )

    def find_account_by_id(self, account_id: str) -> Record | None:
        """Look up an account by exact account ID, case-insensitive."""
        account_id_normalized = account_id.strip().lower()
        return next(
            (a for a in self.accounts if a["account_id"].lower() == account_id_normalized), None
        )

    def find_account_by_name(self, name: str) -> Record | None:
        """Look up an account by name using forgiving matching."""
        query = normalize_lookup_text(name)

        # Exact normalized match
        for account in self.accounts:
            if query == normalize_lookup_text(account["name"]):
                return account

        # Partial normalized match in either direction
        for account in self.accounts:
            account_name = normalize_lookup_text(account["name"])
            if query and (query in account_name or account_name in query):
                return account

        # Fuzzy fallback for small typos
        normalized_names = {normalize_lookup_text(a["name"]): a for a in self.accounts}
        matches = difflib.get_close_matches(query, normalized_names.keys(), n=1, cutoff=0.82)
        if matches:
            return normalized_names[matches[0]]

        return None

    def resolve_account(self, account_name_or_id: str) -> Record | None:
        """Resolve an account by ID or name."""
        return self.find_account_by_id(account_name_or_id) or self.find_account_by_name(
            account_name_or_id
        )

    def contacts_for(self, account_id: str) -> list[Record]:
        return [c for c in self.contacts if c["account_id"] == account_id]

    def opportunities_for(self, account_id: str) -> list[Record]:
        return [o for o in self.opportunities if o["account_id"] == account_id]

    def activities_for(self, account_id: str) -> list[Record]:
        return [a for a in self.activities if a["account_id"] == account_id]

    def tickets_for(self, account_id: str) -> list[Record]:
        return [t for t in self.support_tickets if t["account_id"] == account_id]

    def usage_for(self, account_id: str) -> list[Record]:
        return [u for u in self.product_usage if u["account_id"] == account_id]
