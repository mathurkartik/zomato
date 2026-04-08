#!/usr/bin/env python3
"""
Small smoke tests for Phase 3 (Groq) integration.

Goals:
  - Prove `.env` loading + API key detection.
  - Verify the system never fails: if Groq errors, we still return a deterministic fallback.
  - Confirm caching works (second call is a cache hit).
"""

from __future__ import annotations

import os
import sys


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _print_response(tag: str, resp: object) -> None:
    # Avoid dumping huge objects.
    meta = getattr(resp, "meta", None)
    items = getattr(resp, "items", None) or []
    print(f"\n[{tag}]")
    if meta is not None:
        print(
            "  meta:",
            f"cache_hit={getattr(meta,'cache_hit',None)}",
            f"llm_used={getattr(meta,'llm_used',None)}",
            f"fallback_used={getattr(meta,'fallback_used',None)}",
            f"latency_ms={getattr(meta,'latency_ms',None)}",
            f"tokens_used={getattr(meta,'tokens_used',None)}",
            f"reason={getattr(meta,'reason',None)}",
            f"error={getattr(meta,'error',None)}",
        )
    if items:
        top = items[0]
        print(f"  top_item: id={top.id} name={top.name} rating={top.rating} cost={top.cost_for_two}")
    else:
        print("  items: []")


def main() -> int:
    from src.phase2.catalog_loader import load_catalog
    from src.phase2.preferences import UserPreferences
    from src.phase3.orchestrator import recommend

    catalog = load_catalog()

    tests = [
        (
            "phase3_call_1",
            UserPreferences(locality="Indiranagar", budget_max_inr=2000, cuisine="north indian", min_rating=3.5, extras=["family"]),
        ),
        (
            "phase3_call_2_cache_hit",
            UserPreferences(locality="Indiranagar", budget_max_inr=2000, cuisine="north indian", min_rating=3.5, extras=["family"]),
        ),
        (
            "phase2_reason_no_locality",
            UserPreferences(locality="Unknown Place", budget_max_inr=800, cuisine="chinese", min_rating=3.0, extras=[]),
        ),
    ]

    for tag, prefs in tests:
        resp = recommend(prefs=prefs, catalog=catalog)
        # Show whether fallback was triggered.
        _print_response(tag, resp)
        if getattr(resp.meta, "fallback_used", False):
            print("  fallback_triggered=True")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

