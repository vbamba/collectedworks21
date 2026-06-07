// frontend/src/library/useBooks.js
// CHANGED (Phase 3d): real book list for the Library shelf, from /api/books.
// Cached as a module singleton so Home, Browse, Volume and the menu drawer
// share one fetch.
import { useState, useEffect } from 'react';

let _cache = null;
let _promise = null;

export function loadBooks() {
  if (_cache) return Promise.resolve(_cache);
  if (!_promise) {
    _promise = fetch('/api/books')
      .then((r) => { if (!r.ok) throw new Error('books'); return r.json(); })
      .then((d) => { _cache = Array.isArray(d) ? d : []; return _cache; })
      .catch((e) => { _promise = null; throw e; });
  }
  return _promise;
}

export function useBooks() {
  const [books, setBooks] = useState(_cache || []);
  useEffect(() => {
    let alive = true;
    loadBooks().then((d) => { if (alive) setBooks(d); }).catch(() => {});
    return () => { alive = false; };
  }, []);
  return books;
}

// Map a backend author name to the sigil/colour code the design uses.
export function authorCode(author) {
  if (!author) return 'd';
  if (/mother/i.test(author)) return 'm';
  if (/aurobindo/i.test(author)) return 'sa';
  return 'd';
}

const COLLECTION_NAMES = {
  CWSA: 'Complete Works of Sri Aurobindo',
  CWM: 'Collected Works of The Mother',
  Agenda: "Mother's Agenda",
  Disciples: 'Works of the Disciples',
};
export function collectionFullName(group) {
  return COLLECTION_NAMES[group] || group;
}

const GROUP_ORDER = ['CWSA', 'CWM', 'Agenda', 'Disciples'];

// Group the flat book list into collections (by backend group_name).
export function deriveCollections(books) {
  const map = new Map();
  for (const b of books) {
    const g = b.group_name || 'Other';
    if (!map.has(g)) map.set(g, { name: g, count: 0, author: authorCode(b.author) });
    map.get(g).count += 1;
  }
  const list = [...map.values()];
  list.sort((a, b) => {
    const ia = GROUP_ORDER.indexOf(a.name); const ib = GROUP_ORDER.indexOf(b.name);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
  });
  return list;
}
