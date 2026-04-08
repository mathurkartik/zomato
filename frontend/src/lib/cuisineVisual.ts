/**
 * Deterministic visuals (photo + gradient + emoji) from restaurant cuisine tags.
 * Same cuisine always maps to the same assets — not card index.
 */

export interface CuisineVisual {
  /** Curated Unsplash food photo (stable URL) */
  imageUrl: string;
  /** Fallback / overlay gradient */
  gradient: string;
  emoji: string;
}

const U = (id: string) =>
  `https://images.unsplash.com/${id}?auto=format&fit=crop&w=900&q=80`;

/* ── Category buckets (order: more specific phrases first) ───────── */
const CATEGORIES: {
  keys: string[];
  image: string;
  gradient: string;
  emoji: string;
}[] = [
  {
    keys: ['north indian', 'biryani', 'kebab', 'mughlai', 'awadhi', 'punjabi', 'rajasthani'],
    image: U('photo-1585937421612-70a008356fbe'),
    gradient: 'linear-gradient(135deg, #bf360c 0%, #e65100 45%, #ffcc80 100%)',
    emoji: '🍛',
  },
  {
    keys: ['south indian', 'bengali', 'mangalorean', 'kerala', 'chettinad', 'andhra'],
    image: U('photo-1630383249896-424e84df8a32'),
    gradient: 'linear-gradient(135deg, #1b5e20 0%, #43a047 50%, #c8e6c9 100%)',
    emoji: '🍽️',
  },
  {
    keys: ['chinese', 'cantonese', 'szechuan'],
    image: U('photo-1563245372-f21724e3856d'),
    gradient: 'linear-gradient(135deg, #b71c1c 0%, #d32f2f 55%, #ffcdd2 100%)',
    emoji: '🥡',
  },
  {
    keys: ['japanese', 'sushi'],
    image: U('photo-1579584425555-18a626b9d289'),
    gradient: 'linear-gradient(135deg, #311b92 0%, #5e35b1 50%, #d1c4e9 100%)',
    emoji: '🍣',
  },
  {
    keys: ['thai', 'vietnamese', 'asian', 'momos', 'tibetan'],
    image: U('photo-1559314809-0d155014e29e'),
    gradient: 'linear-gradient(135deg, #006064 0%, #00838f 50%, #b2ebf2 100%)',
    emoji: '🍜',
  },
  {
    keys: ['italian', 'pizza'],
    image: U('photo-1574071318508-1cdbab80d002'),
    gradient: 'linear-gradient(135deg, #33691e 0%, #558b2f 50%, #f1f8e9 100%)',
    emoji: '🍕',
  },
  {
    keys: ['mexican', 'tex-mex'],
    image: U('photo-1565299585323-381aab226026'),
    gradient: 'linear-gradient(135deg, #e65100 0%, #fb8c00 50%, #ffe0b2 100%)',
    emoji: '🌮',
  },
  {
    keys: ['burger', 'american', 'fast food', 'finger food', 'sandwich', 'rolls', 'street food'],
    image: U('photo-1550547660-d9450f859349'),
    gradient: 'linear-gradient(135deg, #4e342e 0%, #6d4c41 50%, #d7ccc8 100%)',
    emoji: '🍔',
  },
  {
    keys: ['seafood', 'fish'],
    image: U('photo-1559339352-11d035aa65de'),
    gradient: 'linear-gradient(135deg, #01579b 0%, #0277bd 50%, #b3e5fc 100%)',
    emoji: '🦐',
  },
  {
    keys: ['steak', 'bbq', 'charcoal chicken', 'grill'],
    image: U('photo-1529193591184-425a6c1efd1c'),
    gradient: 'linear-gradient(135deg, #3e2723 0%, #5d4037 50%, #d7ccc8 100%)',
    emoji: '🥩',
  },
  {
    keys: ['cafe', 'coffee', 'tea', 'beverages', 'juices', 'juice', 'bakery'],
    image: U('photo-1495474472287-4d71bcdd2085'),
    gradient: 'linear-gradient(135deg, #4e342e 0%, #795548 50%, #efebe9 100%)',
    emoji: '☕',
  },
  {
    keys: ['desserts', 'ice cream', 'mithai', 'cake'],
    image: U('photo-1551024506-0bccd828d307'),
    gradient: 'linear-gradient(135deg, #880e4f 0%, #c2185b 50%, #f8bbd9 100%)',
    emoji: '🍰',
  },
  {
    keys: ['salad', 'healthy food'],
    image: U('photo-1512621776951-a57141f2eedd'),
    gradient: 'linear-gradient(135deg, #1b5e20 0%, #43a047 50%, #c8e6c9 100%)',
    emoji: '🥗',
  },
  {
    keys: ['mediterranean', 'lebanese', 'arabian', 'middle eastern'],
    image: U('photo-1541518763669-27fef04b14ea'),
    gradient: 'linear-gradient(135deg, #f57f17 0%, #fbc02d 50%, #fff9c4 100%)',
    emoji: '🥙',
  },
  {
    keys: ['european', 'continental', 'french'],
    image: U('photo-1414235077428-338989a2e8c0'),
    gradient: 'linear-gradient(135deg, #37474f 0%, #546e7a 50%, #cfd8dc 100%)',
    emoji: '🍝',
  },
  {
    keys: ['maharashtrian', 'gujarati', 'goan'],
    image: U('photo-1601050690597-df0568f70950'),
    gradient: 'linear-gradient(135deg, #e65100 0%, #fb8c00 50%, #ffe0b2 100%)',
    emoji: '🍴',
  },
];

const DEFAULT: CuisineVisual = {
  imageUrl: U('photo-1504674900247-0877df9cc836'),
  gradient: 'linear-gradient(135deg, #c62828 0%, #e53935 40%, #ffcdd2 100%)',
  emoji: '🍽️',
};

const FALLBACKS: CuisineVisual[] = [
  DEFAULT,
  {
    imageUrl: U('photo-1546069901-ba9599a7e63c'),
    gradient: 'linear-gradient(135deg, #1565c0 0%, #42a5f5 50%, #e3f2fd 100%)',
    emoji: '🥘',
  },
  {
    imageUrl: U('photo-1476224203421-9ac39bcb3327'),
    gradient: 'linear-gradient(135deg, #2e7d32 0%, #66bb6a 50%, #e8f5e9 100%)',
    emoji: '🍲',
  },
  {
    imageUrl: U('photo-1504754524776-8f4f37790ca0'),
    gradient: 'linear-gradient(135deg, #6a1b9a 0%, #ab47bc 50%, #f3e5f5 100%)',
    emoji: '🍱',
  },
];

function hashPick(s: string): CuisineVisual {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return FALLBACKS[h % FALLBACKS.length]!;
}

function normalizeToken(t: string): string {
  return t.trim().toLowerCase();
}

/**
 * Pick visual from API cuisine list (first token drives the theme; checks all for keyword match).
 */
export function getCuisineVisual(cuisines: string[] | undefined | null): CuisineVisual {
  if (!cuisines?.length) return DEFAULT;

  const tokens = cuisines.map(normalizeToken).filter(Boolean);
  const blob = tokens.join(' ');

  for (const cat of CATEGORIES) {
    for (const key of cat.keys) {
      for (const tok of tokens) {
        if (tok === key || tok.includes(key) || key.includes(tok) || blob.includes(key)) {
          return { imageUrl: cat.image, gradient: cat.gradient, emoji: cat.emoji };
        }
      }
    }
  }

  return hashPick(tokens[0] || blob);
}

/** Hero / preview: single cuisine slug from dropdown */
export function getCuisineVisualFromSlug(slug: string | undefined | null): CuisineVisual {
  if (!slug?.trim()) return DEFAULT;
  return getCuisineVisual([slug]);
}
