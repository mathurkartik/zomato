from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from src.phase1.transform import apply_cuisine_aliases, tokenize_cuisines
from src.phase2.catalog_loader import normalize_locality


class UserPreferences(BaseModel):
    locality: str = Field(min_length=1)
    budget_min_inr: int = Field(default=0, ge=0, le=5000)
    budget_max_inr: int = Field(ge=0, le=5000)
    cuisine: str = Field(min_length=1)
    min_rating: float = Field(ge=0.0, le=5.0)
    extras: list[str] = Field(default_factory=list)
    online_order: bool | None = Field(
        default=None,
        description="If True, only restaurants that offer online ordering.",
    )
    book_table: bool | None = Field(
        default=None,
        description="If True, only restaurants that offer table booking.",
    )
    persona: Literal["budget", "premium"] = Field(
        default="premium",
        description="budget: value-first shortlist order; premium: quality-first (weighted_score).",
    )

    @field_validator("locality")
    @classmethod
    def validate_locality(cls, v: str) -> str:
        # Canonical key for matching (catalog localities are lowercased at load time).
        return normalize_locality(v).strip().lower()

    @field_validator("cuisine")
    @classmethod
    def validate_cuisine(cls, v: str) -> str:
        # Accept values like "North Indian", "north indian", or comma-joined text.
        tokens = tokenize_cuisines(v)
        if not tokens:
            raise ValueError("cuisine must be non-empty")
        return apply_cuisine_aliases([tokens[0]])[0]

    @field_validator("extras")
    @classmethod
    def validate_extras(cls, values: list[str]) -> list[str]:
        out: list[str] = []
        for v in values:
            s = str(v).strip()
            if s:
                out.append(s)
        return out

    @model_validator(mode="after")
    def validate_budget_bounds(self) -> "UserPreferences":
        if self.budget_min_inr > self.budget_max_inr:
            raise ValueError("budget_min_inr must be <= budget_max_inr")
        return self
