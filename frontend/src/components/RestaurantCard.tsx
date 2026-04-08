import { useState } from 'react';
import type { RestaurantItem } from '@/lib/api';
import { getCuisineVisualFromSlug } from '@/lib/cuisineVisual';

interface RestaurantCardProps {
  item: RestaurantItem;
  llmUsed?: boolean;
  index?: number;
}

export default function RestaurantCard({
  item,
  llmUsed = true,
  index = 0,
}: RestaurantCardProps) {
  const [imgFailed, setImgFailed] = useState(false);
  const primaryCuisine = item.cuisines && item.cuisines.length ? item.cuisines[0] : undefined;
  const visual = getCuisineVisualFromSlug(primaryCuisine);

  const cuisineStr = item.cuisines && item.cuisines.length
    ? item.cuisines.map(c => c.charAt(0).toUpperCase() + c.slice(1)).join(' · ')
    : null;

  const scoreLine = (() => {
    const ws = item.weighted_score;
    const r = item.rating;
    const v = item.votes ?? 0;
    if (ws == null || r == null) return null;
    const pop = Math.log1p(Math.max(0, v));
    return `Score: ${ws.toFixed(1)} (rating ${r.toFixed(1)} × popularity ${pop.toFixed(1)})`;
  })();

  return (
    <article
      className="restaurant-card"
      id={`card-${item.id ?? index}`}
      style={{ animationDelay: `${index * 60}ms` }}
      aria-label={`Restaurant: ${item.name}`}
    >
      {/* Thumbnail — cuisine-themed photo + gradient fallback */}
      <div className="card-thumb" style={{ background: visual.gradient }}>
        {!imgFailed && (
          <img
            className="card-thumb-img"
            src={visual.imageUrl}
            alt=""
            loading="lazy"
            decoding="async"
            onError={() => setImgFailed(true)}
          />
        )}
        <div className="card-thumb-scrim" aria-hidden />
        <div
          className="card-thumb-emoji"
          aria-hidden
        >
          {visual.emoji}
        </div>

        {/* Rank badge */}
        <div className="card-rank-badge" aria-label={`Rank ${item.rank}`}>
          {item.rank}
        </div>

        {/* Rating badge */}
        {item.rating != null && (
          <div className="card-rating-badge" aria-label={`Rating ${item.rating.toFixed(1)}`}>
            <span className="star-icon">★</span>
            {item.rating.toFixed(1)}
          </div>
        )}
      </div>

      {/* Body */}
      <div className="card-body">
        <h3 className="card-name">{item.name}</h3>

        <div className="card-meta-row">
          {item.cost_display && (
            <span className="card-badge badge-cost">{item.cost_display}</span>
          )}
          {item.rest_type && (
            <span className="card-badge badge-type">{item.rest_type}</span>
          )}
          {!llmUsed && (
            <span className="card-badge badge-fallback">⚡ Fallback</span>
          )}
        </div>

        {cuisineStr && (
          <p className="card-cuisines">{cuisineStr}</p>
        )}

        {scoreLine && (
          <p className="card-score-line" title="weighted_score = rating × ln(1 + votes)">
            {scoreLine}
          </p>
        )}

        <p className="card-reason">
          &ldquo;{item.explanation}&rdquo;
        </p>
      </div>
    </article>
  );
}
