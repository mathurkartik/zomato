# phase-wise-architecture.md

This document reflects the current architecture implemented in the project.

## Overview

Pipeline:

1. Frontend captures user input
2. Backend validates request and loads catalog
3. Deterministic filtering creates shortlist
4. Scenario filter optionally narrows shortlist
5. LLM ranks/explains candidates (with deterministic fallback)
6. Response includes recommendations, rejected list, and meta signals

## Phase 1: Data normalization and catalog loading

Primary responsibilities:

- Load data into a normalized in-memory catalog.
- Normalize localities/cuisines and retain fields used by filtering/ranking.
- Provide helper endpoints for available localities/cuisines and locality cuisine summaries.

Key modules:

- `src/phase1/transform.py`
- `src/phase2/catalog_loader.py`

## Phase 2: Preferences and deterministic filtering

Primary responsibilities:

- Validate user preferences.
- Apply deterministic filters first:
  - locality
  - cuisine
  - budget range
  - minimum rating
  - online order
  - table booking
- Apply shortlist ranking/capping and return reason codes for empty states.

Key modules:

- `src/phase2/preferences.py`
- `src/phase2/filter.py`

## Phase 3: Intent + orchestration + LLM ranking

Primary responsibilities:

- Parse intent/scenario/dish/locality from free text.
- Map dish to cuisine when applicable.
- Apply scenario rules on top of deterministic shortlist.
- Build prompt and call LLM for ranking/explanations.
- Fall back to deterministic ranking when LLM fails or output is invalid.
- Build rejected list from shortlist items not present in final accepted items.

Key modules:

- `src/phase3/intent_parser.py`
- `src/phase3/query_parser.py`
- `src/phase3/scenario_config.py`
- `src/phase3/scenario_filter.py`
- `src/phase3/prompt_builder.py`
- `src/phase3/groq_client.py`
- `src/phase3/orchestrator.py`

## Phase 4: API and schemas

Primary responsibilities:

- Expose request/response contracts to frontend.
- Provide operational endpoints.
- Return robust meta for empty states and confidence signals.

Endpoints:

- `GET /health`
- `GET /api/v1/filters`
- `GET /api/v1/filters/cuisines`
- `GET /api/v1/filters/cuisines/summary`
- `POST /api/v1/filters/counts` (dynamic online-order / table-booking counts)
- `POST /api/v1/recommend`
- `GET /` (JSON service info)

Key modules:

- `src/phase4/schemas.py`
- `src/phase4/app.py`

## Frontend architecture

Primary responsibilities:

- Maintain search form state and submit recommendation requests.
- Show filter options and dynamic counts.
- Render recommendation cards, confidence indicator, rejected list, and empty-state guidance.

Key areas:

- `frontend/src/components/`
- `frontend/src/hooks/useRecommend.ts`
- `frontend/src/lib/api.ts`
- `frontend/src/pages/index.tsx`

## Response model highlights

- `RecommendationResponse.items`: final ranked recommendations
- `RecommendationResponse.rejected`: shortlisted but not recommended items with reason
- `RecommendationResponse.meta`: shortlist size, fallback flags, latency, reason codes, and suggestion localities

## Notes

- Retrieval remains deterministic; LLM is used for ranking/explanation.
- If LLM is unavailable/invalid, deterministic fallback ensures stable output.
- Dynamic counts endpoint keeps UI counters aligned with active filter context.

# Phase-wise Architecture (Current Implementation)

> Project: AI-powered restaurant recommendation (Zomato dataset)
>  
> Scope: This document reflects the **actual implemented architecture** in code.

---

## 1) System Summary

The system combines deterministic filtering with LLM-based ranking:

1. Parse user text (dish, locality, budget, intent)
2. Build effective structured preferences
3. Deterministically filter catalog
4. Optionally apply scenario constraints
5. Rank with LLM (Groq) and validate IDs
6. Merge with catalog-backed fields
7. Re-rank final list by primary-cuisine match and rating
8. Return display-ready API response with metadata

Key rule:
- LLM is not used for retrieval.
- Retrieval/filtering remains deterministic.

---

## 2) Current Stack

- Backend: Python, FastAPI, Pydantic v2
- Data: pandas + Parquet catalog
- LLM: Groq chat-completions API
- Frontend: Next.js (Pages Router), TypeScript, CSS

---

## 3) Phase 1 — Data Foundation

### What exists
- Catalog ingestion and transformation pipeline
- Canonical fields include:
  - `id`, `name`, `locality`, `cuisines`, `rating`, `votes`, `cost_for_two`, `weighted_score`, `rest_type`
- Alias normalization is used in preference parsing/filter logic

### Purpose
- Provide stable, cleaned, queryable catalog used by all later phases.

---

## 4) Phase 2 — Deterministic Filtering

### Core module
- `src/phase2/filter.py`

### Input model (effective)
- `locality` (supports `"all"` for global search)
- `budget_min_inr`
- `budget_max_inr`
- `cuisine`
- `min_rating`
- `extras` (hints)

### Deterministic pipeline
1. Locality scope:
   - exact locality match, or full catalog for `all/any/*`
2. Cuisine match from tokenized cuisine list
3. Budget range filter:
   - `budget_min_inr <= cost_for_two <= budget_max_inr`
4. Rating filter and relaxation pass
5. Chain-cap and shortlist cap from config

### Reason codes
- `OK`
- `NO_LOCALITY_MATCH`
- `NO_CUISINE_MATCH`
- `NO_RESULTS`
- `THIN_LOCALITY`
- `BUDGET_TOO_LOW`

---

## 5) Phase 3 — Query Intelligence + Orchestration

### Core modules
- `src/phase3/orchestrator.py`
- `src/phase3/query_parser.py`
- `src/phase3/dish_mapping.py`
- `src/phase3/intent_parser.py`
- `src/phase3/scenario_filter.py`
- `src/phase3/prompt_builder.py`
- `src/phase3/monitor.py`

### Text parsing behavior (implemented)
- Dish detection:
  - `extract_dish(query)` using `DISH_TO_CUISINE`
  - phrase precedence by earliest position + longest match
- Dish -> cuisine mapping:
  - `cuisine_for_dish(dish)`
- Locality detection from free text:
  - `extract_locality(query, known_localities)`
- Budget extraction:
  - first integer from query (`extract_budget`)
- Scenario detection:
  - keyword-based scenario mapping in `intent_parser`

### Preference override logic
From user text, orchestrator may override request fields:
- `locality` (if detected in query)
- `cuisine` (if dish mapped)
- `budget_max_inr` (if number extracted)

### Filtering and shortlist handling
1. Run Phase 2 filter on effective preferences
2. Fallback to original preferences if mapped-cuisine path returns no result
3. Apply scenario filters on shortlist
4. Sort shortlist with:
   - persona ordering
   - primary-cuisine priority

### LLM behavior
- Prompt receives shortlist + structured preferences + parsed context
- Returns summary + ranked IDs + explanation
- Returned IDs are validated against shortlist IDs
- If LLM returns partial list, deterministic remainder is appended
- If LLM fails/rate-limits, deterministic fallback ranking is used

### Full-result behavior
- System is not hard-capped at 5 results anymore.
- Final response can include full shortlisted list (subject to validation/fallback).

---

## 6) Final Ranking Rule (Implemented)

Before response is returned, items are re-ordered by:

1. **Primary cuisine match** with target cuisine (first cuisine token)
2. **Higher rating**
3. **Higher votes**

This ensures, for example, European-primary restaurants appear above non-European-primary restaurants when query cuisine is European.

---

## 7) Phase 4 — API Layer

### Core module
- `src/phase4/app.py`

### Endpoints
- `GET /health`
- `GET /api/v1/filters`
- `GET /api/v1/filters/cuisines?locality=...`
- `GET /api/v1/filters/cuisines/summary?locality=...`
- `POST /api/v1/recommend`

### Recommendation request supports
- structured fields: locality, cuisine, budget range, min rating
- free text: `specific_cravings`
- optional scenario field

### Recommendation response
- `summary`
- `items[]` with name, cuisines, rating, cost, explanation, etc.
- `meta` with shortlist size, llm/fallback/cache info, timing/tokens, reason, etc.

---

## 8) Phase 5 — Frontend UX (Current)

### Core components
- `SearchCard`
- `HeroSection`
- `ResultsSection`
- `RestaurantCard`
- `useRecommend` hook + typed `api.ts`

### Current search UX
- Chat-style free text input (`Search`)
- Quick pills (currently text-first dish/cuisine triggers):
  - `pizza`, `butter chicken`, `Cheesecake`, `Biryani`, `Chinese`
- Locality dropdown (optional when text provided; can fallback to global)
- Cuisine dropdown (auto-detected from text when possible)
- Budget **min-max** controls:
  - numeric min/max
  - dual-handle style range sliders
- Min rating pills always visible

### Results UX
- Cards use image theme from restaurant **primary cuisine**
- Reason-specific empty states from backend `meta.reason`
- Meta footer shows shortlist/latency/cache/model/tokens

---

## 9) Cross-cutting Concerns

- In-memory cache in orchestrator with schema-versioned cache key
- Structured monitoring log for recommendation trace
- Safe failure behavior:
  - no hard crash on LLM/network failures
  - deterministic fallback path

---

## 10) Known Design Decisions

- Deterministic retrieval is authoritative.
- LLM is ranking/explanation only.
- Dish search is implemented via cuisine mapping because dataset is cuisine-level.
- Locality can be inferred from text; otherwise user dropdown value is used.

---

## 11) Operational Run Commands

Backend:
- `py -m uvicorn src.phase4.app:app --host 0.0.0.0 --port 8000`

Frontend:
- `cd frontend && npm run dev -- --port 3000`

---

## 12) Current Status

- Architecture is implemented and tested end-to-end.
- Backend unit/integration test suites pass.
- Frontend build passes.
- Doc now reflects current behavior and code paths.

# Architecture: AI-Powered Restaurant Recommendation System

> **Project:** Zomato-style restaurant discovery using LLM-ranked recommendations
> **Dataset:** [ManikaSaini/zomato-restaurant-recommendation](https://huggingface.co/datasets/ManikaSaini/zomato-restaurant-recommendation) (~51,000 rows — Bangalore-only)
> **LLM:** Groq (Phase 3) — API key loaded from `.env`
> **Backend:** Python 3.11+ · FastAPI · Pydantic v2
> **Data layer:** pandas + Parquet
> **Frontend:** Next.js 14 (Pages Router) · TypeScript · Vanilla CSS — `frontend/` directory

---

## Verified checklist (complete before writing any code)

- [ ] Phase 1 — `locality` field used (not city), dedup on `(name_normalized, locality)`, rating parsed from "4.1/5" string, weighted score computed, cuisine alias map applied, cost outliers capped
- [ ] Phase 2 — `budget_max_inr` used (not enum), extras passed as LLM hints only, zero-match returns typed reason code, chain-dominance cap applied, thin-locality check in place
- [ ] Phase 3 — Groq model specified, `top_k = min(5, shortlist_size)`, JSON fallback documented, in-memory cache working, hallucinated IDs validated and dropped
- [ ] Phase 4 — LLM output merged with catalog for all numeric fields, `latency_ms` + `tokens_used` in every meta, `max_shortlist_candidates` read from `config.yaml` not hardcoded, `/filters` returns `localities` not `cities`
- [ ] Phase 5 — Next.js app at `frontend/`; `useRecommend` hook drives all API calls; locality dropdown from API (cascaded cuisine); chat-style input + quick-filter pills; budget ₹ number input + slider; extras labelled as hints; empty state shows reason-specific message; meta footer rendered; Zomato AI light theme with red accent

---

## System context

**Purpose:** Accept user preferences → filter 51,000 restaurant rows to a shortlist → send shortlist to Groq LLM → return ranked recommendations with AI-generated explanations.

**High-level flow:**
```
User inputs → [Cache check] → Locality + cuisine + budget filter
           → Weighted ranking → Groq LLM → Merge with catalog → Frontend display
```

**Non-goals (for now):** User accounts, live scraping, custom embeddings, Redis, PostgreSQL,
fuzzy typo matching (dropdowns prevent it), geo-distance expansion (no coordinates in dataset),
real-time data refresh.

---

## Dependency graph

```
Phase 1 — Catalog (data foundation)
      │
      ▼
Phase 2 — Filter + Preferences (deterministic logic)
      │
      ▼
Phase 3 — LLM orchestration (probabilistic ranking)
      │
      ▼
Phase 4 — API + UI (application layer)
      │
      ▼
Phase 5 — Hardening (observability + quality)
```

Phases 2–3 can be prototyped in a notebook before extraction into modules.
Phase 4 consumes the stable interfaces from Phases 2 and 3.

---

## Traceability matrix

| Problem statement requirement                              | Delivered in phase |
|------------------------------------------------------------|--------------------|
| Load HF Zomato dataset, extract and clean fields           | 1                  |
| User inputs: locality, budget_max_inr, cuisine, rating, extras | 2, 4           |
| Filter catalog to relevant shortlist                       | 2                  |
| Weighted ranking (rating × log votes) before LLM          | 2                  |
| LLM prompt for reasoning and ranking                       | 3                  |
| LLM-generated explanations + summary                      | 3                  |
| Display name, cuisine, rating, cost, explanation           | 4, 5               |
| Observability: latency, token usage, cache status          | 3, 4               |
| Locality dropdown populated from catalog                   | 4, 5               |

---

## Technology stack

| Concern    | Choice                                                                    |
|------------|---------------------------------------------------------------------------|
| Language   | Python 3.11+                                                              |
| Data       | pandas + Parquet                                                          |
| Validation | Pydantic v2                                                               |
| API        | FastAPI                                                                   |
| LLM        | Groq (configured in Phase 3) · key in `.env`                              |
| UI         | **Next.js 14** (Pages Router) · TypeScript · Vanilla CSS · port 3000      |
| API client | `src/lib/api.ts` typed fetch wrappers + `NEXT_PUBLIC_API_URL` env var     |
| State hook | `src/hooks/useRecommend.ts` — localities, cascaded cuisines, results      |
| Config     | `config.yaml` for non-secret tunables (backend) · `.env.local` (frontend) |

---

## Phase 1 — Data ingestion and catalog setup

### 1.1 Objectives
- Download and normalize the Hugging Face dataset into a clean local catalog.
- Define a canonical schema so all later phases use consistent field names.
- Make ingestion repeatable: same command always produces the same artifact.

### 1.2 Dataset — critical facts about this specific dataset

This dataset is **Bangalore-only**. The `location` column contains **locality names**
(e.g. "Indiranagar", "BTM Layout", "Koramangala") — not city names. There is no "Bangalore"
row value in that column. Filtering by city returns zero results. All location filtering
must use `location` as a locality field.

Real column names in this dataset:
- `name` — restaurant name (may contain apostrophes and spelling variants)
- `location` — locality within Bangalore (the primary filter field)
- `rate` — stored as `"4.1/5"` string, or `"NEW"`, or `"-"` — never a float
- `votes` — integer; can be 0 (valid data, not missing)
- `approx_cost(for two people)` — stored as `"800"` or `"1,200"` with commas
- `cuisines` — comma-separated string e.g. `"North Indian, Chinese, Mughlai"`
- `rest_type` — restaurant type (Quick Bites, Casual Dining, etc.)
- `online_order` — Yes / No string
- `book_table` — Yes / No string
- `dish_liked` — free text, optional

### 1.3 Canonical schema

| Internal field     | Source column                     | Type          | Role                                               |
|--------------------|-----------------------------------|---------------|----------------------------------------------------|
| `id`               | derived                           | string        | `md5(name_normalized + locality)[:12]`             |
| `name`             | `name`                            | string        | Display name (original casing)                     |
| `name_normalized`  | derived from `name`               | string        | Lowercase, punctuation-stripped — used for dedup   |
| `locality`         | `location`                        | string        | Locality within Bangalore — the filter field       |
| `cuisines`         | `cuisines`                        | list[string]  | Split, alias-mapped, lowercased                    |
| `rating`           | `rate`                            | float or None | Parsed from "4.1/5"; None if "NEW" or "-"          |
| `votes`            | `votes`                           | int           | Can be 0 — valid, not missing                      |
| `cost_for_two`     | `approx_cost(for two people)`     | int or None   | Commas stripped, cast to int                       |
| `weighted_score`   | derived                           | float         | `rating × log1p(votes)` — used for shortlist rank  |
| `rest_type`        | `rest_type`                       | string        | Optional; passed to LLM as context                 |
| `online_order`     | `online_order`                    | bool          | Optional; surfaced in UI card                      |
| `book_table`       | `book_table`                      | bool          | Optional; surfaced in UI card                      |

### 1.4 Components

| Component        | File path                            | Responsibility                                                    |
|------------------|--------------------------------------|-------------------------------------------------------------------|
| Ingestion script | `scripts/ingest_zomato.py`           | Download dataset, select columns, rename to canonical schema      |
| Validator        | `src/phase1/validate.py`             | Row-level checks, log drop counts and reasons                     |
| Transformer      | `src/phase1/transform.py`            | All cleaning steps; alias dicts; weighted score computation       |
| Catalog store    | `data/processed/restaurants.parquet` | Final cleaned artifact                                            |

### 1.5 Data cleaning steps (in order)

1. **Drop** rows where `name` or `location` is null — these are unfilterable.

2. **Normalize name** for dedup only — keep original name for display:
   ```python
   import re
   def normalize_name(s: str) -> str:
       return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()
   # "Domino's Pizza" → "dominos pizza"
   # "Dominos Pizza"  → "dominos pizza"  ← same key, deduped correctly
   ```

3. **Remove duplicates** on `(name_normalized, locality)` — keep row with highest `votes`.
   Note: "Pizza Hut Indiranagar" and "Pizza Hut BTM" are **separate outlets** — keep both,
   because `locality` differs.

4. **Parse `rating`**: strip `/5` suffix and whitespace, cast to float.
   If value is `"NEW"`, `"-"`, or cannot be cast → set `rating = None`.
   Keep the row — it is excluded only from the rating filter, not from the catalog.

5. **Parse `cost_for_two`**: strip commas and currency symbols, cast to int.
   If null or unparseable → `None`.
   **Drop rows where `cost_for_two < 100`** — these are data entry errors.
   Keep high-cost rows (₹5,000+) — they are valid fine-dining entries.

6. **Parse `cuisines`**: split on `,`, strip whitespace from each token, lowercase.

7. **Apply cuisine alias map** — normalize regional/colloquial names to canonical labels:
   ```python
   CUISINE_ALIASES = {
       "punjabi":     "north indian",
       "mughlai":     "north indian",
       "awadhi":      "north indian",
       "rajasthani":  "north indian",
       "cantonese":   "chinese",
       "szechuan":    "chinese",
       "kerala":      "south indian",
       "chettinad":   "south indian",
       "andhra":      "south indian",
       "hyderabadi":  "south indian",
       "continental": "european",
       "american":    "european",
   }
   # Unrecognized tokens ("cafe", "beverages", "finger food") → kept as-is, never dropped
   # Apply alias map to both catalog AND user input at query time
   ```

8. **Normalize locality**: strip, title case. No city alias map needed — dataset is Bangalore-only.

9. **Compute `weighted_score`**:
   ```python
   import numpy as np
   df["weighted_score"] = df["rating"].fillna(0) * np.log1p(df["votes"])
   # 4.8 rating / 3 votes  → score ≈ 6.7
   # 4.2 rating / 800 votes → score ≈ 28.1   ← ranked higher, correctly
   # rating=None → score=0, appears last in shortlist
   ```

10. **Derive `id`**: `md5(name_normalized + locality)[:12]`.

11. **Log to console**: total rows loaded → rows dropped per reason (null fields, cost < 100,
    duplicate) → final row count.

### 1.6 Configuration (`config.yaml`)

```yaml
data:
  processed_catalog: data/processed/restaurants.parquet
  cost_min_valid: 100              # rows below this cost dropped as data errors

filter:
  max_shortlist_candidates: 40     # max rows passed to LLM — change here, not in code
  chain_max_per_name: 2            # max outlets of same restaurant name in one shortlist
  relax_rating_by: 0.5             # lower min_rating by this on first relaxation pass
  thin_locality_threshold: 3       # if shortlist < this after relax → THIN_LOCALITY

llm:
  model: llama-3.1-8b-instant
  temperature: 0.3
  max_tokens: 1200
  top_k_results: 5
  timeout_seconds: 15
  prompt_version: v1
```

### 1.7 Artifacts and folder layout

```
data/
  raw/                              # optional raw snapshot
  processed/
    restaurants.parquet             # canonical catalog
scripts/
  ingest_zomato.py                  # run once to build catalog
src/
  config.py                         # loads config.yaml → AppConfig dataclass
  phase1/
    ingest.py
    validate.py
    transform.py                    # CUISINE_ALIASES, normalize_name, weighted_score
  phase2/
    preferences.py                  # UserPreferences Pydantic model
    filter.py                       # filter_restaurants() → FilterResult
    catalog_loader.py               # loads parquet at startup
  phase3/
    prompt_builder.py
    groq_client.py
    orchestrator.py                 # in-memory cache + recommend()
  phase4/
    app.py                          # FastAPI app
    schemas.py                      # request/response Pydantic models
web/                                # legacy vanilla HTML/CSS/JS (kept for reference)
  index.html
  styles.css
  app.js
frontend/                           # Next.js 14 frontend (primary UI)
  src/
    pages/
      _app.tsx                      # global CSS + page title
      _document.tsx                 # Google Fonts, meta description
      index.tsx                     # main page — assembles all sections
    components/
      Header.tsx                    # sticky nav: "zomato AI" brand + health badge
      HeroSection.tsx               # full-viewport food-photo hero, embeds SearchCard
      SearchCard.tsx                # chat input, quick pills, locality/cuisine cascade,
                                    #   budget slider, cravings input, more-options accordion
      RestaurantCard.tsx            # result card: gradient thumb, rank badge, AI reason
      ResultsSection.tsx            # spinner / empty state / cards grid / meta footer
    hooks/
      useRecommend.ts               # loads filters, cascades cuisines, submits search
    lib/
      api.ts                        # typed fetch wrappers — BASE_URL from env
    styles/
      globals.css                   # full design system (Zomato-red light theme)
  public/
    hero-food.jpg                   # AI-generated food photography hero image
  .env.local                        # NEXT_PUBLIC_API_URL=http://localhost:8000
  package.json
  tsconfig.json
Docs/
  problem_statement.md
  phase-wise-architecture.md
config.yaml                         # non-secret tunables
.env                                # NEVER commit
.env.example                        # commit — empty placeholder values
.gitignore                          # must include: .env, data/raw/
```

### 1.8 Exit criteria
- [ ] `python scripts/ingest_zomato.py` completes without error.
- [ ] `data/processed/restaurants.parquet` exists with > 40,000 rows.
- [ ] Console prints: loaded → dropped per reason → final count.
- [ ] Sample row printed as JSON — confirms `locality` (not city), `rating` as float or null,
      `weighted_score` as float, `cuisines` as list.
- [ ] Alias map verified: search "punjabi" in output → maps to "north indian".
- [ ] Dedup verified: two outlets of same chain in different localities both kept;
      exact `(name_normalized, locality)` duplicate removed.
- [ ] Weighted score verified: 4.8/3-vote row scores lower than 4.2/800-vote row.

---

## Phase 2 — Preference model and filtering pipeline

### 2.1 Objectives
- Accept user inputs and validate them into a typed preference object.
- Filter the catalog to a bounded, diverse shortlist for the LLM.
- Handle all edge cases without crashing — return typed reason codes, never exceptions.

### 2.2 User preference model

| Field            | Type         | Required | Validation                                          |
|------------------|--------------|----------|-----------------------------------------------------|
| `locality`       | string       | Yes      | Must match a value in catalog's `locality` column   |
| `budget_max_inr` | int          | Yes      | `ge=100, le=5000` — user enters a rupee number directly |
| `cuisine`        | string       | Yes      | Alias-normalized before filtering                   |
| `min_rating`     | float        | Yes      | `ge=0.0, le=5.0`                                    |
| `extras`         | list[string] | No       | Default `[]` — passed to LLM as preference hints only, no hard filter |

**Why `budget_max_inr` not an enum:** The user enters a number (e.g. ₹800). The filter becomes
`cost_for_two <= budget_max_inr`. More honest UX than asking someone to classify their
budget as "medium", and simpler filter logic.

**Why extras are hints-only:** This dataset has no reliable `is_veg` or `is_family_friendly`
column. Tags like "veg", "family", "rooftop" cannot hard-filter the data. They are joined
into the LLM prompt as preference context. This constraint should be visible in the UI label.

### 2.3 Filtering pipeline (order matters)

1. **Locality filter:** `locality == user.locality` (exact match on normalized value).
2. **Cuisine filter:** any token in row's `cuisines` list matches `user.cuisine`
   (case-insensitive; alias map applied to user input at query time).
3. **Rating filter:** `rating >= user.min_rating` — rows where `rating is None` skipped in this pass.
4. **Budget filter:** `cost_for_two <= user.budget_max_inr` — rows where `cost_for_two is None` skipped.
5. **Chain dominance cap:** group by `name_normalized`, keep at most `config.chain_max_per_name`
   (default 2) rows per restaurant name — prevents one chain monopolizing the shortlist.
6. **Shortlist ranking:** sort by `weighted_score DESC`.
   Take top `config.max_shortlist_candidates` (default 40) rows.
7. **Relaxation pass (if shortlist < 5):** lower `min_rating` by `config.relax_rating_by` (0.5),
   re-run steps 3–6. Include None-rated rows at bottom of shortlist in this pass.
   Set `relaxed_rating: true` in meta.
8. **Thin locality check:** if shortlist still < `config.thin_locality_threshold` (3) after
   relaxation → return `reason: "THIN_LOCALITY"`, skip LLM.

### 2.4 Edge case table

| Scenario                                    | Reason code         | Behaviour                                                        |
|---------------------------------------------|---------------------|------------------------------------------------------------------|
| Locality not found in catalog               | `NO_LOCALITY_MATCH` | Return empty, no LLM call                                        |
| No cuisine match after alias normalization  | `NO_CUISINE_MATCH`  | Return empty, no LLM call                                        |
| Zero results after all 4 filters           | `NO_RESULTS`        | Trigger relaxation pass                                          |
| Shortlist < 3 after relaxation             | `THIN_LOCALITY`     | Return empty — no LLM call                                      |
| `budget_max_inr` below cheapest in locality | `BUDGET_TOO_LOW`    | Return empty + `min_cost_in_locality` in meta                   |
| `rating is None` on rows                   | —                   | Skipped in primary pass; included at bottom of relaxation pass   |
| `cost_for_two is None` on rows             | —                   | Skipped in budget filter; included in other passes               |
| `votes == 0`                               | —                   | Keep row — `weighted_score = 0`, appears last in ranking         |
| Chain appears 10× in locality              | —                   | Cap to `chain_max_per_name` (2) in shortlist                    |
| `extras` is empty list                     | —                   | Pass empty string to LLM — no error                              |

### 2.5 Exit criteria
- [ ] Unit tests cover: locality match, cuisine mismatch, rating edge, budget edge,
      empty result, relaxation trigger, chain cap, thin locality.
- [ ] `FilterResult` always has `items` list + `reason` string — never raises an exception.
- [ ] `BUDGET_TOO_LOW` response includes `min_cost_in_locality`.
- [ ] Chain cap confirmed: query returning 5 outlets of one chain → max 2 in shortlist.
- [ ] Shortlist size and timing logged per request.

---

## Phase 3 — LLM integration (Groq) + in-memory cache

### 3.1 Objectives
- Pass filtered shortlist + user preferences to Groq and receive ranked recommendations.
- Cache repeated identical queries — no LLM call on cache hit.
- Keep output schema strict and validate returned IDs against shortlist.

### 3.2 Groq configuration (from `config.yaml`)

| Setting        | Value                                                           |
|----------------|-----------------------------------------------------------------|
| API key source | `.env` (for example: `GROQ_API_KEY`)                            |
| Model          | `llama-3.1-8b-instant` (fast)                              |
| Temperature    | `0.3`                                                           |
| Max tokens     | `1200`                                                          |
| Top K          | `min(config.top_k_results, len(shortlist))` — never ask for more than you have |
| Timeout        | `15s`                                                           |

**Security rule:** `.env` is in `.gitignore`. Never paste the API key into any Cursor
prompt or source file. Cursor generates `.env.example` — copy it to `.env` manually.

### 3.3 In-memory query cache

```python
# src/phase3/orchestrator.py
import hashlib, json

_cache: dict[str, RecommendationResponse] = {}

def _cache_key(prefs: UserPreferences) -> str:
    payload = {
        "locality":       prefs.locality,
        "budget_max_inr": prefs.budget_max_inr,
        "cuisine":        prefs.cuisine,
        "min_rating":     prefs.min_rating,
        "extras":         sorted(prefs.extras),
    }
    return hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()

def recommend(prefs: UserPreferences) -> RecommendationResponse:
    key = _cache_key(prefs)
    if key in _cache:
        return _cache[key]              # instant return — no LLM call
    result = _call_groq_pipeline(prefs)
    _cache[key] = result
    return result
```

Cache is in-process memory only — resets on server restart. No Redis needed.
Include `cache_hit: true/false` in every API response meta.

### 3.4 Prompt structure

**System message:**
```
You are an expert restaurant recommender for Bangalore, India.
You will be given a JSON list of restaurants and a user's preferences.
Recommend the top {top_k} restaurants FROM THE PROVIDED LIST ONLY.
Do not invent, hallucinate, or reference any restaurant not present in the list.
Prefer highly-rated local restaurants over chain brands where ratings are comparable.
Each explanation MUST cite the restaurant's actual rating, cost_for_two, and at least one
cuisine from the provided data. Do not invent numeric values.
Respond ONLY with valid JSON — no markdown fences, no text before or after the object.
```

**User message template:**
```
User preferences:
- Locality: {locality}
- Maximum budget: ₹{budget_max_inr} for two people
- Cuisine preference: {cuisine}
- Minimum rating: {min_rating}
- Additional preferences (hints only — not guaranteed by data): {extras_joined}

Restaurant shortlist (recommend ONLY from restaurant_id values below):
{shortlist_json}

shortlist_json contains only: id, name, rating, cost_for_two, cuisines, rest_type
Do not reference fields not present in this data.

Respond with this exact JSON structure:
{{
  "summary": "2-3 sentences summarising your picks for this user",
  "recommendations": [
    {{
      "restaurant_id": "string — must be an id from the shortlist",
      "rank": 1,
      "explanation": "1-2 sentences citing actual rating, cost, and cuisine from the data"
    }}
  ]
}}
```

### 3.5 Orchestration steps

| Step | Action                                                                               |
|------|--------------------------------------------------------------------------------------|
| 1    | Check in-memory cache — return immediately on hit, `cache_hit: true`                |
| 2    | Run Phase 2 filter → `FilterResult`                                                  |
| 3    | If shortlist empty → return structured empty response, skip LLM                      |
| 4    | Serialize shortlist: 6 fields only — `id, name, rating, cost_for_two, cuisines, rest_type` |
| 5    | Compute `top_k = min(config.top_k_results, len(shortlist))`                         |
| 6    | Render prompt from template (inject `top_k`, `extras_joined`, `shortlist_json`)      |
| 7    | Call Groq with timeout; record `start_time`                                          |
| 8    | Parse JSON response; record `latency_ms`; extract `tokens_used` from LLM response    |
| 9    | **Validate IDs:** drop any `restaurant_id` not present in shortlist (hallucination guard) |
| 10   | If JSON invalid → retry once with "respond ONLY in JSON, no other text" appended     |
| 11   | If retry fails → fallback: return top `top_k` by `weighted_score`, set `llm_used: false` |
| 12   | **Merge** LLM output with catalog rows by `restaurant_id` to fill all display fields |
| 13   | Store in cache; return full response with meta                                        |

**Critical — never trust LLM for numbers:** The LLM provides only `restaurant_id`, `rank`,
and `explanation`. Rating, cost, cuisines, address are all merged from the catalog after parsing.
This prevents hallucinated ratings or costs appearing in the UI.

### 3.6 Exit criteria
- [ ] 3–4 integration test calls to real Groq API.
- [ ] All returned `restaurant_id` values exist in shortlist — none hallucinated.
- [ ] LLM returns valid JSON for at least 3 of 4 test inputs.
- [ ] Fallback tested: force JSON parse failure → top-5-by-score returned, `llm_used: false`.
- [ ] Cache hit confirmed: same query twice → second returns instantly, `cache_hit: true`.

---

## Phase 4 — Backend API (FastAPI)

### 4.1 Objectives
- Expose `/api/v1/recommend` orchestrating Phase 2 + Phase 3.
- Return a fully merged, display-ready response.
- Include observability fields in every response.
- Read all tunables from `config.yaml`, not hardcoded.

### 4.2 API endpoints

#### `POST /api/v1/recommend`

**Request body:**
```json
{
  "locality": "Indiranagar",
  "budget_max_inr": 800,
  "cuisine": "north indian",
  "min_rating": 3.5,
  "extras": ["family", "veg"]
}
```

**Response (200 — results found):**
```json
{
  "summary": "Here are top picks for North Indian in Indiranagar under ₹800...",
  "items": [
    {
      "id": "abc123def456",
      "rank": 1,
      "name": "Punjabi By Nature",
      "locality": "Indiranagar",
      "cuisines": ["north indian"],
      "rating": 4.2,
      "cost_for_two": 700,
      "cost_display": "₹700 for two",
      "rest_type": "Casual Dining",
      "weighted_score": 28.4,
      "explanation": "Rated 4.2 with 820 votes, this North Indian spot fits your ₹800 budget..."
    }
  ],
  "meta": {
    "shortlist_size": 35,
    "model": "llama-3.1-8b-instant",
    "prompt_version": "v1",
    "relaxed_rating": false,
    "cache_hit": false,
    "llm_used": true,
    "latency_ms": 1823,
    "tokens_used": 748
  }
}
```

**Response (200 — budget too low):**
```json
{
  "summary": "No restaurants matched your filters.",
  "items": [],
  "meta": {
    "reason": "BUDGET_TOO_LOW",
    "min_cost_in_locality": 650,
    "shortlist_size": 0,
    "cache_hit": false,
    "llm_used": false,
    "latency_ms": 11,
    "tokens_used": 0
  }
}
```

**Response (422):** Pydantic auto-returns field-level validation errors.

#### `GET /health`
```json
{ "status": "ok", "catalog_rows": 48321 }
```
Returns `"status": "degraded"` if catalog failed to load at startup.

#### `GET /api/v1/filters`
Populated dynamically from the actual catalog — never hardcoded:
```json
{
  "localities": ["Indiranagar", "BTM Layout", "Koramangala", "Whitefield"],
  "cuisines": ["north indian", "chinese", "south indian", "italian"],
  "rating_options": [3.0, 3.5, 4.0, 4.5],
  "extras_tags": ["veg", "family", "quick_service", "rooftop", "romantic", "outdoor"],
  "budget_range": { "min": 100, "max": 5000, "step": 50 }
}
```

Note: `localities` not `cities` — matches actual dataset field name and structure.

### 4.3 Cross-cutting concerns
- CORS enabled for `*` in development.
- Catalog and config loaded once at startup (`@app.on_event("startup")`).
- `max_shortlist_candidates` and all tunables read from `config.yaml` — not hardcoded.
- Pydantic v2 models in `src/phase4/schemas.py` with field-level validators.
- All errors logged with a short request ID.

### 4.4 Exit criteria
- [ ] `POST /api/v1/recommend` returns full response including `latency_ms` and `tokens_used`.
- [ ] `GET /api/v1/filters` returns `localities` (not `cities`) from actual catalog.
- [ ] `GET /health` returns 200 with catalog row count; degraded if catalog missing.
- [ ] `BUDGET_TOO_LOW` response includes `min_cost_in_locality`.
- [ ] Empty result returns 200 — never 404 or 500.
- [ ] Invalid body returns 422 with field-level errors.
- [ ] Changing `max_shortlist_candidates` in `config.yaml` reflects in meta without code change.

---

## Phase 5 — Frontend website (Next.js)

### 5.1 Objectives
- Next.js 14 (Pages Router + TypeScript) app at `frontend/` connecting to FastAPI at `http://localhost:8000`.
- Zomato AI design direction: light theme, red accent `#E23744`, hero with food photography background.
- Locality dropdown populated dynamically — cuisine cascades from locality selection.
- Budget is a ₹ number input + range slider (100–5000), not a low/medium/high enum.
- Extras are multi-select chips clearly labelled as AI preference hints.
- Empty state shows reason-specific guidance mapped from `meta.reason`.
- All display-ready fields merged from catalog — LLM provides only `rank` + `explanation`.

### 5.2 Page layout
```
[ Header: "zomato AI" logo · Home · Dining Out · Delivery · Profile · Health badge ]

[ HERO: full-viewport food-photo background + dark overlay ]
  [ "Find Your Perfect Meal with Zomato AI" ]

  [ Search Card (floating white card) ]
    [ 🎤 "Hi! What are you craving today?"    | Send ]
    [ Italian ] [ Spicy ] [ Dessert ] [ Near Me ] [ Biryani ] [ Chinese ]   ← quick pills
    [ LOCALITY dropdown  ]  [ CUISINE dropdown (cascaded) ]
    [ BUDGET (₹) input   ]  [ SPECIFIC CRAVINGS text input ]
    [ ▶ More options ]
      [ ⭐ Min Rating: 3.0 / 3.5 / 4.0 / 4.5 ]
      [ ✨ Preference Hints: veg | family | quick_service | rooftop | romantic | outdoor ]
    [ Get Recommendations → ]

[ PERSONALIZED PICKS section ]
  [ Summary paragraph from LLM ]
  [ Card grid ]
    [ Card: #1 | [gradient thumb] | ★ 4.2 | ₹700 for two | Casual Dining ]
      [ Cuisines: North Indian ]
      [ AI reason ]
  [ Empty state: reason-specific message + one suggestion ]
  [ Meta footer: 35 shortlisted · 1.8s · 748 tokens · 🌐 Live query · 🤖 model ]

[ Site Footer ]
```

### 5.3 Component architecture

| Component           | File                              | Responsibility                                                              |
|---------------------|-----------------------------------|-----------------------------------------------------------------------------|
| `useRecommend`      | `hooks/useRecommend.ts`           | Boot (health + localities), cascade cuisines, POST recommend, state mgmt   |
| `api.ts`            | `lib/api.ts`                      | Typed fetch wrappers; `BASE_URL` from `NEXT_PUBLIC_API_URL`                |
| `Header`            | `components/Header.tsx`           | Sticky nav with zomato AI brand + health badge                             |
| `HeroSection`       | `components/HeroSection.tsx`      | Full-viewport `<Image>` background + gradient overlay + wraps SearchCard   |
| `SearchCard`        | `components/SearchCard.tsx`       | Form: chat input, quick pills, locality/cuisine selects, budget, cravings, more-options accordion, CTA |
| `RestaurantCard`    | `components/RestaurantCard.tsx`   | Gradient-thumb card with rank badge, rating badge, cuisine tags, AI reason |
| `ResultsSection`    | `components/ResultsSection.tsx`   | Spinner / empty state / deduped cards grid / summary / meta footer         |
| `index.tsx`         | `pages/index.tsx`                 | Assembles all sections; drives `useRecommend`                              |

### 5.4 State and data flow

```
useRecommend hook
  ├── boot: fetchHealth() + fetchFilters()  →  health badge + locality list
  ├── onLocalityChange → fetchCuisinesForLocality()  →  cuisine dropdown
  └── onSubmit → postRecommend()  →  items + meta  →  ResultsSection
```

**Typed API contracts (`lib/api.ts`):**
```typescript
export const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function postRecommend(body: RecommendRequest): Promise<RecommendResponse>
export async function fetchFilters(): Promise<FiltersResponse>
export async function fetchCuisinesForLocality(locality: string): Promise<CuisinesResponse>
export async function fetchHealth(): Promise<HealthResponse>
```

**Submit payload (unchanged from vanilla JS version):**
```typescript
const params: RecommendRequest = {
  locality,
  budget_max_inr: budget,   // integer
  cuisine,
  min_rating: minRating,
  extras: extras.length ? extras : undefined,
  specific_cravings: cravings || undefined,
};
```

### 5.5 Design system

| Token          | Value                              | Usage                               |
|----------------|------------------------------------|-------------------------------------|
| `--red`        | `#E23744`                          | CTAs, active pills, accents         |
| `--red-glow`   | `rgba(226,55,68,0.25)`             | Focus rings, button shadows         |
| `--white`      | `#ffffff`                          | Search card background, result cards|
| `--gray-50`    | `#f8f9fa`                          | Page background                     |
| Font           | Inter (Google Fonts, 300–900)      | All typography                      |
| Hero overlay   | `rgba(10,0,0,0.72) → rgba(10,0,0,0.70)` | Dark gradient over food photo  |

### 5.6 Known issues handled
- Deduplicate result cards by `id` (then `name`) on the frontend before rendering.
- Cuisine dropdown disabled until locality selected; shows "Select a locality first…".
- Loading state per-request: send button shows inline spinner, CTA disabled.
- `meta.llm_used === false` → "⚡ Fallback" badge shown on each card.
- `meta.cache_hit === true` → "⚡ Cached (instant)" shown in meta footer.
- Groq latency 2–5s — spinner shown immediately on submit.

### 5.7 Running locally

```bash
# Terminal 1 — FastAPI backend (port 8000)
uvicorn src.phase4.app:app --reload

# Terminal 2 — Next.js frontend (port 3000)
cd frontend
npm run dev
```

Environment: `frontend/.env.local`
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 5.8 Exit criteria
- [ ] `npm run dev` starts without TypeScript errors.
- [ ] Hero section renders with food photography background and floating search card.
- [ ] Locality dropdown populated from `/api/v1/filters` — not hardcoded.
- [ ] Cuisine dropdown cascades from locality via `/api/v1/filters/cuisines?locality=…`.
- [ ] Budget is a number input with ₹ prefix + range slider 100–5000.
- [ ] Extras chips labelled as preference hints.
- [ ] Submit sends `budget_max_inr` as integer, `extras` as `list[string]`.
- [ ] Each `meta.reason` code maps to a specific non-generic empty-state message.
- [ ] Meta footer shows shortlist size, latency, tokens, cache/live status.
- [ ] No duplicate cards rendered (deduplicated by id).
- [ ] Works end-to-end locally with live backend.

---

## Testing strategy

| Layer   | Test type                  | What to test                                                     | Tool              |
|---------|----------------------------|------------------------------------------------------------------|-------------------|
| Data    | Snapshot test              | Sample row from parquet matches expected schema                  | pytest            |
| Filter  | Unit tests                 | All reason codes, relaxation trigger, chain cap, thin locality   | pytest            |
| Prompt  | Snapshot test              | Rendered template with fixture preferences matches expected output | pytest           |
| API     | Contract tests             | `/recommend` schema; 422 on bad input; empty result returns 200  | pytest + httpx    |
| LLM     | Integration test (optional)| Real Groq call returns valid JSON; all IDs exist in shortlist    | pytest -m integration |
| Cache   | Unit test                  | Same prefs → second call instant, `cache_hit: true`              | pytest            |

Mark LLM integration tests with `@pytest.mark.integration` so CI can skip them
(they cost API calls and add latency).


## Environment variable reference

| Variable       | Description                | Where to get it                      |
|----------------|----------------------------|--------------------------------------|
| `GROQ_API_KEY` | Groq API key for LLM calls | Provider dashboard |

`.env` (never commit):
```
GROQ_API_KEY=your_key_here
```

`.env.example` (commit this):
```
GROQ_API_KEY=
```

**Never commit `.env`.** Never paste the key into a Cursor prompt.

---

## Improvements Log

### IMP-1 — Locality name normalisation (Koramangala block collapse)

**Problem:** The raw dataset stores Koramangala sub-areas as individual localities:
`Koramangala 1St Block`, `Koramangala 2Nd Block`, … `Koramangala 8Th Block`.
Users searching for "Koramangala" found nothing because the filter used exact matching.

**Fix (backend — `src/phase2/catalog_loader.py`):**
A regex `\s+\d+\s*(?:st|nd|rd|th)\s+block\s*$` is applied to every `locality` value
at catalog load time via `normalize_locality()`. This collapses all block variants into
the base name (`Koramangala`). The normalisation happens once at startup so no filter
or query code needed to change.

```python
_BLOCK_RE = re.compile(r"\s+\d+\s*(?:st|nd|rd|th)\s+block\s*$", re.IGNORECASE)

def normalize_locality(name: str) -> str:
    return _BLOCK_RE.sub("", name).strip()

# Applied in load_catalog():
df["locality"] = df["locality"].dropna().map(normalize_locality).reindex(df.index)
```

**Impact:** Localities like `Indiranagar 1st Stage` are **not** affected (no "Block" suffix).
Only `<Name> N[st|nd|rd|th] Block` patterns are collapsed.

---

### IMP-2 — Locality-first cascaded cuisine dropdown

**Problem:** The cuisine dropdown showed all ~80 cuisines across the entire dataset regardless
of which locality was selected, making it easy to pick a cuisine not available in a locality
and get a confusing empty result.

**Fix (backend):**
- New function `get_cuisines_for_locality(catalog, locality)` in `catalog_loader.py` returns
  only cuisines present in that locality's restaurants.
- New endpoint `GET /api/v1/filters/cuisines?locality=<name>` backed by above function.
- New schema `LocalityCuisinesResponse` in `src/phase4/schemas.py`.

**Fix (frontend — `web/app.js`):**
- On page load, cuisine dropdown is **disabled** with placeholder "Select a locality first…"
- When the user picks a locality, `loadCuisinesForLocality(locality)` fetches
  `/api/v1/filters/cuisines?locality=<name>` and repopulates the cuisine list
  with only relevant options.
- Cuisine dropdown enables only after the API call completes.

**Flow:**
```
User selects locality
  → GET /api/v1/filters/cuisines?locality=Church Street
  ← { "locality": "Church Street", "cuisines": ["cafe","continental","italian",...] }
  → Cuisine dropdown repopulates with those cuisines only
```

---

### IMP-3 — "No restaurants present" empty state messaging

**Problem:** When a search returned no results, the generic "No results found" / "Try adjusting
your filters" text was shown regardless of the actual reason.

**Fix (frontend — `web/app.js`):**
Updated `REASON_MESSAGES` map with clearer, user-friendly copy:

| Reason code        | Title shown to user                                      |
|--------------------|----------------------------------------------------------|
| `NO_LOCALITY_MATCH`| No restaurants present in this area.                    |
| `NO_CUISINE_MATCH` | No restaurants serve that cuisine here.                 |
| `BUDGET_TOO_LOW`   | Budget too low for this area. (+ dynamic min cost)      |
| `THIN_LOCALITY`    | Too few restaurants match here.                         |
| `NO_RESULTS`       | No restaurants present with these filters.              |

All empty-state messages now use the phrase **"No restaurants present"** rather than the
generic "No results found", making it explicit that the search succeeded but the dataset
has no matching entries.

---

### IMP-4 — Next.js frontend migration (Zomato AI design)

**Problem:** The original vanilla HTML/CSS/JS frontend in `web/` had no component structure,
no TypeScript safety, and a dated dark-glassmorphism design that differed from the target
Zomato AI visual direction shown in the design screenshot.

**Fix:** Migrated frontend to **Next.js 14 (Pages Router + TypeScript)** at `frontend/`.
The vanilla `web/` directory is preserved for reference.

**Key architectural improvements:**

| Area               | Before (vanilla)                          | After (Next.js)                                        |
|--------------------|-------------------------------------------|--------------------------------------------------------|
| Language           | Vanilla JS (no types)                     | TypeScript — full type safety on API contracts         |
| Structure          | 3 files (index.html, styles.css, app.js)  | 7 components + hook + API client + design system CSS   |
| State management   | Inline DOM manipulation                   | `useRecommend` hook with React state                   |
| API client         | Ad-hoc `fetch` in app.js                  | Typed `lib/api.ts` wrappers + env-var base URL         |
| Design             | Dark glassmorphism (orange accent)        | Zomato AI light theme (red `#E23744`, food-photo hero) |
| Search UX          | Form only                                | Chat-style input + quick-filter pills + accordion       |
| Result display     | Simple card list                          | Responsive grid with gradient thumbnails               |

**New endpoint consumed:** `GET /api/v1/filters/cuisines?locality=<name>` (IMP-2) — driven
from the `useRecommend` hook's `loadCuisines(locality)` function.

**No backend changes required.** All existing API endpoints and response schemas remain
identical. The Next.js app connects to FastAPI via `NEXT_PUBLIC_API_URL` env var.
