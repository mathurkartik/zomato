'use client';
import { useEffect, useState, useRef } from 'react';
import { postFilterCounts } from '@/lib/api';
import type { RecommendRequest, CuisineCount } from '@/lib/api';
import { formatLocalityDisplay } from '@/lib/formatLocality';

interface SearchCardProps {
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
  /** Updates hero imagery to match the cuisine dropdown (not card index). */
  onHeroCuisineChange?: (cuisine: string) => void;
}

const QUICK_PILLS = ['pizza', 'butter chicken', 'Cheesecake', 'Biryani', 'Chinese'];
const DISH_TO_CUISINE: Record<string, string> = {
  'butter chicken': 'north indian',
  'paneer tikka': 'north indian',
  'dal makhani': 'north indian',
  naan: 'north indian',
  roti: 'north indian',
  kebab: 'north indian',
  tandoori: 'north indian',
  biryani: 'north indian',
  thali: 'north indian',
  dosa: 'south indian',
  idli: 'south indian',
  vada: 'south indian',
  sambar: 'south indian',
  uttapam: 'south indian',
  noodles: 'chinese',
  'fried rice': 'chinese',
  manchurian: 'chinese',
  'spring roll': 'chinese',
  pizza: 'italian',
  pasta: 'italian',
  lasagna: 'italian',
  spaghetti: 'italian',
  risotto: 'italian',
  burger: 'fast food',
  sandwich: 'fast food',
  fries: 'fast food',
  wrap: 'fast food',
  roll: 'fast food',
  combo: 'fast food',
  coffee: 'cafe',
  latte: 'cafe',
  cappuccino: 'cafe',
  tea: 'cafe',
  shake: 'cafe',
  cheesecake: 'desserts',
  cake: 'desserts',
  'ice cream': 'desserts',
  brownie: 'desserts',
  pastry: 'desserts',
  waffle: 'desserts',
  donut: 'desserts',
  'pani puri': 'street food',
  golgappa: 'street food',
  chaat: 'street food',
  samosa: 'street food',
  kachori: 'street food',
  korma: 'mughlai',
  nihari: 'mughlai',
  steak: 'continental',
  grill: 'continental',
};

function detectCuisineFromText(query: string): string | null {
  const q = query.toLowerCase();
  const matches: Array<{ idx: number; len: number; cuisine: string }> = [];
  for (const [dish, mappedCuisine] of Object.entries(DISH_TO_CUISINE)) {
    const idx = q.indexOf(dish);
    if (idx !== -1) {
      matches.push({ idx, len: dish.length, cuisine: mappedCuisine });
    }
  }
  if (!matches.length) return null;
  matches.sort((a, b) => (a.idx !== b.idx ? a.idx - b.idx : b.len - a.len));
  return matches[0].cuisine;
}

export default function SearchCard({
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
  onHeroCuisineChange,
}: SearchCardProps) {
  const [chatText, setChatText]       = useState('');
  const [quickActive, setQuickActive] = useState<string | null>(null);
  const [locality, setLocality]       = useState('');
  const [cuisine, setCuisine]         = useState('');
  const [budgetMin, setBudgetMin]     = useState(0);
  const [budgetMax, setBudgetMax]     = useState(1000);
  const [minRating, setMinRating]     = useState(4.0);
  const [onlineOrder, setOnlineOrder] = useState<boolean | null>(null);
  const [bookTable, setBookTable]     = useState<boolean | null>(null);
  const [dynamicOnlineCount, setDynamicOnlineCount] = useState<number>(onlineOrderCount);
  const [dynamicBookCount, setDynamicBookCount] = useState<number>(bookTableCount);
  const [formError, setFormError]     = useState('');

  const formRef = useRef<HTMLFormElement>(null);

  function handleLocalityChange(val: string) {
    setLocality(val);
    setCuisine('');
    setBudgetMin(0);
    setBudgetMax(1000);
    setMinRating(4.0);
    setOnlineOrder(null);
    setBookTable(null);
    setChatText('');
    setQuickActive(null);
    setFormError('');
    onHeroCuisineChange?.('');
    onLocalityChange(val);
  }

  useEffect(() => {
    setDynamicOnlineCount(onlineOrderCount);
    setDynamicBookCount(bookTableCount);
  }, [onlineOrderCount, bookTableCount]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const counts = await postFilterCounts({
          locality: locality || 'all',
          cuisine: cuisine || null,
          budget_min_inr: budgetMin,
          budget_max_inr: budgetMax,
          min_rating: minRating,
          online_order: onlineOrder,
          book_table: bookTable,
        });
        if (cancelled) return;
        setDynamicOnlineCount(counts.online_order_count ?? 0);
        setDynamicBookCount(counts.book_table_count ?? 0);
      } catch {
        if (cancelled) return;
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [locality, cuisine, budgetMin, budgetMax, minRating, onlineOrder, bookTable]);

  function handleQuickPill(pill: string) {
    setQuickActive(prev => (prev === pill ? null : pill));
    const lower = pill.toLowerCase();
    // Drive backend free-text intent with quick pills (visible via chat input).
    setChatText(pill);
    const detected = detectCuisineFromText(lower);
    if (detected) {
      setCuisine(detected);
      onHeroCuisineChange?.(detected);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError('');

    const hasTextSearch = chatText.trim().length > 0;
    if (!hasTextSearch && !locality) {
      setFormError('Please select a locality when no text query is provided.');
      return;
    }
    const autoCuisine = detectCuisineFromText(chatText);
    const finalCuisine = cuisine || autoCuisine;
    if (!finalCuisine) {
      setFormError('Please type a dish (e.g. pizza) or select a cuisine.');
      return;
    }

    onSubmit({
      locality: locality || 'all',
      budget_min_inr: budgetMin,
      budget_max_inr: budgetMax,
      cuisine: finalCuisine,
      min_rating: minRating,
      // Free-text intent used by the backend for scenario detection + explanation.
      specific_cravings: chatText || undefined,
      online_order: onlineOrder,
      book_table: bookTable,
    });
  }

  const cuisineLabel = loadingCuisines
    ? 'Loading cuisines…'
    : !locality
      ? 'Type a dish or choose cuisine…'
      : cuisines.length === 0
        ? 'No cuisines found'
        : 'Choose cuisine…';

  return (
    <form
      id="search-form"
      ref={formRef}
      className="search-card"
      onSubmit={handleSubmit}
      autoComplete="off"
      noValidate
    >
      {/* Chat input row */}
      <div className="chat-input-row">
        <div className="chat-input-wrap">
          <span className="chat-icon">🎤</span>
          <input
            id="chat-input"
            className="chat-input"
            type="text"
            placeholder="Hi! What are you craving today?"
            value={chatText}
            onChange={e => {
              const next = e.target.value;
              setChatText(next);
              const detected = detectCuisineFromText(next);
              if (detected) {
                setCuisine(detected);
                onHeroCuisineChange?.(detected);
              }
            }}
            aria-label="Type your food craving"
          />
        </div>
        <button
            type="submit"
          id="send-btn"
          className="send-btn"
            disabled={!chatText}
        >
          Search
        </button>
      </div>
      <p style={{ marginTop: '0.35rem', marginBottom: '0.55rem', fontSize: '0.78rem', color: 'var(--text-light)' }}>
        Tip: You can type dish names like "butter chicken", "pizza", or "dosa". We map dish intent to cuisine automatically.
      </p>

      {/* Quick-filter pills */}
      <div className="quick-pills" role="group" aria-label="Quick filters">
        {QUICK_PILLS.map(pill => (
          <button
            key={pill}
            type="button"
            className={`quick-pill${quickActive === pill ? ' active' : ''}`}
            onClick={() => handleQuickPill(pill)}
          >
            {pill}
          </button>
        ))}
      </div>

      {/* Main form grid */}
      <div className="form-grid">
        <div className="or-divider" aria-hidden="true">
          <span className="or-divider-line" />
          <span className="or-divider-label">Or</span>
          <span className="or-divider-line" />
        </div>

        {/* Locality */}
        <div className="form-group locality-row">
          <label htmlFor="locality" className="form-label">Locality</label>
          <div className="select-wrap">
            <select
              id="locality"
              className="form-select"
              value={locality}
              onChange={e => handleLocalityChange(e.target.value)}
              disabled={loadingLocalities}
            >
              <option value="">
                {loadingLocalities ? 'Loading localities…' : 'Any locality'}
              </option>
              {localities.map(l => (
                <option key={l} value={l}>{formatLocalityDisplay(l)}</option>
              ))}
            </select>
            <span className="select-chevron">▾</span>
          </div>
        </div>

        {/* Cuisine heatmap (catalog-driven) */}
        {locality && cuisineSummary.length > 0 && (
          <div className="cuisine-heatmap" aria-label="Popular cuisines in this locality">
            <p className="heatmap-label">In {formatLocalityDisplay(locality)}:{' '}
              {cuisineSummary.slice(0, 4).map((row, i) => (
                <span key={row.cuisine}>
                  {i > 0 ? ' · ' : ''}
                  <strong>{row.cuisine.charAt(0).toUpperCase() + row.cuisine.slice(1)}</strong> ({row.count})
                </span>
              ))}
            </p>
          </div>
        )}

        {/* Cuisine */}
        <div className="form-group">
          <label htmlFor="cuisine" className="form-label">Cuisine</label>
          <div className="select-wrap">
            <select
              id="cuisine"
              className="form-select"
              value={cuisine}
              onChange={e => {
                const v = e.target.value;
                setCuisine(v);
                onHeroCuisineChange?.(v);
              }}
              disabled={loadingCuisines || (locality !== '' && cuisines.length === 0)}
            >
              <option value="">{cuisineLabel}</option>
              {cuisines.map(c => (
                <option key={c} value={c}>
                  {c.charAt(0).toUpperCase() + c.slice(1)}
                </option>
              ))}
            </select>
            <span className="select-chevron">▾</span>
          </div>
        </div>

        {/* Budget Range */}
        <div className="form-group">
          <label htmlFor="budget-min" className="form-label">Budget Range (₹ for Two)</label>
          <div className="budget-wrap">
            <span className="budget-prefix">₹</span>
            <input
              id="budget-min"
              className="budget-number"
              type="number"
              min={0} max={5000} step={50}
              value={budgetMin}
              onChange={e => {
                const next = Math.min(5000, Math.max(0, parseInt(e.target.value) || 0));
                setBudgetMin(Math.min(next, budgetMax));
              }}
            />
            <span className="budget-prefix" style={{ marginLeft: 8 }}>to ₹</span>
            <input
              id="budget-max"
              className="budget-number"
              type="number"
              min={0} max={5000} step={50}
              value={budgetMax}
              onChange={e => {
                const next = Math.min(5000, Math.max(0, parseInt(e.target.value) || 0));
                setBudgetMax(Math.max(next, budgetMin));
              }}
            />
          </div>
          <div className="budget-slider-row">
            <span>₹0</span>
            <div className="budget-range-stack">
              <div
                className="budget-range-active"
                style={{
                  left: `${(budgetMin / 5000) * 100}%`,
                  right: `${100 - (budgetMax / 5000) * 100}%`,
                }}
              />
              <input
                type="range"
                id="budget-min-slider"
                className="budget-slider"
                min={0}
                max={5000}
                step={50}
                value={budgetMin}
                onChange={e => {
                  const next = parseInt(e.target.value);
                  setBudgetMin(Math.min(next, budgetMax));
                }}
                aria-label="Minimum budget"
              />
              <input
                type="range"
                id="budget-max-slider"
                className="budget-slider"
                min={0}
                max={5000}
                step={50}
                value={budgetMax}
                onChange={e => {
                  const next = parseInt(e.target.value);
                  setBudgetMax(Math.max(next, budgetMin));
                }}
                aria-label="Maximum budget"
              />
            </div>
            <span>₹5000</span>
          </div>
        </div>

      {/* Removed redundant "Specific Cravings" input:
          the chat input already provides free-text intent. */}
      </div>

      {/* Min Rating (always visible; removed More Options wrapper) */}
      <div className="rating-section">
        <p className="rating-label">⭐ Min Rating</p>
        <div className="rating-pills" role="group" aria-label="Minimum rating">
          {[3.0, 3.5, 4.0, 4.5].map(val => (
            <button
              key={val}
              type="button"
              className={`rating-pill${minRating === val ? ' active' : ''}`}
              onClick={() => setMinRating(val)}
              aria-pressed={minRating === val}
            >
              {val === 4.5 ? '4.5+' : val.toFixed(1)}
            </button>
          ))}
        </div>
        <input type="hidden" id="min-rating" value={minRating} readOnly />
      </div>

      <div style={{ display: 'flex', gap: '1.25rem', marginTop: '0.75rem', flexWrap: 'wrap' }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.875rem', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={!!onlineOrder}
            onChange={e => setOnlineOrder(e.target.checked ? true : null)}
          />
          Online order available
          <span style={{ color: 'var(--color-text-tertiary)', fontSize: '0.75rem' }}>
            ({dynamicOnlineCount})
          </span>
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.875rem', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={!!bookTable}
            onChange={e => setBookTable(e.target.checked ? true : null)}
          />
          Table booking
          <span style={{ color: 'var(--color-text-tertiary)', fontSize: '0.75rem' }}>
            ({dynamicBookCount})
          </span>
        </label>
      </div>

      {/* Error */}
      {formError && (
        <p style={{ color: 'var(--red)', fontSize: '0.82rem', marginTop: '0.5rem' }}>
          ⚠ {formError}
        </p>
      )}

      {/* CTA */}
      <button
        type="submit"
        id="submit-btn"
        className="cta-btn"
        disabled={loading}
      >
        {loading ? (
          <>
            <span style={{ width: 18, height: 18, border: '2px solid rgba(255,255,255,0.4)', borderTopColor: '#fff', borderRadius: '50%', display: 'inline-block', animation: 'spin 0.7s linear infinite' }} />
            Finding your spot…
          </>
        ) : (
          <>
            Get Recommendations
            <span className="btn-arrow">→</span>
          </>
        )}
      </button>
    </form>
  );
}
