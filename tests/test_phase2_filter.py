from __future__ import annotations

import pandas as pd

from src.config import FilterConfig
from src.phase2.filter import filter_restaurants
from src.phase2.preferences import UserPreferences


def _catalog_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "id": "a1",
                "name": "Alpha",
                "name_normalized": "alpha",
                "locality": "indiranagar",
                "cuisines": ["north indian", "chinese"],
                "rating": 4.2,
                "votes": 800,
                "cost_for_two": 700,
                "weighted_score": 28.1,
                "rest_type": "Casual Dining",
                "online_order": True,
                "book_table": False,
            },
            {
                "id": "a2",
                "name": "Alpha 2",
                "name_normalized": "alpha",
                "locality": "indiranagar",
                "cuisines": ["north indian"],
                "rating": 4.1,
                "votes": 600,
                "cost_for_two": 650,
                "weighted_score": 26.2,
                "rest_type": "Casual Dining",
                "online_order": True,
                "book_table": True,
            },
            {
                "id": "a3",
                "name": "Alpha 3",
                "name_normalized": "alpha",
                "locality": "indiranagar",
                "cuisines": ["north indian"],
                "rating": 4.0,
                "votes": 500,
                "cost_for_two": 680,
                "weighted_score": 24.8,
                "rest_type": "Quick Bites",
                "online_order": True,
                "book_table": False,
            },
            {
                "id": "b1",
                "name": "Beta",
                "name_normalized": "beta",
                "locality": "indiranagar",
                "cuisines": ["north indian"],
                "rating": 3.6,
                "votes": 120,
                "cost_for_two": 500,
                "weighted_score": 17.2,
                "rest_type": "Quick Bites",
                "online_order": True,
                "book_table": False,
            },
            {
                "id": "g1",
                "name": "Gamma",
                "name_normalized": "gamma",
                "locality": "indiranagar",
                "cuisines": ["north indian"],
                "rating": None,
                "votes": 0,
                "cost_for_two": 450,
                "weighted_score": 0.0,
                "rest_type": "Cafe",
                "online_order": False,
                "book_table": False,
            },
            {
                "id": "r1",
                "name": "R1",
                "name_normalized": "r1",
                "locality": "rajarajeshwari nagar",
                "cuisines": ["south indian"],
                "rating": 4.0,
                "votes": 80,
                "cost_for_two": 600,
                "weighted_score": 17.0,
                "rest_type": "Casual Dining",
                "online_order": True,
                "book_table": False,
            },
        ]
    )


def _cfg() -> FilterConfig:
    return FilterConfig(
        max_shortlist_candidates=40,
        chain_max_per_name=2,
        relax_rating_by=0.5,
        thin_locality_threshold=3,
    )


def test_no_locality_match() -> None:
    prefs = UserPreferences(
        locality="Unknown Place",
        budget_max_inr=800,
        cuisine="north indian",
        min_rating=3.5,
        extras=[],
    )
    result = filter_restaurants(_catalog_fixture(), prefs, _cfg())
    assert result.reason == "NO_LOCALITY_MATCH"
    assert result.items == []


def test_no_cuisine_match() -> None:
    prefs = UserPreferences(
        locality="Indiranagar",
        budget_max_inr=800,
        cuisine="italian",
        min_rating=3.0,
        extras=[],
    )
    result = filter_restaurants(_catalog_fixture(), prefs, _cfg())
    assert result.reason == "NO_CUISINE_MATCH"


def test_budget_too_low_has_min_cost() -> None:
    prefs = UserPreferences(
        locality="Rajarajeshwari Nagar",
        budget_max_inr=100,
        cuisine="south indian",
        min_rating=3.0,
        extras=[],
    )
    result = filter_restaurants(_catalog_fixture(), prefs, _cfg())
    assert result.reason == "BUDGET_TOO_LOW"
    assert result.meta.min_cost_in_locality == 600


def test_chain_cap_limits_same_name() -> None:
    prefs = UserPreferences(
        locality="Indiranagar",
        budget_max_inr=800,
        cuisine="north indian",
        min_rating=3.5,
        extras=[],
    )
    result = filter_restaurants(_catalog_fixture(), prefs, _cfg())
    assert result.reason == "OK"
    names = [x["name_normalized"] for x in result.items]
    assert names.count("alpha") <= 2


def test_relaxation_includes_unrated_when_needed() -> None:
    prefs = UserPreferences(
        locality="Indiranagar",
        budget_max_inr=800,
        cuisine="north indian",
        min_rating=4.5,
        extras=[],
    )
    result = filter_restaurants(_catalog_fixture(), prefs, _cfg())
    assert result.reason == "OK"
    assert result.meta.relaxed_rating is True
    assert any(pd.isna(item["rating"]) for item in result.items)


def test_thin_locality_after_relaxation() -> None:
    thin_df = _catalog_fixture().query("locality == 'rajarajeshwari nagar'").copy()
    prefs = UserPreferences(
        locality="Rajarajeshwari Nagar",
        budget_max_inr=1000,
        cuisine="south indian",
        min_rating=4.5,
        extras=[],
    )
    result = filter_restaurants(thin_df, prefs, _cfg())
    assert result.reason == "OK"
    assert len(result.items) >= 1
    assert result.meta.relaxed_rating is True
