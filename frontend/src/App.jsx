import { useCallback, useEffect, useRef, useState } from 'react';
import SearchBar from './components/SearchBar.jsx';
import MovieCard from './components/MovieCard.jsx';
import { searchMovies } from './api.js';

const EXAMPLES = ['new', 'star', 'love', 'dark knight'];

function initialQuery() {
  return new URLSearchParams(window.location.search).get('q')?.trim() ?? '';
}

function syncUrl(query) {
  const url = new URL(window.location.href);
  if (query) url.searchParams.set('q', query);
  else url.searchParams.delete('q');
  window.history.replaceState(null, '', url);
}

export default function App() {
  const [query, setQuery] = useState(initialQuery);
  // status: idle | loading | success | error
  const [state, setState] = useState({ status: 'idle', results: [], total: 0, error: null });
  const controllerRef = useRef(null);

  const runSearch = useCallback(async (q) => {
    setQuery(q);
    syncUrl(q);
    controllerRef.current?.abort();

    if (!q) {
      setState({ status: 'error', results: [], total: 0, error: 'Please enter a movie title to search.' });
      return;
    }

    const controller = new AbortController();
    controllerRef.current = controller;
    setState((s) => ({ ...s, status: 'loading', error: null }));
    try {
      const { results, total } = await searchMovies(q, { signal: controller.signal });
      setState({ status: 'success', results, total, error: null });
    } catch (err) {
      if (err.name === 'AbortError') return;
      setState({ status: 'error', results: [], total: 0, error: err.message });
    }
  }, []);

  useEffect(() => {
    if (query) runSearch(query);
    return () => controllerRef.current?.abort();
    // Run once for a ?q= in the URL.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const { status, results, total, error } = state;
  const loading = status === 'loading';

  return (
    <main className="app">
      <h1>Movie Search</h1>
      <SearchBar initialValue={query} loading={loading} onSearch={runSearch} />

      <section aria-live="polite" aria-busy={loading}>
        {status === 'idle' && (
          <div className="hint">
            <p>Search 1,250 movies by title. Try:</p>
            <div className="examples">
              {EXAMPLES.map((example) => (
                <button key={example} type="button" onClick={() => runSearch(example)}>
                  {example}
                </button>
              ))}
            </div>
          </div>
        )}

        {loading && (
          <div className="loading" role="status">
            <span className="spinner" aria-hidden="true" />
            Searching for “{query}”…
          </div>
        )}

        {status === 'error' && (
          <div className="message error" role="alert">
            <p>{error}</p>
            {query && (
              <button type="button" onClick={() => runSearch(query)}>
                Try again
              </button>
            )}
          </div>
        )}

        {status === 'success' && results.length === 0 && (
          <div className="message empty" role="alert">
            <p>
              No movies found for “{query}”. Try a different title or fewer words.
            </p>
          </div>
        )}

        {status === 'success' && results.length > 0 && (
          <>
            <p className="summary">
              {total === results.length
                ? `${total} ${total === 1 ? 'result' : 'results'}`
                : `Showing top ${results.length} of ${total} results`}{' '}
              for “{query}”
            </p>
            <div className="results">
              {results.map((movie) => (
                <MovieCard key={movie.id} movie={movie} />
              ))}
            </div>
          </>
        )}
      </section>
    </main>
  );
}
