import { useState } from 'react';
import { formatRating, formatRuntime, joinNames } from '../format.js';

function Poster({ src, title }) {
  const [failed, setFailed] = useState(false);
  if (!src || failed) {
    return (
      <div className="poster poster-placeholder" role="img" aria-label={`No poster for ${title}`}>
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M4 5h16v14H4z M4 9h16 M8 5v4 M12 5v4 M16 5v4" fill="none" stroke="currentColor" strokeWidth="1.5" />
        </svg>
      </div>
    );
  }
  return <img className="poster" src={src} alt={`${title} poster`} loading="lazy" onError={() => setFailed(true)} />;
}

export default function MovieCard({ movie }) {
  const rating = formatRating(movie.rating);
  const runtime = formatRuntime(movie.running_time_secs);
  const cast = joinNames(movie.actors);
  const directors = joinNames(movie.directors);
  const genres = Array.isArray(movie.genres) ? movie.genres : [];

  return (
    <article className="movie-card">
      <Poster src={movie.image_url} title={movie.title} />
      <div className="movie-info">
        <header className="movie-heading">
          <h2>{movie.title}</h2>
          {movie.year && <span className="year">{movie.year}</span>}
          {rating && (
            <span className="rating" aria-label={`Rating ${rating} out of 10`}>
              ★ {rating}
            </span>
          )}
          {runtime && <span className="runtime">{runtime}</span>}
        </header>

        {genres.length > 0 && (
          <ul className="genres" aria-label="Genres">
            {genres.map((genre) => (
              <li key={genre}>{genre}</li>
            ))}
          </ul>
        )}

        {movie.plot && <p className="plot">{movie.plot}</p>}
        {cast && (
          <p className="credits">
            <strong>Cast:</strong> {cast}
          </p>
        )}
        {directors && (
          <p className="credits">
            <strong>{movie.directors.length > 1 ? 'Directors' : 'Director'}:</strong> {directors}
          </p>
        )}
      </div>
    </article>
  );
}
