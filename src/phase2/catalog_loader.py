from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import load_config
from src.phase1.transform import normalize_locality


def load_catalog(path: Path | None = None) -> pd.DataFrame:
    cfg = load_config()
    catalog_path = path if path is not None else cfg.data.processed_catalog
    df = pd.read_parquet(catalog_path)
    # Normalise locality in-place so all downstream filters see clean names.
    df["locality"] = df["locality"].dropna().map(normalize_locality).reindex(df.index)
    df["locality"] = df["locality"].astype(str).str.strip().str.lower()
    return df


def get_catalog_filters(catalog: pd.DataFrame) -> dict[str, list[str]]:
    localities = sorted(
        s for s in catalog["locality"].dropna().astype(str).unique().tolist() if s.strip()
    )
    cuisine_set: set[str] = set()
    for cuisines in catalog["cuisines"]:
        if cuisines is None or isinstance(cuisines, str):
            continue
        try:
            cuisine_set.update(str(c).strip() for c in cuisines if str(c).strip())
        except TypeError:
            continue
    return {
        "localities": localities,
        "cuisines": sorted(cuisine_set),
    }


def get_cuisines_for_locality(catalog: pd.DataFrame, locality: str) -> list[str]:
    """Return sorted list of cuisines available in the given (normalised) locality."""
    loc = locality.strip().lower()
    locality_df = catalog[catalog["locality"] == loc]
    cuisine_set: set[str] = set()
    for cuisines in locality_df["cuisines"]:
        if cuisines is None or isinstance(cuisines, str):
            continue
        try:
            cuisine_set.update(str(c).strip() for c in cuisines if str(c).strip())
        except TypeError:
            continue
    return sorted(cuisine_set)


def get_cuisine_counts_for_locality(
    catalog: pd.DataFrame, locality: str, *, limit: int = 12
) -> list[dict[str, int]]:
    """
    Return [{cuisine, count}, ...] sorted by count descending (restaurant rows per cuisine token).
    """
    loc = locality.strip().lower()
    locality_df = catalog[catalog["locality"] == loc]
    counts: dict[str, int] = {}
    for cuisines in locality_df["cuisines"]:
        if cuisines is None or isinstance(cuisines, str):
            continue
        try:
            for c in cuisines:
                t = str(c).strip().lower()
                if t:
                    counts[t] = counts.get(t, 0) + 1
        except TypeError:
            continue
    ranked = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    return [{"cuisine": c, "count": n} for c, n in ranked[:limit]]
