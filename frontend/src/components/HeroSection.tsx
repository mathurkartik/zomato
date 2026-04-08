'use client';
import Image from 'next/image';
import SearchCard from './SearchCard';
import type { RecommendRequest, CuisineCount } from '@/lib/api';
import { getCuisineVisualFromSlug } from '@/lib/cuisineVisual';

interface HeroSectionProps {
  localities: string[];
  loadingLocalities: boolean;
  cuisines: string[];
  cuisineSummary: CuisineCount[];
  onlineOrderCount: number;
  bookTableCount: number;
  loadingCuisines: boolean;
  onLocalityChange: (loc: string) => void;
  onSubmit: (params: RecommendRequest) => void;
  loading: boolean;
  /** Drives hero background to match selected cuisine (dropdown). */
  heroCuisine?: string;
  onHeroCuisineChange?: (cuisine: string) => void;
}

export default function HeroSection({
  localities,
  loadingLocalities,
  cuisines,
  cuisineSummary,
  onlineOrderCount,
  bookTableCount,
  loadingCuisines,
  onLocalityChange,
  onSubmit,
  loading,
  heroCuisine = '',
  onHeroCuisineChange,
}: HeroSectionProps) {
  const visual = getCuisineVisualFromSlug(heroCuisine);

  return (
    <section className="hero" aria-label="Search your perfect meal">
      <Image
        src={visual.imageUrl}
        alt=""
        fill
        className="hero-bg"
        priority
        sizes="100vw"
        style={{ objectFit: 'cover' }}
      />

      <div className="hero-overlay" aria-hidden="true" />

      <div className="hero-content">
        <h1 className="hero-title">
          Find Your Perfect Meal with Zomato AI
        </h1>

        <SearchCard
          localities={localities}
          loadingLocalities={loadingLocalities}
          cuisines={cuisines}
          cuisineSummary={cuisineSummary}
          onlineOrderCount={onlineOrderCount}
          bookTableCount={bookTableCount}
          loadingCuisines={loadingCuisines}
          onLocalityChange={onLocalityChange}
          onSubmit={onSubmit}
          loading={loading}
          onHeroCuisineChange={onHeroCuisineChange}
        />
      </div>
    </section>
  );
}
