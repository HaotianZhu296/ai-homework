/** Display helpers. Every field in the dataset can be missing, so each helper returns null when there is nothing to show. */

export function formatRuntime(seconds) {
  if (!Number.isFinite(seconds) || seconds <= 0) return null;
  const totalMinutes = Math.round(seconds / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours === 0) return `${minutes}m`;
  return minutes === 0 ? `${hours}h` : `${hours}h ${minutes}m`;
}

export function formatRating(rating) {
  if (rating === null || rating === undefined || rating === '') return null;
  const value = Number(rating);
  return Number.isFinite(value) ? value.toFixed(1) : null;
}

export function joinNames(names) {
  if (!Array.isArray(names)) return null;
  const clean = names.filter((n) => typeof n === 'string' && n.trim());
  return clean.length ? clean.join(', ') : null;
}

export function buildSearchUrl(baseUrl, query) {
  const base = (baseUrl || '').replace(/\/+$/, '');
  return `${base}/search?q=${encodeURIComponent(query)}`;
}
