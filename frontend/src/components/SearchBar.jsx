import { useEffect, useState } from 'react';

export default function SearchBar({ initialValue = '', loading, onSearch }) {
  const [value, setValue] = useState(initialValue);

  useEffect(() => setValue(initialValue), [initialValue]);

  function handleSubmit(event) {
    event.preventDefault();
    onSearch(value.trim());
  }

  return (
    <form className="search-bar" role="search" onSubmit={handleSubmit}>
      <input
        type="search"
        aria-label="Search movies by title"
        placeholder="Search movies by title…"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        autoFocus
      />
      <button type="submit" disabled={loading}>
        {loading ? 'Searching…' : 'Search'}
      </button>
    </form>
  );
}
