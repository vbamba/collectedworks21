// frontend/src/components/BooksMenu.jsx
// CHANGED: book quick-picker modal opened from the global NavBar's "Books"
// button. Calls /api/books once on first open, caches in component state
// for the session, then renders a filterable list grouped by author. A
// row click opens the book's first content chapter via /read/<coll>/<book>/<slug>;
// a separate "PDF" link to the right opens the source PDF in a new tab.
//
// Uses react-modal (already a project dep — see ResultCardModal.jsx) for
// consistency rather than introducing a Bootstrap-JS modal that the
// project doesn't currently bundle.

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Modal from 'react-modal';
import './BooksMenu.css';

// CHANGED: collection_folder → display name. Three values cover all 91
// served books (sriaurobindo, mother, disciples); the malformed
// Nolini-Kanta-Gupta-Seer-Poets row is filtered server-side.
const COLLECTION_LABEL = {
  sriaurobindo: 'Sri Aurobindo',
  mother: 'The Mother',
  disciples: 'Disciples',
};

// CHANGED: render Disciples books in collection order (Sri Aurobindo →
// Mother → Disciples) so the user's most likely target appears first.
const COLLECTION_ORDER = ['sriaurobindo', 'mother', 'disciples'];

// CHANGED: build a /viewer?file=...&v=... URL the same way TextResultCard
// does (~line 148) so the PDF opens through the in-app PdfViewer chrome
// instead of the browser dumping the raw PDF stream. We omit `page` so
// PdfViewer defaults to page 1 — the picker has no per-section context.
const APP_VERSION = process.env.REACT_APP_BUILD_VERSION || String(Date.now());

function buildViewerUrl(pdfUrl) {
  if (!pdfUrl) return '';
  return `/viewer?file=${encodeURIComponent(pdfUrl)}&v=${encodeURIComponent(APP_VERSION)}`;
}

export default function BooksMenu({ show, onClose }) {
  const [books, setBooks] = useState(null);  // null = not loaded yet
  const [error, setError] = useState('');
  const [filter, setFilter] = useState('');
  const filterRef = useRef(null);
  const navigate = useNavigate();

  // CHANGED: lazy-load on first open. /api/books is cached server-side
  // against chapters.db's mtime, but we still cache in component state
  // so reopening the modal in the same session is instant.
  useEffect(() => {
    if (!show || books !== null) return;
    fetch('/api/books')
      .then(res => {
        if (!res.ok) throw new Error('Failed to load books');
        return res.json();
      })
      .then(setBooks)
      .catch(err => setError(err.message));
  }, [show, books]);

  // CHANGED: autofocus the filter input so the user can start typing
  // immediately on open. Defer one tick because react-modal mounts the
  // input asynchronously and focus() before mount silently no-ops.
  useEffect(() => {
    if (show) {
      const t = setTimeout(() => filterRef.current?.focus(), 50);
      return () => clearTimeout(t);
    }
    // CHANGED: clear the filter on close so the next open starts fresh.
    setFilter('');
  }, [show]);

  // CHANGED: client-side substring filter against title + author. With
  // ~91 entries this is instant; a 100KB JSON download covers it. Author
  // is included because Disciples titles often start with the author
  // name ("Nirodbaran - Talks…") so typing "nirod" should match.
  const filtered = useMemo(() => {
    if (!books) return [];
    const q = filter.trim().toLowerCase();
    if (!q) return books;
    return books.filter(b =>
      b.title.toLowerCase().includes(q) ||
      (b.author || '').toLowerCase().includes(q)
    );
  }, [books, filter]);

  // CHANGED: group by collection_folder using COLLECTION_LABEL for the
  // section heading. We keep an explicit order (Sri Aurobindo first)
  // rather than alphabetical so the heading order doesn't shuffle when
  // the user filters down to one collection's results.
  const grouped = useMemo(() => {
    const out = new Map();
    for (const c of COLLECTION_ORDER) out.set(c, []);
    for (const b of filtered) {
      if (!out.has(b.collection)) out.set(b.collection, []);
      out.get(b.collection).push(b);
    }
    return out;
  }, [filtered]);

  const openBook = (book) => {
    onClose();
    navigate(
      `/read/${encodeURIComponent(book.collection)}` +
      `/${encodeURIComponent(book.book_slug)}` +
      `/${encodeURIComponent(book.first_slug)}`
    );
  };

  // CHANGED: keyboard nav — Enter opens the first filtered result so a
  // user can type "savi" + Enter without reaching for the mouse. Esc is
  // already handled by react-modal's onRequestClose.
  const onFilterKeyDown = (e) => {
    if (e.key === 'Enter' && filtered.length > 0) {
      e.preventDefault();
      openBook(filtered[0]);
    }
  };

  return (
    <Modal
      isOpen={show}
      onRequestClose={onClose}
      contentLabel="Open a book"
      // CHANGED: react-modal uses inline style overrides; class-based
      // styling would require unstyled portal classes. Keep layout here
      // so BooksMenu.css can focus on the inner row/group styling.
      className="books-menu-content"
      overlayClassName="books-menu-overlay"
      ariaHideApp={false}
    >
      <div className="books-menu-header">
        <input
          ref={filterRef}
          type="text"
          className="form-control books-menu-filter"
          placeholder="Type a book or author…"
          value={filter}
          onChange={e => setFilter(e.target.value)}
          onKeyDown={onFilterKeyDown}
          aria-label="Filter books"
        />
        <button
          type="button"
          className="btn-close ms-2"
          aria-label="Close"
          onClick={onClose}
        />
      </div>

      <div className="books-menu-body">
        {error && (
          <div className="alert alert-danger m-3">{error}</div>
        )}
        {!books && !error && (
          <div className="text-muted p-3">Loading…</div>
        )}
        {books && filtered.length === 0 && (
          <div className="text-muted p-3">No books match "{filter}".</div>
        )}
        {books && filtered.length > 0 && (
          <>
            {[...grouped.entries()].map(([collection, items]) => {
              if (items.length === 0) return null;
              const label = COLLECTION_LABEL[collection] || collection;
              return (
                <section key={collection} className="books-menu-group">
                  <h6 className="books-menu-group-title">
                    {label} <span className="text-muted">({items.length})</span>
                  </h6>
                  <ul className="list-unstyled mb-0">
                    {items.map(b => (
                      <li key={`${b.collection}|${b.book_folder}`}
                          className="books-menu-row">
                        <button
                          type="button"
                          className="books-menu-row-main"
                          onClick={() => openBook(b)}
                        >
                          <span className="books-menu-row-title">{b.title}</span>
                        </button>
                        {b.pdf_url && (
                          <a
                            href={buildViewerUrl(b.pdf_url)}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="books-menu-row-pdf"
                            aria-label={`Open PDF of ${b.title} in a new tab`}
                            // CHANGED: stop the click from also opening
                            // the chapter view (event would bubble to
                            // <li> if we wired the row click there).
                            onClick={(e) => e.stopPropagation()}
                          >
                            PDF
                          </a>
                        )}
                      </li>
                    ))}
                  </ul>
                </section>
              );
            })}
          </>
        )}
      </div>
    </Modal>
  );
}
