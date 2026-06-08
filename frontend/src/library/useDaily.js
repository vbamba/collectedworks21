// frontend/src/library/useDaily.js
// CHANGED: home/daily "thought of the day" now comes from /api/daily (an
// editable curated JSON on the backend) instead of stub data. Date-seeded so
// every visitor sees the same message on a given day.
import { useState, useEffect } from 'react';

let _cache = null;
let _promise = null;

export function loadDaily() {
  if (_cache) return Promise.resolve(_cache);
  if (!_promise) {
    _promise = fetch('/api/daily')
      .then((r) => { if (!r.ok) throw new Error('daily'); return r.json(); })
      .then((d) => { _cache = Array.isArray(d.messages) ? d.messages : []; return _cache; })
      .catch((e) => { _promise = null; throw e; });
  }
  return _promise;
}

export function useDaily() {
  const [messages, setMessages] = useState(_cache || []);
  useEffect(() => {
    let alive = true;
    loadDaily().then((d) => { if (alive) setMessages(d); }).catch(() => {});
    return () => { alive = false; };
  }, []);
  return messages;
}

// Deterministic day-of-year index so the message is stable for everyone today.
export function todayIndex(len) {
  if (!len) return 0;
  const now = new Date();
  const start = new Date(now.getFullYear(), 0, 0);
  const day = Math.floor((now - start) / 86400000);
  return day % len;
}
