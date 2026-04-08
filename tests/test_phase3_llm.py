import pytest
import pandas as pd
from typing import Any

from src.phase2.preferences import UserPreferences
from src.phase3.orchestrator import recommend, _cache


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
                "id": "b1",
                "name": "Beta",
                "name_normalized": "beta",
                "locality": "indiranagar",
                "cuisines": ["north indian"],
                "rating": 4.6,
                "votes": 1200,
                "cost_for_two": 800,
                "weighted_score": 35.1,
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
                "rating": 4.8,
                "votes": 1500,
                "cost_for_two": 900,
                "weighted_score": 40.0,
                "rest_type": "Fine Dining",
                "online_order": False,
                "book_table": True,
            },
            {
                "id": "x1",
                "name": "Extra",
                "name_normalized": "extra",
                "locality": "indiranagar",
                "cuisines": ["north indian"],
                "rating": 4.7,
                "votes": 1300,
                "cost_for_two": 750,
                "weighted_score": 38.0,
                "rest_type": "Casual Dining",
                "online_order": True,
                "book_table": True,
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

def setup_function():
    _cache.clear()

@pytest.mark.integration
def test_llm_recommend_basic() -> None:
    prefs = UserPreferences(
        locality="Indiranagar",
        budget_max_inr=1500,
        cuisine="north indian",
        min_rating=4.0,
        extras=["romantic"],
    )
    catalog = _catalog_fixture()
    
    response = recommend(prefs=prefs, catalog=catalog)
    
    # 1. Shortlist has multiple entries for north indian in indiranagar
    assert response.meta.shortlist_size > 0
    # 2. LLM should be used when Groq is available (rate limits make this flaky)
    if not response.meta.llm_used:
        pytest.skip("Groq rate-limited or unavailable; cannot assert LLM path")
    assert response.meta.llm_used is True
    # 3. Cache hasn't been hit yet
    assert response.meta.cache_hit is False
    # 4. Valid results returned
    assert len(response.items) > 0
    
    # Check that all returned IDs are actually in the catalog shortlist
    valid_ids = set(row["id"] for _, row in catalog.iterrows())
    for item in response.items:
        assert item.id in valid_ids

@pytest.mark.integration
def test_llm_cache() -> None:
    prefs = UserPreferences(
        locality="Indiranagar",
        budget_max_inr=1500,
        cuisine="north indian",
        min_rating=4.0,
        extras=["rooftop"],
    )
    catalog = _catalog_fixture()
    
    # First request
    response1 = recommend(prefs=prefs, catalog=catalog)
    if not response1.meta.llm_used:
        pytest.skip("Groq rate-limited or unavailable; cannot test LLM response cache")
    assert response1.meta.llm_used is True
    assert response1.meta.cache_hit is False
    first_latency = response1.meta.latency_ms
    
    # Second identical request
    response2 = recommend(prefs=prefs, catalog=catalog)
    # The cache should be hit!
    assert response2.meta.cache_hit is True
    # Should probably be faster (though we just check flag mostly)
    
    # Items should be identical
    assert len(response1.items) == len(response2.items)
    for i1, i2 in zip(response1.items, response2.items):
        assert i1.id == i2.id

@pytest.mark.integration
def test_llm_empty_shortlist() -> None:
    prefs = UserPreferences(
        locality="Unknown place",
        budget_max_inr=1500,
        cuisine="north indian",
        min_rating=4.0,
        extras=[],
    )
    catalog = _catalog_fixture()
    
    # First request
    response = recommend(prefs=prefs, catalog=catalog)
    assert response.meta.llm_used is False
    assert len(response.items) == 0
