"""
Tests for the three improvements applied to BiteAI:

  IMP-1  Locality name normalisation  (Koramangala block collapse)
  IMP-2  Cascaded cuisine endpoint    (GET /api/v1/filters/cuisines?locality=...)
  IMP-3  "No restaurants present" empty-state messages

Run without the live server:
    py -m pytest tests/test_improvements.py -v
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.phase2.catalog_loader import (
    get_catalog_filters,
    get_cuisines_for_locality,
    normalize_locality,
)
from src.phase4.app import app

# ──────────────────────────────────────────────────────────────────────────────
# Shared test client (loads real catalog via startup event)
# ──────────────────────────────────────────────────────────────────────────────
client = TestClient(app)


# ══════════════════════════════════════════════════════════════════════════════
# IMP-1 — Locality name normalisation
# ══════════════════════════════════════════════════════════════════════════════

class TestLocalityNormalisation:
    """normalize_locality() correctly strips numbered-block suffixes."""

    @pytest.mark.parametrize("raw, expected", [
        # Koramangala block variants
        ("Koramangala 1St Block",   "Koramangala"),
        ("Koramangala 2Nd Block",   "Koramangala"),
        ("Koramangala 3Rd Block",   "Koramangala"),
        ("Koramangala 4Th Block",   "Koramangala"),
        ("Koramangala 8Th Block",   "Koramangala"),
        # Lowercase / mixed case
        ("koramangala 5th block",   "koramangala"),
        ("KORAMANGALA 6TH BLOCK",   "KORAMANGALA"),
        # Leading/trailing whitespace
        ("  Koramangala 7Th Block ", "Koramangala"),
        # Non-block localities must be UNCHANGED
        ("Indiranagar",              "Indiranagar"),
        ("BTM Layout",               "BTM Layout"),
        ("Church Street",            "Church Street"),
        ("Whitefield",               "Whitefield"),
        ("JP Nagar",                 "JP Nagar"),
        # Stage-style locality — NOT a "Block", must be kept as-is
        ("BTM 2nd Stage",            "BTM 2nd Stage"),
        ("HSR Layout",               "HSR Layout"),
        # Already plain — no block suffix
        ("Btm",                      "Btm"),
    ])
    def test_normalize_locality_parametrized(self, raw: str, expected: str) -> None:
        assert normalize_locality(raw) == expected

    def test_catalog_load_normalises_koramangala(self) -> None:
        """After load, only 'Koramangala' appears — no '…NTh Block' variants."""
        with client:
            resp = client.get("/api/v1/filters")
        localities: list[str] = resp.json()["localities"]

        block_variants = [l for l in localities if "block" in l.lower()]
        assert block_variants == [], (
            f"Block-style localities should be collapsed, found: {block_variants}"
        )

    def test_koramangala_is_single_entry(self) -> None:
        """Koramangala appears exactly once in the /filters locality list."""
        with client:
            resp = client.get("/api/v1/filters")
        localities: list[str] = resp.json()["localities"]
        kora = [l for l in localities if l == "koramangala"]
        assert len(kora) == 1, f"Expected exactly 1 Koramangala entry, got: {kora}"

    def test_catalog_rows_normalised_in_dataframe(self) -> None:
        """Rows that were 'Koramangala NTh Block' now have locality='Koramangala'."""
        with TestClient(app) as c:
            catalog: pd.DataFrame = app.state.catalog
        kora_rows = catalog[catalog["locality"] == "koramangala"]
        block_rows = catalog[catalog["locality"].str.contains(r"\d+\w+\s+[Bb]lock", na=False, regex=True)]
        assert len(kora_rows) > 0,  "Expected merged Koramangala rows"
        assert len(block_rows) == 0, "Found un-normalised block-style rows in catalog"


# ══════════════════════════════════════════════════════════════════════════════
# IMP-2 — Cascaded cuisine endpoint
# ══════════════════════════════════════════════════════════════════════════════

class TestCascadedCuisineEndpoint:
    """GET /api/v1/filters/cuisines?locality=<name> returns locality-specific cuisines."""

    def test_endpoint_returns_200(self) -> None:
        with client:
            resp = client.get("/api/v1/filters/cuisines?locality=Church+Street")
        assert resp.status_code == 200

    def test_response_schema(self) -> None:
        with client:
            resp = client.get("/api/v1/filters/cuisines?locality=Indiranagar")
        data = resp.json()
        assert "locality" in data
        assert "cuisines" in data
        assert isinstance(data["cuisines"], list)

    def test_locality_field_echoed(self) -> None:
        with client:
            resp = client.get("/api/v1/filters/cuisines?locality=Church+Street")
        assert resp.json()["locality"] == "church street"

    def test_cuisines_non_empty_for_known_locality(self) -> None:
        with client:
            resp = client.get("/api/v1/filters/cuisines?locality=Indiranagar")
        cuisines = resp.json()["cuisines"]
        assert len(cuisines) > 0

    def test_cuisines_sorted_alphabetically(self) -> None:
        with client:
            resp = client.get("/api/v1/filters/cuisines?locality=Church+Street")
        cuisines = resp.json()["cuisines"]
        assert cuisines == sorted(cuisines), "Cuisines should be sorted A→Z"

    def test_only_locality_relevant_cuisines_returned(self) -> None:
        """Cuisines in response must actually exist in that locality's restaurants."""
        with TestClient(app) as c:
            resp = c.get("/api/v1/filters/cuisines?locality=Church+Street")
            catalog: pd.DataFrame = app.state.catalog
        returned = set(resp.json()["cuisines"])
        # Build the ground-truth set from the catalog
        loc_df = catalog[catalog["locality"] == "church street"]
        truth: set[str] = set()
        for row in loc_df["cuisines"]:
            if row is None or isinstance(row, str):
                continue
            try:
                truth.update(str(c).strip() for c in row if str(c).strip())
            except TypeError:
                pass
        assert returned == truth, (
            f"Extra cuisines: {returned - truth}\nMissing cuisines: {truth - returned}"
        )

    def test_unknown_locality_returns_empty_cuisines(self) -> None:
        with client:
            resp = client.get("/api/v1/filters/cuisines?locality=NonExistentPlace999")
        assert resp.status_code == 200
        assert resp.json()["cuisines"] == []

    def test_cuisines_subset_of_global_cuisines(self) -> None:
        """Locality cuisines must be a subset of the full catalog cuisines."""
        with client:
            global_resp = client.get("/api/v1/filters")
            local_resp  = client.get("/api/v1/filters/cuisines?locality=Indiranagar")
        global_cuisines = set(global_resp.json()["cuisines"])
        local_cuisines  = set(local_resp.json()["cuisines"])
        extra = local_cuisines - global_cuisines
        assert extra == set(), f"Local cuisines not in global list: {extra}"

    def test_koramangala_cuisines_after_normalisation(self) -> None:
        """After block collapse, querying 'Koramangala' must return cuisines (not empty)."""
        with client:
            resp = client.get("/api/v1/filters/cuisines?locality=Koramangala")
        assert resp.status_code == 200
        assert len(resp.json()["cuisines"]) > 0, \
            "Koramangala should have cuisines after locality normalisation"

    @pytest.mark.parametrize("locality", [
        "Church Street",
        "Indiranagar",
        "Koramangala",
        "Whitefield",
        "Btm",          # actual catalog name (Title-cased during ingestion)
        "Jp Nagar",     # actual catalog name
    ])
    def test_multiple_localities_all_return_cuisines(self, locality: str) -> None:
        with client:
            resp = client.get(f"/api/v1/filters/cuisines?locality={locality}")
        assert resp.status_code == 200
        assert len(resp.json()["cuisines"]) > 0, \
            f"{locality} returned no cuisines"


# ══════════════════════════════════════════════════════════════════════════════
# IMP-3 — "No restaurants present" empty-state reason messages
# ══════════════════════════════════════════════════════════════════════════════

class TestEmptyStateReasonCodes:
    """
    The API must return reason codes that the frontend maps to user-friendly
    'No restaurants present' messages.  We validate the reason codes here.
    """

    # ── helper catalog with controlled edge cases ──────────────────────────
    @staticmethod
    def _mini_catalog() -> pd.DataFrame:
        df = pd.DataFrame([
            {
                "id": "t1", "name": "TastyPlace", "name_normalized": "tastyplace",
                "locality": "testlocality", "cuisines": np.array(["north indian"]),
                "rating": 4.2, "votes": 300, "cost_for_two": 800,
                "weighted_score": 24.0, "rest_type": "Casual Dining",
                "online_order": True, "book_table": False,
            },
            {
                "id": "t2", "name": "SpicyHouse", "name_normalized": "spicyhouse",
                "locality": "testlocality", "cuisines": np.array(["south indian"]),
                "rating": 4.0, "votes": 250, "cost_for_two": 600,
                "weighted_score": 22.0, "rest_type": "Casual Dining",
                "online_order": True, "book_table": True,
            },
        ])
        # Use pandas Int64 (nullable) to match real parquet dtype
        df["cost_for_two"] = df["cost_for_two"].astype("Int64")
        return df

    def test_no_locality_match_reason_code(self) -> None:
        """Returns NO_LOCALITY_MATCH when locality not in catalog."""
        original = getattr(app.state, "catalog", None)
        try:
            app.state.catalog = self._mini_catalog()
            # Use module-level client so the injected catalog is visible
            resp = client.post("/api/v1/recommend", json={
                "locality": "GhostTown",
                "budget_max_inr": 1000,
                "cuisine": "north indian",
                "min_rating": 3.0,
                "extras": [],
            })
            data = resp.json()
            assert resp.status_code == 200
            assert data["items"] == []
            assert data["meta"]["reason"] == "NO_LOCALITY_MATCH"
        finally:
            if original is not None:
                app.state.catalog = original

    def test_no_cuisine_match_reason_code(self) -> None:
        """Returns NO_CUISINE_MATCH when cuisine absent from locality."""
        original = getattr(app.state, "catalog", None)
        try:
            app.state.catalog = self._mini_catalog()
            resp = client.post("/api/v1/recommend", json={
                "locality": "testlocality",
                "budget_max_inr": 1000,
                "cuisine": "japanese",          # not in mini catalog
                "min_rating": 3.0,
                "extras": [],
            })
            data = resp.json()
            assert resp.status_code == 200
            assert data["items"] == []
            assert data["meta"]["reason"] == "NO_CUISINE_MATCH"
        finally:
            if original is not None:
                app.state.catalog = original

    def test_budget_too_low_reason_code_and_min_cost(self) -> None:
        """Returns BUDGET_TOO_LOW with min_cost_in_locality when budget is under cheapest."""
        original = getattr(app.state, "catalog", None)
        try:
            app.state.catalog = self._mini_catalog()
            resp = client.post("/api/v1/recommend", json={
                "locality": "testlocality",
                "budget_max_inr": 100,           # below 600 (cheapest)
                "cuisine": "north indian",
                "min_rating": 3.0,
                "extras": [],
            })
            data = resp.json()
            assert resp.status_code == 200
            assert data["items"] == []
            meta = data["meta"]
            assert meta["reason"] == "BUDGET_TOO_LOW"
            assert meta["min_cost_in_locality"] == 600  # cheapest in mini catalog
        finally:
            if original is not None:
                app.state.catalog = original

    def test_empty_result_is_200_never_404_or_500(self) -> None:
        """An unfound locality must return 200, not a 4xx or 5xx error."""
        with client:
            resp = client.post("/api/v1/recommend", json={
                "locality": "SomePlaceThatDoesNotExist",
                "budget_max_inr": 1000,
                "cuisine": "north indian",
                "min_rating": 3.0,
                "extras": [],
            })
        assert resp.status_code == 200
        assert "items" in resp.json()
        assert resp.json()["items"] == []

    def test_all_reason_codes_in_meta(self) -> None:
        """meta.reason must always be present in empty responses."""
        with client:
            resp = client.post("/api/v1/recommend", json={
                "locality": "SomePlaceThatDoesNotExist",
                "budget_max_inr": 1000,
                "cuisine": "north indian",
                "min_rating": 3.0,
                "extras": [],
            })
        meta = resp.json()["meta"]
        assert "reason" in meta
        assert meta["reason"] in {
            "NO_LOCALITY_MATCH", "NO_CUISINE_MATCH",
            "BUDGET_TOO_LOW", "THIN_LOCALITY", "NO_RESULTS", None
        }

    def test_llm_not_called_on_empty_result(self) -> None:
        """llm_used must be False when no restaurants matched."""
        with client:
            resp = client.post("/api/v1/recommend", json={
                "locality": "SomePlaceThatDoesNotExist",
                "budget_max_inr": 1000,
                "cuisine": "north indian",
                "min_rating": 3.0,
                "extras": [],
            })
        assert resp.json()["meta"]["llm_used"] is False


# ══════════════════════════════════════════════════════════════════════════════
# Helper function unit tests (get_catalog_filters, get_cuisines_for_locality)
# ══════════════════════════════════════════════════════════════════════════════

class TestCatalogLoaderHelpers:
    """Unit tests for helper functions in catalog_loader.py."""

    @staticmethod
    def _sample_df() -> pd.DataFrame:
        return pd.DataFrame([
            {"locality": "indiranagar", "cuisines": np.array(["north indian", "chinese"])},
            {"locality": "indiranagar", "cuisines": np.array(["italian"])},
            {"locality": "church street", "cuisines": np.array(["cafe", "continental"])},
            {"locality": "church street", "cuisines": None},
        ])

    def test_get_catalog_filters_returns_sorted_localities(self) -> None:
        df = self._sample_df()
        result = get_catalog_filters(df)
        assert result["localities"] == sorted(result["localities"])

    def test_get_catalog_filters_returns_sorted_cuisines(self) -> None:
        df = self._sample_df()
        result = get_catalog_filters(df)
        assert result["cuisines"] == sorted(result["cuisines"])

    def test_get_cuisines_for_locality_correct_set(self) -> None:
        df = self._sample_df()
        cuisines = get_cuisines_for_locality(df, "indiranagar")
        assert set(cuisines) == {"north indian", "chinese", "italian"}

    def test_get_cuisines_for_locality_sorted(self) -> None:
        df = self._sample_df()
        cuisines = get_cuisines_for_locality(df, "indiranagar")
        assert cuisines == sorted(cuisines)

    def test_get_cuisines_for_locality_ignores_none_rows(self) -> None:
        df = self._sample_df()
        cuisines = get_cuisines_for_locality(df, "church street")
        # None cuisines row should be skipped, not crash
        assert set(cuisines) == {"cafe", "continental"}

    def test_get_cuisines_for_unknown_locality_returns_empty(self) -> None:
        df = self._sample_df()
        cuisines = get_cuisines_for_locality(df, "NowhereVille")
        assert cuisines == []
