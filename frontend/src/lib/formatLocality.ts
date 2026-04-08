/** Display-only: catalog/API use lowercase locality slugs. */
export function formatLocalityDisplay(s: string): string {
  if (!s.trim()) return s;
  return s
    .split(/\s+/)
    .map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(' ');
}
