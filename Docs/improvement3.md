# improvement3.md

## Feature: Dish-based search over cuisine-level catalog

The dataset is cuisine-granular, not dish-granular. Dish input is mapped to cuisine before deterministic filtering.

## Implemented modules

- `src/phase3/dish_mapping.py`
- `src/phase3/query_parser.py`
- `src/phase3/orchestrator.py`

## Behavior

1. Parse dish mention from free-text query.
2. Map dish to canonical cuisine token.
3. Override effective cuisine for deterministic filtering.
4. If mapped cuisine returns no results, safely retry with original user-selected cuisine.
5. Include dish/mapped-cuisine context in prompt for better explanation quality.

## Example mappings

- `butter chicken` -> `north indian`
- `dosa` -> `south indian`
- `pizza` -> `italian`
- `coffee` -> `cafe`
- `cheesecake` -> `desserts`

## Validation checklist

- [ ] Dish-only free-text query returns relevant cuisine results.
- [ ] Fallback to original cuisine works when mapped cuisine has no match.
- [ ] API `meta` still reflects normal reason/error/fallback semantics.

Enhance the system to support **dish-based search** via deterministic **Dish -> Cuisine mapping**.

## Context

The current dataset is cuisine-level, not dish-level. This means dish queries cannot be used directly for retrieval.

So the architecture must enforce:

- Dish query -> mapped cuisine -> deterministic filtering
- LLM is used only for ranking + explanation on shortlisted restaurants
- No dataset schema change required

---

## Implemented Architecture (End-to-End)

### Frontend

- User types free text in the chat input (example: "butter chicken under 900").
- UI sends this as `specific_cravings` in `POST /api/v1/recommend`.
- A hint is shown under chat input to communicate supported dish terms.

### Backend API / Orchestrator

- API accepts `specific_cravings` (free text).
- Orchestrator parses query and detects:
  - `detected_dish`
  - `mapped_cuisine_from_dish`
  - `budget_extracted` (if present)
- If a mapped cuisine exists, it overrides request cuisine for deterministic filtering.

### Business Logic Layer

- `dish_mapping.py`: central dish -> cuisine mapping dictionary.
- `query_parser.py`:
  - `extract_dish(query)` detects strongest dish phrase.
  - `cuisine_for_dish(dish)` returns mapped cuisine.
- `filter_restaurants(...)` stays deterministic and unchanged in principle:
  - locality + cuisine + rating + budget filtering
  - no LLM retrieval.

### LLM Layer

- Prompt includes detected dish/cuisine context when available.
- LLM still receives shortlist only and can only rank/explain those IDs.

### Monitoring

Request-level monitor logs include:

- `user_query`
- `detected_dish`
- `mapped_cuisine_from_dish`
- `detected_scenario`
- candidate counts before/after scenario filter

---

## Rule Set

1. Never retrieve by dish directly from dataset.
2. Always map dish -> cuisine before deterministic filtering.
3. LLM is ranking/explanation only, never primary retrieval.
4. If dish mapping yields no results, fallback to normal cuisine flow.

---

## Edge Case Handling

- **Multiple dishes in query**
  - choose strongest match by earliest position, then longer phrase (e.g. "spring roll" over "roll").
- **Dish not found**
  - use normal filtering with request cuisine.
- **No results after mapped cuisine**
  - retry with user-selected cuisine as safe fallback.

---

## Files Added / Updated

- Added: `src/phase3/dish_mapping.py`
- Added: `src/phase3/query_parser.py`
- Updated: `src/phase3/orchestrator.py`
- Updated: `src/phase3/prompt_builder.py`
- Updated: `src/phase3/monitor.py`
- Updated: `frontend/src/components/SearchCard.tsx`

---

## Goal

Enable dish-based user intent without changing dataset schema and without breaking the existing architecture contract:

**free text -> deterministic retrieval -> LLM ranking/explanation**.