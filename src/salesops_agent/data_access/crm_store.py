"""In-memory access to the approved CRM data files."""

import difflib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

Record = dict[str, Any]

CLOSED_STAGES = {"Closed Won", "Closed Lost"}
FUZZY_MATCH_CUTOFF = 0.82


def normalize_name(value: str) -> str:
    """Lowercase a name and drop punctuation and legal suffixes such as "Inc."."""
    value = re.sub(r"[^a-z0-9\s]", " ", value.lower())
    value = re.sub(r"\b(incorporated|inc|corp|corporation|ltd|limited|llc|co|company)\b", "", value)
    return re.sub(r"\s+", " ", value).strip()


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

    def find_accounts(self, name_or_id: str) -> list[Record]:
        """Return accounts matching an ID or name, from the strictest match type that hits.

        More than one result means the input is ambiguous, so callers should ask
        which account was meant instead of picking one.
        """
        account_id = name_or_id.strip().lower()
        by_id = [a for a in self.accounts if a["account_id"].lower() == account_id]
        if by_id:
            return by_id

        query = normalize_name(name_or_id)
        if not query:
            return []

        names = {normalize_name(a["name"]): a for a in self.accounts}
        if query in names:
            return [names[query]]

        partial = [
            account
            for name, account in names.items()
            if re.search(rf"\b{re.escape(query)}", name)
            or re.search(rf"\b{re.escape(name)}\b", query)
        ]
        if partial:
            return partial

        close = difflib.get_close_matches(query, names, n=1, cutoff=FUZZY_MATCH_CUTOFF)
        return [names[match] for match in close]

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
