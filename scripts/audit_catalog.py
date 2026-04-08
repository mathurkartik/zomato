#!/usr/bin/env python3
"""
Audit the processed restaurant catalog for presentation / demo readiness.

Run from repo root:
    py scripts/audit_catalog.py
    py scripts/audit_catalog.py --deep

Exit code 1 only on integrity failures (e.g. duplicate ids). Cost/rating caveats are warnings.
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from src.phase2.catalog_loader import load_catalog
from src.phase2.filter import filter_restaurants
from src.phase2.preferences import UserPreferences


def _long_table(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for _, row in df.iterrows():
        loc = row.get("locality")
        if loc is None or (isinstance(loc, float) and pd.isna(loc)):
            continue
        loc_s = str(loc).strip().lower()
        if not loc_s:
            continue
        cuisines = row.get("cuisines")
        cost = row.get("cost_for_two")
        if cuisines is None or isinstance(cuisines, str):
            continue
        try:
            for c in cuisines:
                t = str(c).strip().lower()
                if t:
                    rows.append({"locality": loc_s, "token": t, "cost": cost})
        except TypeError:
            continue
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deep", action="store_true")
    ap.add_argument("--sample", type=int, default=60)
    args = ap.parse_args()

    df = load_catalog()
    n = len(df)
    ids = df["id"].astype(str)
    dup = ids[ids.duplicated()].unique().tolist()

    localities = df["locality"].dropna().astype(str).nunique()
    empty_loc = int((df["locality"].astype(str).str.strip() == "").sum())

    print("=== BiteAI catalog audit ===")
    print(f"Rows: {n:,} | Localities: {localities}")
    print(f"Duplicate ids: {len(dup)}")
    if dup:
        print(f"  ERROR sample: {dup[:10]}")
    print(f"Empty locality strings: {empty_loc}")

    code = 0
    if dup or empty_loc:
        code = 1

    long = _long_table(df)
    long["cost_num"] = pd.to_numeric(long["cost"], errors="coerce")
    budget = 5000

    agg = long.groupby(["locality", "token"], as_index=False).agg(
        min_cost=("cost_num", "min"),
        n=("cost_num", "count"),
    )

    missing_cost = agg["min_cost"].isna()
    pricey = agg["min_cost"].notna() & (agg["min_cost"] > budget)

    print(f"Unique (locality, cuisine-token) pairs: {len(agg):,}")
    print()
    print(f"WARN: pairs where all listings lack cost_for_two (min is null): {int(missing_cost.sum())}")
    for _, r in agg[missing_cost].head(15).iterrows():
        print(f"  {r['locality']} | {r['token']}")
    if int(missing_cost.sum()) > 15:
        print(f"  ... ({int(missing_cost.sum()) - 15} more)")

    print()
    print(
        f"WARN: pairs where cheapest cost_for_two exceeds Rs.{budget} (user needs higher budget): "
        f"{int(pricey.sum())}"
    )
    for _, r in agg[pricey].head(15).iterrows():
        print(f"  {r['locality']} | {r['token']} | min Rs.{int(r['min_cost'])}")
    if int(pricey.sum()) > 15:
        print(f"  ... ({int(pricey.sum()) - 15} more)")

    print()
    print(
        "Note: Filter includes last-resort paths (rating / unknown cost) so demos still return "
        "results when possible; min-cost warnings flag dataset gaps, not app bugs."
    )

    pairs = list(zip(agg["locality"].tolist(), agg["token"].tolist()))
    if args.deep and pairs:
        print()
        print(f"--deep: filter_restaurants on {min(args.sample, len(pairs))} random pairs ...")
        rng = random.Random(42)
        sample = rng.sample(pairs, min(args.sample, len(pairs)))
        failed = 0
        for loc, cuisine in sample:
            prefs = UserPreferences(
                locality=loc,
                cuisine=cuisine,
                budget_max_inr=budget,
                min_rating=4.0,
                extras=[],
                persona="premium",
            )
            r = filter_restaurants(df, prefs)
            if r.reason == "NO_RESULTS" or (r.reason == "OK" and not r.items):
                print(f"  FAIL {loc} | {cuisine} -> {r.reason} items={len(r.items)}")
                failed += 1
        if failed:
            print(f"Deep check: {failed} unexpected empty shortlists")
            code = 1
        else:
            print("Deep check: OK (sampled pairs produced a shortlist or expected BUDGET_TOO_LOW).")

    return code


if __name__ == "__main__":
    raise SystemExit(main())
