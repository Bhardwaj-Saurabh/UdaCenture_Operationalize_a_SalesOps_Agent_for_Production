import json

import pytest

from salesops_agent.tools.crm import build_crm_tools
from salesops_agent.tools.email import build_email_tools
from salesops_agent.tools.registry import build_tools


@pytest.fixture
def crm_tools(store):
    return {built.name: built for built in build_crm_tools(store)}


def test_default_tools_exclude_restricted_data_and_sending(config, store):
    enabled = {built.name for built in build_tools(config, store)}
    assert enabled == {
        "lookup_account",
        "lookup_account_context",
        "list_open_opportunities",
        "summarize_pipeline",
        "draft_email",
    }


def test_unknown_configured_tool_raises(config, store):
    tools = config.tools.model_copy(update={"enabled": ("delete_everything",)})
    with pytest.raises(ValueError, match="delete_everything"):
        build_tools(config.model_copy(update={"tools": tools}), store)


def test_account_context_includes_related_records(crm_tools):
    context = crm_tools["lookup_account_context"].invoke({"account_name_or_id": "Acme Corp"})
    assert context["account"]["account_id"] == "A001"
    assert context["contacts"]
    assert all(c["account_id"] == "A001" for c in context["contacts"])


def test_ambiguous_lookup_returns_candidates_instead_of_guessing(crm_tools):
    result = crm_tools["lookup_account"].invoke({"account_name_or_id": "a"})
    assert "error" in result
    assert len(result["candidates"]) > 1


def test_open_pipeline_excludes_closed_deals(crm_tools, store):
    summary = crm_tools["summarize_pipeline"].invoke({})
    stage_totals = summary["by_stage"]
    assert stage_totals["Closed Won"]["is_open"] is False
    assert summary["open_pipeline"]["count"] == sum(
        entry["count"] for entry in stage_totals.values() if entry["is_open"]
    )
    assert summary["open_pipeline"]["count"] == len(crm_tools["list_open_opportunities"].invoke({}))


def test_stage_filter_ignores_case(crm_tools):
    results = crm_tools["list_open_opportunities"].invoke({"stage": "negotiation"})
    assert results
    assert {o["stage"] for o in results} == {"Negotiation"}


def test_draft_email_targets_the_primary_contact_and_does_not_send(store, tmp_path):
    outbox = tmp_path / "outbox.json"
    draft_email, _ = build_email_tools(store, outbox)
    draft = draft_email.invoke({"account_name_or_id": "Acme Corp", "purpose": "next steps"})
    assert draft["to"] == "omar.stone@acmecorp.example.com"
    assert draft["status"] == "drafted"
    assert not outbox.exists()


def test_send_email_appends_to_the_outbox(store, tmp_path):
    outbox = tmp_path / "nested" / "outbox.json"
    _, send_email = build_email_tools(store, outbox)
    for subject in ("First", "Second"):
        send_email.invoke({"to": "a@example.com", "subject": subject, "body": "Hi"})
    assert [m["subject"] for m in json.loads(outbox.read_text())] == ["First", "Second"]
