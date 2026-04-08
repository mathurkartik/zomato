from __future__ import annotations

from pathlib import Path

import pandas as pd
from datasets import load_dataset

from src.config import AppConfig, load_config
from src.phase1.transform import (
    apply_cuisine_aliases,
    compute_weighted_score,
    derive_id,
    normalize_locality,
    normalize_name,
    parse_bool_yn,
    parse_cost_for_two,
    parse_rating,
    tokenize_cuisines,
)
from src.phase1.validate import (
    count_unmapped_alias_source_tokens,
    print_sample_json,
    validate_schema,
    verify_weighted_score_ordering,
)

COST_COL = "approx_cost(for two people)"


def _load_hf_dataframe() -> pd.DataFrame:
    ds = load_dataset("ManikaSaini/zomato-restaurant-recommendation", split="train")
    return ds.to_pandas()


def _has_name_location(df: pd.DataFrame) -> pd.Series:
    name_ok = df["name"].notna() & (df["name"].astype(str).str.strip() != "")
    loc_ok = df["location"].notna() & (df["location"].astype(str).str.strip() != "")
    return name_ok & loc_ok


def build_catalog(df: pd.DataFrame, cost_min_valid: int) -> tuple[pd.DataFrame, dict[str, int]]:
    stats: dict[str, int] = {}
    n_loaded = len(df)
    stats["loaded"] = n_loaded

    mask = _has_name_location(df)
    dropped_null = int((~mask).sum())
    stats["dropped_null_name_or_location"] = dropped_null
    df = df.loc[mask].copy()

    df["locality"] = df["location"].astype(str).map(normalize_locality)
    df["name_normalized"] = df["name"].astype(str).map(normalize_name)
    df["votes"] = pd.to_numeric(df["votes"], errors="coerce").fillna(0).astype(int)

    before_dedup = len(df)
    df = df.sort_values("votes", ascending=False)
    df = df.drop_duplicates(subset=["name_normalized", "locality"], keep="first")
    stats["dropped_duplicate_name_locality"] = before_dedup - len(df)

    df["rating"] = df["rate"].map(parse_rating)
    df["cost_for_two"] = df[COST_COL].map(parse_cost_for_two)

    low_cost_mask = df["cost_for_two"].notna() & (df["cost_for_two"] < cost_min_valid)
    dropped_cost = int(low_cost_mask.sum())
    stats["dropped_cost_below_min"] = dropped_cost
    df = df.loc[~low_cost_mask]

    df["cuisines"] = df["cuisines"].map(
        lambda raw: apply_cuisine_aliases(tokenize_cuisines(raw))
    )

    df["rest_type"] = df["rest_type"].fillna("").astype(str)
    df["online_order"] = df["online_order"].map(parse_bool_yn)
    df["book_table"] = df["book_table"].map(parse_bool_yn)

    df["weighted_score"] = compute_weighted_score(df["rating"], df["votes"])
    df["id"] = [
        derive_id(str(n), str(loc)) for n, loc in zip(df["name_normalized"], df["locality"], strict=True)
    ]

    out = df[
        [
            "id",
            "name",
            "name_normalized",
            "locality",
            "cuisines",
            "rating",
            "votes",
            "cost_for_two",
            "weighted_score",
            "rest_type",
            "online_order",
            "book_table",
        ]
    ].copy()
    out["cost_for_two"] = out["cost_for_two"].astype("Int64")

    stats["final_rows"] = len(out)
    return out, stats


def run_ingestion(config: AppConfig | None = None) -> Path:
    cfg = config or load_config()
    out_path: Path = cfg.data.processed_catalog
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print("Loading Hugging Face dataset ManikaSaini/zomato-restaurant-recommendation ...")
    raw = _load_hf_dataframe()
    print(f"Rows loaded from source: {len(raw)}")

    catalog, stats = build_catalog(raw, cost_min_valid=cfg.data.cost_min_valid)

    print("\n--- Ingestion stats ---")
    print(f"  Loaded:                          {stats['loaded']}")
    print(f"  Dropped (null name/location):    {stats['dropped_null_name_or_location']}")
    print(f"  Dropped (duplicate name+locality): {stats['dropped_duplicate_name_locality']}")
    print(f"  Dropped (cost < Rs.{cfg.data.cost_min_valid}):        {stats['dropped_cost_below_min']}")
    print(f"  Final row count:                 {stats['final_rows']}")
    if stats["final_rows"] < 40_000:
        print(
            "  Note: final count is below 40k because the raw dataset has many "
            "rows sharing the same (name, locality); dedup keeps the highest-vote row per pair."
        )

    validate_schema(catalog)
    catalog.to_parquet(out_path, index=False)
    print(f"\nWrote: {out_path}")

    print("\n--- Sample row (JSON) ---")
    print_sample_json(catalog, index=0)

    print("\n--- Verification ---")
    alias_leftovers = count_unmapped_alias_source_tokens(catalog)
    nonzero = {k: v for k, v in alias_leftovers.items() if v > 0}
    print(f"  Alias source tokens still present (expect empty): {nonzero or 'none'}")
    print(f"  Weighted score sanity: {verify_weighted_score_ordering(catalog)}")

    return out_path


def load_catalog_parquet(path: Path | None = None) -> pd.DataFrame:
    """Load processed catalog (for later phases)."""
    p = Path(path) if path is not None else load_config().data.processed_catalog
    return pd.read_parquet(p)
