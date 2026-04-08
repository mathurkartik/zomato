// ── BiteAI API Client ──────────────────────────────────────────────
// Typed fetch wrappers for the FastAPI backend

export const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ── Types ─────────────────────────────────────────────────────────

export interface FiltersResponse {
  localities: string[];
  extras_tags?: string[];
  online_order_count?: number;
  book_table_count?: number;
}

export interface FilterCountsRequest {
  locality?: string | null;
  cuisine?: string | null;
  budget_min_inr?: number;
  budget_max_inr?: number;
  min_rating?: number;
  online_order?: boolean | null;
  book_table?: boolean | null;
}

export interface FilterCountsResponse {
  online_order_count: number;
  book_table_count: number;
}

export interface CuisinesResponse {
  cuisines: string[];
}

export interface CuisineCount {
  cuisine: string;
  count: number;
}

export interface CuisineSummaryResponse {
  locality: string;
  counts: CuisineCount[];
}

export interface HealthResponse {
  status: 'ok' | 'degraded';
  catalog_rows?: number;
}

export interface RecommendRequest {
  locality: string;
  budget_min_inr?: number;
  budget_max_inr: number;
  cuisine: string;
  min_rating: number;
  extras?: string[];
  specific_cravings?: string;
  /** budget: value-first shortlist; premium: quality-first */
  persona?: 'budget' | 'premium';
  online_order?: boolean | null;
  book_table?: boolean | null;
}

export interface RestaurantItem {
  id: string | number;
  rank: number;
  name: string;
  rating?: number | null;
  cost_display?: string;
  rest_type?: string;
  cuisines?: string[];
  weighted_score?: number | null;
  votes?: number | null;
  explanation: string;
}

export interface RecommendMeta {
  shortlist_size: number;
  latency_ms?: number;
  tokens_used?: number;
  cache_hit?: boolean;
  model?: string;
  llm_used?: boolean;
  fallback_used?: boolean;
  relaxed_rating?: boolean;
  persona?: 'budget' | 'premium';
  reason?: string;
  min_cost_in_locality?: number;
  suggest_localities?: string[];
}

export interface RejectedItem {
  id: string;
  name: string;
  rating: number | null;
  cost_for_two: number | null;
  cost_display: string | null;
  rejection_reason: string;
}

export interface RecommendResponse {
  items: RestaurantItem[];
  rejected: RejectedItem[];
  summary?: string;
  meta: RecommendMeta;
}

// ── API Functions ─────────────────────────────────────────────────

export async function fetchFilters(): Promise<FiltersResponse> {
  const res = await fetch(`${BASE_URL}/api/v1/filters`);
  if (!res.ok) throw new Error(`Filters fetch failed: ${res.status}`);
  return res.json();
}

export async function fetchCuisinesForLocality(
  locality: string
): Promise<CuisinesResponse> {
  const res = await fetch(
    `${BASE_URL}/api/v1/filters/cuisines?locality=${encodeURIComponent(locality)}`
  );
  if (!res.ok) throw new Error(`Cuisines fetch failed: ${res.status}`);
  return res.json();
}

export async function fetchCuisineSummary(
  locality: string,
  limit = 12
): Promise<CuisineSummaryResponse> {
  const res = await fetch(
    `${BASE_URL}/api/v1/filters/cuisines/summary?locality=${encodeURIComponent(locality)}&limit=${limit}`
  );
  if (!res.ok) throw new Error(`Cuisine summary fetch failed: ${res.status}`);
  return res.json();
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${BASE_URL}/health`);
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
  return res.json();
}

export async function postRecommend(
  body: RecommendRequest
): Promise<RecommendResponse> {
  const res = await fetch(`${BASE_URL}/api/v1/recommend`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Recommend failed: ${res.status}`);
  return res.json();
}

export async function postFilterCounts(
  body: FilterCountsRequest
): Promise<FilterCountsResponse> {
  const res = await fetch(`${BASE_URL}/api/v1/filters/counts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`Filter counts failed: ${res.status}`);
  return res.json();
}
