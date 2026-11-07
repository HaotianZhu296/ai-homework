import { describe, expect, it } from 'vitest';
import { buildSearchUrl, formatRating, formatRuntime, joinNames } from './format.js';

describe('formatRuntime', () => {
  it('formats hours and minutes like the sample UI', () => {
    expect(formatRuntime(7080)).toBe('1h 58m');
    expect(formatRuntime(8100)).toBe('2h 15m');
    expect(formatRuntime(7200)).toBe('2h');
    expect(formatRuntime(2700)).toBe('45m');
  });

  it('returns null for missing values', () => {
    expect(formatRuntime(undefined)).toBeNull();
    expect(formatRuntime(0)).toBeNull();
  });
});

describe('formatRating', () => {
  it('always shows one decimal, including integer ratings', () => {
    expect(formatRating(7.4)).toBe('7.4');
    expect(formatRating(7)).toBe('7.0');
  });

  it('returns null for missing values', () => {
    expect(formatRating(undefined)).toBeNull();
    expect(formatRating(null)).toBeNull();
  });
});

describe('joinNames', () => {
  it('joins names and skips blanks', () => {
    expect(joinNames(['A', '', 'B'])).toBe('A, B');
    expect(joinNames([])).toBeNull();
    expect(joinNames(undefined)).toBeNull();
  });
});

describe('buildSearchUrl', () => {
  it('encodes the query and tolerates a trailing slash', () => {
    expect(buildSearchUrl('https://x.test/prod/', "new year's eve")).toBe(
      'https://x.test/prod/search?q=new%20year\'s%20eve',
    );
    expect(buildSearchUrl('https://x.test/prod', 'a&b')).toBe('https://x.test/prod/search?q=a%26b');
  });
});
