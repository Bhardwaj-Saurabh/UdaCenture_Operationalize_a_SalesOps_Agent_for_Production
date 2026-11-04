import pytest


def names(accounts):
    return [account["name"] for account in accounts]


def test_dataset_matches_the_documented_model(store):
    customers = {a["account_id"] for a in store.accounts if a["account_status"] == "customer"}
    closed_won = {o["account_id"] for o in store.opportunities if o["stage"] == "Closed Won"}
    assert len(store.accounts) == 109
    assert customers == closed_won
    assert len(customers) == 27


@pytest.mark.parametrize(
    "query",
    ["A003", "a003", "TechStart Inc", "TechStart Inc.", "techstart", "the TechStart account"],
)
def test_natural_inputs_resolve_to_the_same_account(store, query):
    assert names(store.find_accounts(query)) == [store.find_accounts("A003")[0]["name"]]


def test_small_typo_uses_the_fuzzy_fallback(store):
    assert names(store.find_accounts("Techstrat")) == names(store.find_accounts("techstart"))


def test_mid_word_fragment_does_not_match(store):
    assert store.find_accounts("start") == []


@pytest.mark.parametrize("query", ["", "Inc.", "No Such Company Anywhere"])
def test_unknown_inputs_return_nothing(store, query):
    assert store.find_accounts(query) == []


def test_ambiguous_fragment_returns_every_candidate(store):
    assert len(store.find_accounts("a")) > 1


def test_store_has_no_restricted_data(store):
    assert "Marcus Thorne" not in str(store)
    assert "CONFIDENTIAL_M_AND_A" not in str(store)
