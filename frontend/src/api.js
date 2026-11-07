import { buildSearchUrl } from './format.js';

const API_URL = import.meta.env.VITE_API_URL;

export async function searchMovies(query, { signal } = {}) {
  if (!API_URL) {
    throw new Error('VITE_API_URL is not set. Copy .env.example to .env and add the API URL.');
  }

  let response;
  try {
    response = await fetch(buildSearchUrl(API_URL, query), { signal });
  } catch (err) {
    if (err.name === 'AbortError') throw err;
    throw new Error('Could not reach the search service. Check your connection and try again.');
  }

  let data = null;
  try {
    data = await response.json();
  } catch {
    // Non-JSON error page; handled below.
  }

  if (!response.ok) {
    throw new Error(data?.error || `Search failed (HTTP ${response.status}).`);
  }
  return { results: data?.results ?? [], total: data?.total ?? 0 };
}
