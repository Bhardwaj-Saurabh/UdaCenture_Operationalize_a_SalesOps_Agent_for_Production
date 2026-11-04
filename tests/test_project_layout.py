from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CRM_FILES = {
    "accounts.json",
    "activities.json",
    "contacts.json",
    "opportunities.json",
    "product_usage.json",
    "support_tickets.json",
}


@pytest.mark.parametrize("folder", ["src", "data", "logs", "traces", "reports"])
def test_required_folder_exists(folder):
    assert (ROOT / folder).is_dir()


def test_restricted_data_is_kept_out_of_the_crm_folder():
    assert {path.name for path in (ROOT / "data" / "crm").glob("*.json")} == CRM_FILES
