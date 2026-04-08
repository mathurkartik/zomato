# improvement4.md
# Complete implementation guide — safe cleanups + innovations

Apply changes in the listed order.

---

## SECTION 1 — Cleanup

Delete obsolete debug/scratch files (already applied in project cleanup).

## SECTION 2 — `.gitignore`

Keep scratch/debug patterns ignored:

```gitignore
# debug and scratch files
*.txt
debug_*.py
test_*.txt
raw_output.txt
```

## SECTION 3 — Scenario config correctness

- Replace `Continental` with `European` in `date_night`.
- Remove unused `diversity_boost` from `food_exploration`.

## SECTION 4 — Shared helper

Create shared cuisine synonym helper in `src/utils.py`:

- `cuisine_tokens_equivalent(a, b)`

## SECTION 5/6/7 — De-duplicate helpers + orchestrator fixes

- Remove local `_cuisine_tokens_equivalent` copies from:
  - `src/phase2/filter.py`
  - `src/phase3/scenario_filter.py`
  - `src/phase3/orchestrator.py`
- Import shared helper from `src.utils`.
- In orchestrator:
  - use context-aware budget extraction
  - do not override dropdown locality from free text when already set
  - keep rank renumbering, remove final re-sort
  - replace monitor helper call with resilient inline logger

## SECTION 8 — API root route

- Remove static `web/` serving from backend app.
- Add JSON `GET /` service info route.

## SECTION 9 — Innovation 1: “Why Not?” rejected list

- Add `RejectedItem` model in `src/phase4/schemas.py`.
- Add `rejected` in `RecommendationResponse`.
- Build rejected list in orchestrator from shortlisted-but-not-returned items.
- Render rejected list in frontend results section.

## SECTION 10 — Innovation 2: Online order + table booking filters

- Add optional `online_order` and `book_table` to preferences/request model.
- Apply both in deterministic filtering.
- Add counts to filters response.
- Add UI toggles in search card.
- Send values as `true` or `null` in recommend request body.

## SECTION 11 — Innovation 3: “Try Nearby” locality actions

- Use `meta.suggest_localities` in empty state.
- Clicking locality suggestion should update locality and trigger re-search.

## SECTION 12 — Innovation 4: Confidence badge

Add badge in results header based on `meta`:

- fallback badge when LLM unavailable
- relaxed-rating badge when rating floor is relaxed
- high-confidence badge for large shortlist
- default shortlist-size badge otherwise

---

## Verification checklist

- `GET /` returns service JSON.
- `POST /api/v1/recommend` returns `rejected`.
- `GET /api/v1/filters` returns counts.
- Search toggles correctly filter results.
- Empty-state nearby locality actions work.
- Confidence badge renders above results.
- Test suite passes.

