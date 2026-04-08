from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from src.phase2.filter import ReasonCode
from src.phase2.preferences import UserPreferences


class RecommendationRequest(UserPreferences):
    """API request uses the same validation as Phase 2 preferences."""

    # Free-text user intent from the frontend chat box.
    # Kept as `specific_cravings` to match the existing frontend payload.
    specific_cravings: str | None = None

    # Optional override: frontend can send a detected/selected scenario.
    scenario: str | None = None


class RecommendationItem(BaseModel):
    id: str
    rank: int
    name: str
    locality: str
    cuisines: list[str]
    rating: float | None
    cost_for_two: int | None
    cost_display: str | None
    rest_type: str | None
    weighted_score: float | None = None
    votes: int | None = None
    explanation: str


class RejectedItem(BaseModel):
    id: str
    name: str
    rating: float | None
    cost_for_two: int | None
    cost_display: str | None
    rejection_reason: str


class RecommendationMeta(BaseModel):
    shortlist_size: int
    model: str | None = None
    prompt_version: str | None = None
    relaxed_rating: bool = False
    cache_hit: bool = False
    llm_used: bool = False
    fallback_used: bool = False
    latency_ms: int = 0
    tokens_used: int | None = None
    reason: ReasonCode | None = None
    min_cost_in_locality: int | None = None
    error: str | None = None
    persona: Literal["budget", "premium"] | None = None
    suggest_localities: list[str] = Field(default_factory=list)


class RecommendationResponse(BaseModel):
    summary: str
    items: list[RecommendationItem] = Field(default_factory=list)
    rejected: list[RejectedItem] = Field(default_factory=list)
    meta: RecommendationMeta


class FiltersResponse(BaseModel):
    localities: list[str]
    cuisines: list[str]
    rating_options: list[float] = [3.0, 3.5, 4.0, 4.5]
    online_order_count: int = 0
    book_table_count: int = 0
    extras_tags: list[str] = [
        "veg",
        "family",
        "quick_service",
        "rooftop",
        "romantic",
        "outdoor",
    ]
    budget_range: dict[str, int] = Field(default_factory=lambda: {"min": 100, "max": 5000, "step": 50})


class FilterCountsRequest(BaseModel):
    locality: str | None = None
    cuisine: str | None = None
    budget_min_inr: int = 0
    budget_max_inr: int = 5000
    min_rating: float = 0.0
    online_order: bool | None = None
    book_table: bool | None = None


class FilterCountsResponse(BaseModel):
    online_order_count: int = 0
    book_table_count: int = 0


class LocalityCuisinesResponse(BaseModel):
    """Cuisines available in a specific locality (for cascaded dropdown)."""
    locality: str
    cuisines: list[str]


class CuisineCountItem(BaseModel):
    cuisine: str
    count: int


class LocalityCuisineSummaryResponse(BaseModel):
    """Cuisine distribution in a locality (heatmap / informed choice)."""
    locality: str
    counts: list[CuisineCountItem] = Field(default_factory=list)
