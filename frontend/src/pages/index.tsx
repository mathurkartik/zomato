'use client';
import { useState } from 'react';
import Header from '@/components/Header';
import HeroSection from '@/components/HeroSection';
import ResultsSection from '@/components/ResultsSection';
import { useRecommend } from '@/hooks/useRecommend';
import type { RecommendRequest } from '@/lib/api';

export default function HomePage() {
  const { health, filters, search, loadCuisines, submitSearch, clearResults } = useRecommend();
  const [hasSearched, setHasSearched] = useState(false);
  const [heroCuisine, setHeroCuisine] = useState('');
  const [lastParams, setLastParams] = useState<RecommendRequest | null>(null);

  async function handleSubmit(params: RecommendRequest) {
    setHasSearched(true);
    setLastParams(params);
    await submitSearch(params);
  }

  function handleLocalityChange(loc: string) {
    clearResults();
    setHasSearched(false);
    setHeroCuisine('');
    void loadCuisines(loc);
  }

  async function handleLocalityTryNearby(loc: string) {
    if (!loc) return;
    await loadCuisines(loc);
    if (!lastParams) return;
    const nextParams: RecommendRequest = { ...lastParams, locality: loc };
    setHasSearched(true);
    setLastParams(nextParams);
    await submitSearch(nextParams);
  }

  return (
    <>
      <Header health={health} />

      <main id="main-content">
        <HeroSection
          localities={filters.localities}
          loadingLocalities={filters.loadingLocalities}
          cuisines={filters.cuisines}
          cuisineSummary={filters.cuisineSummary}
          onlineOrderCount={filters.online_order_count}
          bookTableCount={filters.book_table_count}
          loadingCuisines={filters.loadingCuisines}
          onLocalityChange={handleLocalityChange}
          onSubmit={handleSubmit}
          loading={search.loading}
          heroCuisine={heroCuisine}
          onHeroCuisineChange={setHeroCuisine}
        />

        <ResultsSection
          loading={search.loading}
          result={search.result}
          error={search.error}
          hasSearched={hasSearched}
          onLocalityChange={handleLocalityTryNearby}
        />
      </main>

      <footer className="site-footer">
        <p>
          BiteAI &middot; Bangalore &middot; Groq-powered recommendations &middot; Zomato dataset ~51k restaurants
        </p>
      </footer>
    </>
  );
}
