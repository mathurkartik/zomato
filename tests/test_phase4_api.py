import pytest
from fastapi.testclient import TestClient

from src.phase4.app import app

client = TestClient(app)

def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "catalog_rows" in data
        assert data["catalog_rows"] > 0

def test_filters_endpoint():
    with TestClient(app) as client:
        response = client.get("/api/v1/filters")
        assert response.status_code == 200
        data = response.json()
        
        # Check standard fields exist
        assert "localities" in data
        assert "cuisines" in data
        assert "rating_options" in data
        assert "extras_tags" in data
        assert "budget_range" in data
        
        # Ensure localities and cuisines are populated from catalog
        assert len(data["localities"]) > 0
        assert len(data["cuisines"]) > 0

def test_recommend_budget_too_low():
    import pandas as pd
    with TestClient(app) as client:
        # Override the global state catalog temporarily for this test
        original_catalog = getattr(app.state, "catalog", None)
        try:
            app.state.catalog = pd.DataFrame([
                {
                    "id": "1",
                    "name": "Expensive Fine Dining",
                    "name_normalized": "expensive fine dining",
                    "locality": "richarea",
                    "cuisines": ["north indian"],
                    "rating": 4.5,
                    "votes": 100,
                    "cost_for_two": 3000,
                    "weighted_score": 10.0,
                    "rest_type": "Fine Dining",
                    "online_order": False,
                    "book_table": True,
                }
            ])
            payload = {
                "locality": "Richarea",
                "budget_max_inr": 100, # Valid input, but definitely below 3000
                "cuisine": "north indian",
                "min_rating": 3.0,
                "extras": []
            }
            
            response = client.post("/api/v1/recommend", json=payload)
            
            # Ensure empty result returns 200, never 404 or 500
            assert response.status_code == 200
            data = response.json()
            
            # Check standard empty response structure
            assert data["items"] == []
            assert "summary" in data
            
            meta = data["meta"]
            assert meta["reason"] == "BUDGET_TOO_LOW"
            assert meta["min_cost_in_locality"] == 3000
            assert meta["shortlist_size"] == 0
            assert meta["llm_used"] is False
        finally:
            if original_catalog is not None:
                app.state.catalog = original_catalog

def test_recommend_invalid_body():
    with TestClient(app) as client:
        payload = {
            "locality": "Indiranagar",
            # Missing budget_max_inr and cuisine
        }
        response = client.post("/api/v1/recommend", json=payload)
        
        # Invalid body returns 422 with field-level errors.
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert len(errors) > 0

@pytest.mark.integration
def test_recommend_success_case():
    with TestClient(app) as client:
        # Use known values from the Bangalore dataset
        payload = {
            "locality": "Indiranagar",
            "budget_max_inr": 2000,
            "cuisine": "north indian",
            "min_rating": 4.0,
            "extras": ["rooftop"]
        }
        response = client.post("/api/v1/recommend", json=payload)
        data = response.json()
        assert response.status_code == 200, f"Failed with {data}"
        
        assert "items" in data, f"Missing items in: {data}"
        assert len(data["items"]) > 0, f"Expected items, got: {data}"
        
        # Test meta
        meta = data["meta"]
        assert meta["shortlist_size"] > 0
        # Live Groq may rate-limit (HTTP 429); fallback still returns items with llm_used False.
        assert isinstance(meta["llm_used"], bool)
        assert "latency_ms" in meta
        
        # First item checks
        first_item = data["items"][0]
        assert "id" in first_item
        assert first_item["locality"] == "indiranagar"
