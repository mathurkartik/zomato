'use client';
import { useState, useEffect } from 'react';
import {
  fetchFilters,
  fetchCuisinesForLocality,
  fetchCuisineSummary,
  fetchHealth,
  postRecommend,
  type RecommendRequest,
  type RecommendResponse,
  type HealthResponse,
  type CuisineCount,
} from '@/lib/api';

interface FiltersState {
  localities: string[];
  extras_tags: string[];
  cuisines: string[];
  cuisineSummary: CuisineCount[];
  online_order_count: number;
  book_table_count: number;
  loadingLocalities: boolean;
  loadingCuisines: boolean;
}

interface SearchState {
  loading: boolean;
  result: RecommendResponse | null;
  error: string | null;
}

export function useRecommend() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [filters, setFilters] = useState<FiltersState>({
    localities: [],
    extras_tags: [],
    cuisines: [],
    cuisineSummary: [],
    online_order_count: 0,
    book_table_count: 0,
    loadingLocalities: true,
    loadingCuisines: false,
  });
  const [search, setSearch] = useState<SearchState>({
    loading: false,
    result: null,
    error: null,
  });

  // Boot: health + localities
  useEffect(() => {
    void (async () => {
      // Health check
      try {
        const h = await fetchHealth();
        setHealth(h);
      } catch {
        setHealth({ status: 'degraded' });
      }

      // Filters
      try {
        const data = await fetchFilters();
        setFilters(prev => ({
          ...prev,
          localities: (data.localities || []).sort(),
          extras_tags: data.extras_tags || ['veg', 'family', 'quick_service', 'rooftop', 'romantic', 'outdoor'],
          online_order_count: data.online_order_count ?? 0,
          book_table_count: data.book_table_count ?? 0,
          loadingLocalities: false,
        }));
      } catch {
        setFilters(prev => ({ ...prev, loadingLocalities: false }));
      }
    })();
  }, []);

  // Reload cuisines when locality changes
  const loadCuisines = async (locality: string) => {
    if (!locality) {
      setFilters(prev => ({
        ...prev,
        cuisines: [],
        cuisineSummary: [],
        loadingCuisines: false,
      }));
      return;
    }
    setFilters(prev => ({
      ...prev,
      loadingCuisines: true,
      cuisines: [],
      cuisineSummary: [],
    }));
    try {
      const [data, summary] = await Promise.all([
        fetchCuisinesForLocality(locality),
        fetchCuisineSummary(locality).catch(() => ({ counts: [] as CuisineCount[] })),
      ]);
      setFilters(prev => ({
        ...prev,
        cuisines: (data.cuisines || []).sort(),
        cuisineSummary: summary.counts || [],
        loadingCuisines: false,
      }));
    } catch {
      setFilters(prev => ({ ...prev, loadingCuisines: false }));
    }
  };

  // Submit search
  const submitSearch = async (params: RecommendRequest) => {
    setSearch({ loading: true, result: null, error: null });
    try {
      const result = await postRecommend(params);
      setSearch({ loading: false, result, error: null });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unknown error';
      setSearch({ loading: false, result: null, error: msg });
    }
  };

  const clearResults = () => {
    setSearch({ loading: false, result: null, error: null });
  };

  return { health, filters, search, loadCuisines, submitSearch, clearResults };
}
