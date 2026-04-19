// frontend/src/services/api.js

// CHANGED: centralize axios config + safe defaults
import axios from 'axios';

// CHANGED: Prefer same-origin '/api' unless explicitly overridden (e.g., for local dev)
const API_BASE_URL = process.env.REACT_APP_BACKEND_URL || '/api';

// CHANGED: Build/version for cache-busting; stable across a deploy
const APP_VERSION = process.env.REACT_APP_BUILD_VERSION || String(Date.now());

// CHANGED: Small helper to append ?v=… (used by fetch-based calls)
function withVersion(url) {
  const sep = url.includes('?') ? '&' : '?';
  return `${url}${sep}v=${encodeURIComponent(APP_VERSION)}`;
}

// OPTIONAL: Axios instance (timeout + baseURL)
const http = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
});

// ─────────────────────────────────────────────────────────────
// NEW: One-shot singleton for /filters so multiple mounts don’t
// spam the endpoint. If it fails, we allow a retry next time.
// ─────────────────────────────────────────────────────────────
let filtersPromise = null;

/**
 * Fetches filter options from the backend.
 * CHANGED: adds cache-buster + singleton promise de-dupe
 */
export const fetchFilters = async () => {
  try {
    if (!filtersPromise) {
      filtersPromise = http
        .get('/filters', { params: { v: APP_VERSION } }) // cache-buster
        .then((res) => res.data)
        .catch((err) => {
          // reset so the next call can retry
          filtersPromise = null;
          throw err;
        });
    }
    return await filtersPromise;
  } catch (error) {
    // CHANGED: slightly richer logging
    console.error('Error fetching filters:', error?.response?.data || error.message);
    throw error;
  }
};

/**
 * Performs a search query with optional filters.
 * CHANGED: adds cache-buster so results (and file paths) don’t get cached across deploys.
 */
export const performSearch = async (query, filters, top_k = 50) => {
  try {
    const params = {
      query,
      author: filters.author,
      group: filters.group,
      book_title: filters.book_title,
      search_type: filters.search_type,
      top_k: filters.top_k || top_k,
      v: APP_VERSION, // cache-buster
    };
    const response = await http.get('/search', { params });
    return response.data;
  } catch (error) {
    console.error('Error performing search:', error?.response?.data || error.message);
    throw error;
  }
};

/**
 * Text-search (exact / all-words) over SQLite FTS
 * CHANGED: cache-buster + same-origin safety
 */
export async function performTextSearch(
  query,
  { author, group, book_title, search_type },
  limit = 50
) {
  const params = new URLSearchParams({ query, limit, mode: search_type, v: APP_VERSION });
  if (author) params.append('author', author);
  if (group) params.append('group', group);
  if (book_title) params.append('book_title', book_title);

  // NOTE: use same-origin path directly for fetch (works with nginx proxy_pass /api → backend)
  const res = await fetch(withVersion(`/api/text_search?${params.toString()}`));
  if (!res.ok) throw new Error('Text search failed');
  return res.json();
}

/**
 * AI query – CHANGED: adds cache-buster + same-origin by default
 */
export async function performAIQuery(query, model = 'openai', top_k = 4) {
  const params = new URLSearchParams({ query, model, top_k, v: APP_VERSION });

  // If API_BASE_URL is absolute (e.g., dev), use it; else same-origin
  const base = API_BASE_URL || '/api';
  const url = withVersion(`${base}/ai_search?${params.toString()}`);

  const res = await fetch(url);
  if (!res.ok) throw new Error('AI search failed');
  return res.json(); // { answer, sources }
}

// OPTIONAL: expose a way to clear the filters cache (e.g., when user changes collection set)
export function __clearFiltersCache() {
  filtersPromise = null;
}
