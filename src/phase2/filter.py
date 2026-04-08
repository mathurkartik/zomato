from __future__ import annotations

import time
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, Field

from src.config import FilterConfig, load_config
from src.phase2.preferences import UserPreferences
from src.utils import cuisine_tokens_equivalent as _cuisine_tokens_equivalent

ReasonCode = Literal[
    "OK",
    "NO_LOCALITY_MATCH",
    "NO_CUISINE_MATCH",
    "NO_RESULTS",
    "THIN_LOCALITY",
    "BUDGET_TOO_LOW",
]


class FilterMeta(BaseModel):
    reason: ReasonCode
    shortlist_size: int
    relaxed_rating: bool = False
    min_cost_in_locality: int | None = None
    elapsed_ms: int
    suggest_localities: list[str] = Field(
        default_factory=list,
        description="When THIN_LOCALITY: top localities with this cuisine to try next.",
    )


class FilterResult(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)
    reason: ReasonCode
    meta: FilterMeta


def _contains_cuisine(cuisines: Any, target: str) -> bool:
    if cuisines is None or isinstance(cuisines, str):
        return False
    if not isinstance(cuisines, (list, tuple, pd.Series)) and not hasattr(cuisines, "__iter__"):
        return False
    t = target.strip().lower()
    try:
        for c in cuisines:
            row_t = str(c).strip().lower()
            if _cuisine_tokens_equivalent(row_t, t):
                return True
    except TypeError:
        return False
    return False


def _suggest_localities_for_cuisine(
    catalog: pd.DataFrame,
    cuisine: str,
    exclude_locality: str,
    top_n: int = 3,
) -> list[str]:
    """Localities with the most restaurants serving `cuisine`, excluding current locality."""
    counts: dict[str, int] = {}
    for _, row in catalog.iterrows():
        loc = row.get("locality")
        if loc is None or pd.isna(loc):
            continue
        loc_s = str(loc).strip()
        if not loc_s or loc_s == exclude_locality:
            continue
        if _contains_cuisine(row.get("cuisines"), cuisine):
            counts[loc_s] = counts.get(loc_s, 0) + 1
    if not counts:
        return []
    ordered = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    return [loc for loc, _ in ordered[:top_n]]


def _apply_chain_cap(df: pd.DataFrame, max_per_name: int) -> pd.DataFrame:
    if df.empty:
        return df
    return (
        df.sort_values("weighted_score", ascending=False)
        .groupby("name_normalized", group_keys=False)
        .head(max_per_name)
    )


def _rank_and_cap(df: pd.DataFrame, cfg: FilterConfig) -> pd.DataFrame:
    if df.empty:
        return df
    capped = _apply_chain_cap(df, cfg.chain_max_per_name)
    return capped.sort_values("weighted_score", ascending=False).head(cfg.max_shortlist_candidates)


def _primary_pass(locality_cuisine_df: pd.DataFrame, prefs: UserPreferences, cfg: FilterConfig) -> pd.DataFrame:
    df = locality_cuisine_df.copy()
    df = df[df["rating"].notna() & (df["rating"] >= prefs.min_rating)]
    df = df[
        df["cost_for_two"].notna()
        & (df["cost_for_two"] >= prefs.budget_min_inr)
        & (df["cost_for_two"] <= prefs.budget_max_inr)
    ]
    # Online order filter
    if prefs.online_order is not None and "online_order" in df.columns:
        df = df[df["online_order"] == prefs.online_order]

    # Table booking filter
    if prefs.book_table is not None and "book_table" in df.columns:
        df = df[df["book_table"] == prefs.book_table]
    return _rank_and_cap(df, cfg)


def _relaxation_pass(locality_cuisine_df: pd.DataFrame, prefs: UserPreferences, cfg: FilterConfig) -> pd.DataFrame:
    relaxed_min = max(0.0, prefs.min_rating - cfg.relax_rating_by)
    df = locality_cuisine_df.copy()
    df = df[
        df["cost_for_two"].notna()
        & (df["cost_for_two"] >= prefs.budget_min_inr)
        & (df["cost_for_two"] <= prefs.budget_max_inr)
    ]
    # Online order filter
    if prefs.online_order is not None and "online_order" in df.columns:
        df = df[df["online_order"] == prefs.online_order]

    # Table booking filter
    if prefs.book_table is not None and "book_table" in df.columns:
        df = df[df["book_table"] == prefs.book_table]
    # Include unrated rows at the bottom in the relaxation pass.
    df = df[df["rating"].isna() | (df["rating"] >= relaxed_min)]
    # Keep unrated rows after rated rows with same score patterns.
    df = df.copy()
    df["__rating_is_null"] = df["rating"].isna().astype(int)
    df = _apply_chain_cap(df, cfg.chain_max_per_name)
    df = df.sort_values(["__rating_is_null", "weighted_score"], ascending=[True, False]).head(
        cfg.max_shortlist_candidates
    )
    return df.drop(columns=["__rating_is_null"])


def _last_resort_pass(locality_cuisine_df: pd.DataFrame, prefs: UserPreferences, cfg: FilterConfig) -> pd.DataFrame:
    """
    If rating floors still exclude every row, use budget-matched rows at any rating
    (e.g. sole 'juices' place at 3.4★ when user asked for 4.0★).
    If every row has missing cost_for_two, still return those rows (cost unknown — cannot enforce budget).
    """
    df = locality_cuisine_df.copy()
    priced = df[
        df["cost_for_two"].notna()
        & (df["cost_for_two"] >= prefs.budget_min_inr)
        & (df["cost_for_two"] <= prefs.budget_max_inr)
    ]
    if not priced.empty:
        use = priced
    else:
        unknown = df[df["cost_for_two"].isna()]
        if unknown.empty:
            return pd.DataFrame()
        use = unknown
    # Online order filter
    if prefs.online_order is not None and "online_order" in use.columns:
        use = use[use["online_order"] == prefs.online_order]

    # Table booking filter
    if prefs.book_table is not None and "book_table" in use.columns:
        use = use[use["book_table"] == prefs.book_table]
    if use.empty:
        return pd.DataFrame()
    use = use.copy()
    use["__rating_is_null"] = use["rating"].isna().astype(int)
    use = _apply_chain_cap(use, cfg.chain_max_per_name)
    use = use.sort_values(["__rating_is_null", "weighted_score"], ascending=[True, False]).head(
        cfg.max_shortlist_candidates
    )
    return use.drop(columns=["__rating_is_null"])


def filter_restaurants(
    catalog: pd.DataFrame, prefs: UserPreferences, config: FilterConfig | None = None
) -> FilterResult:
    started = time.perf_counter()
    cfg = config or load_config().filter

    if prefs.locality in {"all", "any", "*"}:
        locality_df = catalog
    else:
        locality_df = catalog[catalog["locality"] == prefs.locality]
    if locality_df.empty:
        elapsed = int((time.perf_counter() - started) * 1000)
        meta = FilterMeta(reason="NO_LOCALITY_MATCH", shortlist_size=0, elapsed_ms=elapsed)
        return FilterResult(items=[], reason="NO_LOCALITY_MATCH", meta=meta)

    min_cost = (
        pd.to_numeric(locality_df["cost_for_two"], errors="coerce")
        .dropna()
        .astype(int)
        .min()
        if not locality_df.empty
        else None
    )
    if min_cost is not None and prefs.budget_max_inr < int(min_cost):
        elapsed = int((time.perf_counter() - started) * 1000)
        meta = FilterMeta(
            reason="BUDGET_TOO_LOW",
            shortlist_size=0,
            min_cost_in_locality=int(min_cost),
            elapsed_ms=elapsed,
        )
        return FilterResult(items=[], reason="BUDGET_TOO_LOW", meta=meta)

    cuisine_df = locality_df[locality_df["cuisines"].map(lambda c: _contains_cuisine(c, prefs.cuisine))]
    if cuisine_df.empty:
        elapsed = int((time.perf_counter() - started) * 1000)
        meta = FilterMeta(reason="NO_CUISINE_MATCH", shortlist_size=0, elapsed_ms=elapsed)
        return FilterResult(items=[], reason="NO_CUISINE_MATCH", meta=meta)

    primary = _primary_pass(cuisine_df, prefs, cfg)
    if len(primary) >= 5:
        elapsed = int((time.perf_counter() - started) * 1000)
        meta = FilterMeta(
            reason="OK",
            shortlist_size=len(primary),
            relaxed_rating=False,
            elapsed_ms=elapsed,
        )
        return FilterResult(
            items=primary.to_dict(orient="records"),
            reason="OK",
            meta=meta,
        )

    relaxed = _relaxation_pass(cuisine_df, prefs, cfg)
    if relaxed.empty:
        relaxed = _last_resort_pass(cuisine_df, prefs, cfg)
    if relaxed.empty:
        elapsed = int((time.perf_counter() - started) * 1000)
        meta = FilterMeta(reason="NO_RESULTS", shortlist_size=0, relaxed_rating=True, elapsed_ms=elapsed)
        return FilterResult(items=[], reason="NO_RESULTS", meta=meta)

    # Few matches after relaxation: still return them (user picked cuisine from this locality’s list).
    # Offer alternate localities for the same cuisine as optional “try nearby” hints.
    suggestions: list[str] = []
    if len(relaxed) < cfg.thin_locality_threshold and prefs.locality not in {"all", "any", "*"}:
        suggestions = _suggest_localities_for_cuisine(
            catalog, prefs.cuisine, prefs.locality, top_n=3
        )

    elapsed = int((time.perf_counter() - started) * 1000)
    meta = FilterMeta(
        reason="OK",
        shortlist_size=len(relaxed),
        relaxed_rating=True,
        elapsed_ms=elapsed,
        suggest_localities=suggestions,
    )
    return FilterResult(items=relaxed.to_dict(orient="records"), reason="OK", meta=meta)
