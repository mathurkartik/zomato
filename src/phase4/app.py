from __future__ import annotations

from typing import Any

import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.phase2.catalog_loader import (
    get_catalog_filters,
    get_cuisine_counts_for_locality,
    get_cuisines_for_locality,
    load_catalog,
)
from src.phase3.orchestrator import recommend
from src.phase4.schemas import (
    CuisineCountItem,
    FilterCountsRequest,
    FilterCountsResponse,
    FiltersResponse,
    LocalityCuisineSummaryResponse,
    LocalityCuisinesResponse,
    RecommendationMeta,
    RecommendationRequest,
    RecommendationResponse,
)
from src.utils import cuisine_tokens_equivalent


def _contains_cuisine(cuisines: Any, target: str) -> bool:
    if cuisines is None or isinstance(cuisines, str):
        return False
    if not isinstance(cuisines, (list, tuple, pd.Series)) and not hasattr(cuisines, "__iter__"):
        return False
    t = target.strip().lower()
    try:
        for c in cuisines:
            row_t = str(c).strip().lower()
            if cuisine_tokens_equivalent(row_t, t):
                return True
    except TypeError:
        return False
    return False


def create_app() -> FastAPI:
    app = FastAPI(title="Zomato Restaurant Recommender", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    state: dict[str, object] = {}

    @app.on_event("startup")
    def _startup() -> None:
        try:
            app.state.catalog = load_catalog()
            state["catalog_ok"] = True
        except Exception as e:  # noqa: BLE001
            app.state.catalog = None
            state["catalog_ok"] = False
            app.state.catalog_error = str(e)

        # Optional: validate GROQ_API_KEY exists (without crashing).
        try:
            from src.phase3.groq_client import get_groq_api_key

            _ = get_groq_api_key()
            state["groq_key_ok"] = True
        except Exception as e:  # noqa: BLE001
            state["groq_key_ok"] = False
            state["groq_key_error"] = str(e)
            print(f"[api] groq key missing or invalid: {e}")

    @app.get("/health")
    def health() -> dict[str, object]:
        if getattr(app.state, "catalog", None) is None:
            return {"status": "degraded"}
        return {"status": "ok", "catalog_rows": int(len(app.state.catalog))}

    @app.get("/api/v1/filters", response_model=FiltersResponse)
    def filters() -> FiltersResponse:
        catalog = getattr(app.state, "catalog", None)
        if catalog is None:
            return FiltersResponse(localities=[], cuisines=[])
        f = get_catalog_filters(catalog)
        online_count = int(catalog["online_order"].sum()) if "online_order" in catalog.columns else 0
        book_count = int(catalog["book_table"].sum()) if "book_table" in catalog.columns else 0
        return FiltersResponse(
            localities=f["localities"],
            cuisines=f["cuisines"],
            online_order_count=online_count,
            book_table_count=book_count,
        )

    @app.get("/api/v1/filters/cuisines", response_model=LocalityCuisinesResponse)
    def cuisines_for_locality(locality: str) -> LocalityCuisinesResponse:
        """Return cuisines available in a specific locality (cascaded dropdown)."""
        catalog = getattr(app.state, "catalog", None)
        loc = locality.strip().lower()
        if catalog is None:
            return LocalityCuisinesResponse(locality=loc, cuisines=[])
        cuisines = get_cuisines_for_locality(catalog, loc)
        return LocalityCuisinesResponse(locality=loc, cuisines=cuisines)

    @app.get("/api/v1/filters/cuisines/summary", response_model=LocalityCuisineSummaryResponse)
    def cuisine_summary(locality: str, limit: int = 12) -> LocalityCuisineSummaryResponse:
        """Cuisine counts in a locality (heatmap / informed choice)."""
        catalog = getattr(app.state, "catalog", None)
        loc = locality.strip().lower()
        if catalog is None:
            return LocalityCuisineSummaryResponse(locality=loc, counts=[])
        rows = get_cuisine_counts_for_locality(catalog, loc, limit=limit)
        return LocalityCuisineSummaryResponse(
            locality=loc,
            counts=[CuisineCountItem(**r) for r in rows],
        )

    @app.post("/api/v1/filters/counts", response_model=FilterCountsResponse)
    def filter_counts(body: FilterCountsRequest) -> FilterCountsResponse:
        catalog = getattr(app.state, "catalog", None)
        if catalog is None:
            return FilterCountsResponse(online_order_count=0, book_table_count=0)

        df = catalog
        loc = (body.locality or "").strip().lower()
        if loc and loc not in {"all", "any", "*"} and "locality" in df.columns:
            df = df[df["locality"] == loc]
        cuisine = (body.cuisine or "").strip()
        if cuisine and "cuisines" in df.columns:
            df = df[df["cuisines"].map(lambda c: _contains_cuisine(c, cuisine))]
        if "cost_for_two" in df.columns:
            df = df[
                df["cost_for_two"].notna()
                & (df["cost_for_two"] >= int(body.budget_min_inr))
                & (df["cost_for_two"] <= int(body.budget_max_inr))
            ]
        if "rating" in df.columns:
            df = df[df["rating"].notna() & (df["rating"] >= float(body.min_rating))]

        online_df = df
        if body.book_table is not None and "book_table" in online_df.columns:
            online_df = online_df[online_df["book_table"] == body.book_table]
        online_count = (
            int((online_df["online_order"] == True).sum())  # noqa: E712
            if "online_order" in online_df.columns
            else 0
        )

        book_df = df
        if body.online_order is not None and "online_order" in book_df.columns:
            book_df = book_df[book_df["online_order"] == body.online_order]
        book_count = (
            int((book_df["book_table"] == True).sum())  # noqa: E712
            if "book_table" in book_df.columns
            else 0
        )

        return FilterCountsResponse(
            online_order_count=online_count,
            book_table_count=book_count,
        )

    @app.post("/api/v1/recommend", response_model=RecommendationResponse)
    def recommend_endpoint(body: RecommendationRequest) -> RecommendationResponse:
        catalog = getattr(app.state, "catalog", None)
        if catalog is None:
            return RecommendationResponse(
                summary="No restaurants matched your filters.",
                items=[],
                rejected=[],
                meta=RecommendationMeta(
                    shortlist_size=0,
                    model=None,
                    prompt_version=None,
                    relaxed_rating=False,
                    cache_hit=False,
                    llm_used=False,
                    fallback_used=False,
                    latency_ms=0,
                    tokens_used=None,
                    reason=None,
                    min_cost_in_locality=None,
                    error="catalog_not_loaded",
                ),
            )
        prefs = body
        return recommend(prefs=prefs, catalog=catalog)

    @app.get("/")
    def index() -> JSONResponse:
        return JSONResponse(
            {
                "service": "Zomato Restaurant Recommender API",
                "docs": "/docs",
                "health": "/health",
                "frontend": "Run separately: cd frontend && npm run dev",
            }
        )

    return app


app = create_app()
