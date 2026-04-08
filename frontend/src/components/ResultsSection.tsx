import type { RecommendResponse, RecommendMeta } from '@/lib/api';
import { formatLocalityDisplay } from '@/lib/formatLocality';
import RestaurantCard from './RestaurantCard';

const REASON_MESSAGES: Record<string, [string, string]> = {
  NO_LOCALITY_MATCH: ['No restaurants present in this area.', 'Try a different neighbourhood.'],
  NO_CUISINE_MATCH:  ['No restaurants present for this cuisine here.', 'Pick another cuisine or locality.'],
  BUDGET_TOO_LOW:    ['No restaurants present in this budget range.', ''],
  THIN_LOCALITY:     ['No restaurants present — too few matches in this area.', 'Try a nearby locality below or relax your rating.'],
  NO_RESULTS:        ['No restaurants present with these filters.', 'Try a higher budget or a lower minimum rating.'],
};

function ConfidenceBadge({ meta }: { meta: RecommendMeta }) {
  if (meta.fallback_used) {
    return (
      <span style={{
        background: '#fee2e2', color: '#991b1b',
        padding: '0.2rem 0.65rem', borderRadius: '999px', fontSize: '0.75rem',
      }}>
        Fallback - LLM unavailable
      </span>
    );
  }
  if (meta.relaxed_rating) {
    return (
      <span style={{
        background: '#fef3c7', color: '#92400e',
        padding: '0.2rem 0.65rem', borderRadius: '999px', fontSize: '0.75rem',
      }}>
        Limited results - rating filter relaxed
      </span>
    );
  }
  if ((meta.shortlist_size ?? 0) >= 10) {
    return (
      <span style={{
        background: '#d1fae5', color: '#065f46',
        padding: '0.2rem 0.65rem', borderRadius: '999px', fontSize: '0.75rem',
      }}>
        High confidence · {meta.shortlist_size} options
      </span>
    );
  }
  return (
    <span style={{
      background: '#e0f2fe', color: '#0c4a6e',
      padding: '0.2rem 0.65rem', borderRadius: '999px', fontSize: '0.75rem',
    }}>
      {meta.shortlist_size} options found
    </span>
  );
}

interface ResultsSectionProps {
  loading: boolean;
  result: RecommendResponse | null;
  error: string | null;
  hasSearched: boolean;
  onLocalityChange: (locality: string) => void;
}

export default function ResultsSection({
  loading,
  result,
  error,
  hasSearched,
  onLocalityChange,
}: ResultsSectionProps) {
  const items = result?.items ?? [];
  const meta  = result?.meta;

  // ── Spinner ─────────────────────────────────────────────────────
  if (loading) {
    return (
      <section className="results-section" aria-busy="true" aria-live="polite">
        <div className="spinner-wrap" id="spinner">
          <div className="spinner" />
          <p className="spinner-text">Finding your perfect spot…</p>
        </div>
      </section>
    );
  }

  // ── API error ────────────────────────────────────────────────────
  if (error) {
    return (
      <section className="results-section" aria-live="polite">
        <div className="empty-state" id="empty-state">
          <div className="empty-icon">⚠️</div>
          <h2 className="empty-title" id="empty-title">Could not reach the server</h2>
          <p className="empty-desc" id="empty-desc">{error}</p>
        </div>
      </section>
    );
  }

  // ── No search yet ────────────────────────────────────────────────
  if (!hasSearched) {
    return (
      <section className="results-section" aria-live="polite">
        <h2 className="results-heading">Personalized Picks</h2>
        <p className="results-subheading">
          Fill in your preferences above and click &ldquo;Get Recommendations&rdquo; to discover your next meal.
        </p>
      </section>
    );
  }

  // ── Empty state (show whenever search finished with no items; meta may be missing)
  if (hasSearched && items.length === 0 && !loading) {
    const reason = meta?.reason || 'NO_RESULTS';
    const [title, desc] = REASON_MESSAGES[reason] ?? ['No restaurants found.', 'Try adjusting your filters.'];
    const finalDesc =
      reason === 'BUDGET_TOO_LOW' && meta?.min_cost_in_locality
        ? `Cheapest available is ₹${meta.min_cost_in_locality.toLocaleString()} for two. Try raising your budget.`
        : desc;

    const suggest = meta?.suggest_localities ?? [];

    return (
      <section className="results-section" aria-live="polite">
        <div className="empty-state" id="empty-state">
          <div className="empty-icon">🔍</div>
          <h2 className="empty-title" id="empty-title">{title}</h2>
          <p className="empty-desc" id="empty-desc">{finalDesc}</p>
          {reason === 'THIN_LOCALITY' && suggest.length > 0 && (
            <div className="try-nearby-row" role="group" aria-label="Try a nearby locality">
              {suggest.map(loc => (
                <button
                  key={loc}
                  type="button"
                  className="try-nearby-btn"
                  onClick={() => onLocalityChange(loc)}
                >
                  {formatLocalityDisplay(loc)}
                </button>
              ))}
            </div>
          )}
        </div>
      </section>
    );
  }

  // ── Results ──────────────────────────────────────────────────────
  // Deduplicate by id
  const seen  = new Set<string | number>();
  const unique = items.filter(it => {
    const key = it.id ?? it.name;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  return (
    <section className="results-section" aria-live="polite">
      <h2 className="results-heading" id="personalized-picks">Personalized Picks</h2>
      <p className="results-subheading">
        {unique.length} recommendation{unique.length !== 1 ? 's' : ''} tailored just for you
      </p>

      {meta && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h2 style={{ margin: 0, fontSize: '1.1rem' }}>Recommendations</h2>
          <ConfidenceBadge meta={meta} />
        </div>
      )}

      {meta?.suggest_localities && meta.suggest_localities.length > 0 && (
        <div className="try-nearby-row try-nearby-inline" role="group" aria-label="More options in other areas">
          <span className="try-nearby-hint">Also try this cuisine in:</span>
          {meta.suggest_localities.map(loc => (
            <button
              key={loc}
              type="button"
              className="try-nearby-btn"
              onClick={() => onLocalityChange(loc)}
            >
              {formatLocalityDisplay(loc)}
            </button>
          ))}
        </div>
      )}

      {/* Summary */}
      {result?.summary && (
        <div className="summary-block" id="summary-block">
          <span className="summary-icon">🤖</span>
          {result.summary}
        </div>
      )}

      {/* Cards grid */}
      <div className="cards-grid" id="cards-grid">
        {unique.map((item, idx) => (
          <RestaurantCard
            key={item.id ?? idx}
            item={item}
            llmUsed={meta?.llm_used}
            index={idx}
          />
        ))}
      </div>

      {result?.rejected && result.rejected.length > 0 && (
        <details style={{ marginTop: '2rem' }}>
          <summary style={{
            cursor: 'pointer',
            color: 'var(--color-text-secondary)',
            fontSize: '0.875rem',
            userSelect: 'none',
          }}>
            {result.rejected.length} other restaurants were considered but not recommended
          </summary>
          <ul style={{ marginTop: '0.75rem', listStyle: 'none', padding: 0 }}>
            {result.rejected.map((r) => (
              <li key={r.id} style={{
                fontSize: '0.8rem',
                color: 'var(--color-text-secondary)',
                marginBottom: '0.35rem',
                paddingLeft: '0.75rem',
                borderLeft: '2px solid var(--color-border-tertiary)',
              }}>
                <strong>{r.name}</strong>
                {r.rating != null && ` · ★ ${r.rating}`}
                {r.cost_display && ` · ${r.cost_display}`}
                {' - '}{r.rejection_reason}
              </li>
            ))}
          </ul>
        </details>
      )}

      {/* Meta footer */}
      {meta && (
        <footer className="meta-footer" id="meta-footer">
          <span className="meta-item" id="meta-shortlist">
            🔍 {meta.shortlist_size} shortlisted
          </span>
          <span className="meta-item" id="meta-latency">
            ⏱ {meta.latency_ms ?? 0}ms
          </span>
          {meta.tokens_used != null && (
            <span className="meta-item" id="meta-tokens">
              🔤 {meta.tokens_used} tokens
            </span>
          )}
          <span className="meta-item" id="meta-cache">
            {meta.cache_hit ? '⚡ Cached (instant)' : '🌐 Live query'}
          </span>
          {meta.model && (
            <span className="meta-item" id="meta-model">
              🤖 {meta.model}
            </span>
          )}
        </footer>
      )}
    </section>
  );
}
