// frontend/src/components/NavBar.jsx
// CHANGED: global sticky nav rendered above <Routes> in App.js. Replaces
// the per-page <header className="page-header"> banners (which only
// appeared on Search/Question pages and left chapter pages with no way
// to switch books). The nav surfaces three actions:
//   Search   → / (text search, the primary use case)
//   Books    → opens BooksMenu modal (new book quick-picker)
//   Question → /question (semantic search; deprioritized to the right
//              because most users only rely on text search)
// SearchBar's inline "Ask a Question" link was retired in the same change
// since this navbar entry covers it.
// Bootstrap CSS-only navbar — the toggler/collapse are managed via React
// state instead of data-bs-toggle because the project doesn't bundle the
// Bootstrap JS (only the CSS, see App.js).

import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import BooksMenu from './BooksMenu';
import './NavBar.css';

export default function NavBar() {
  // CHANGED: navOpen drives the mobile-collapsed menu show/hide. On md+
  // (≥768px) the .navbar-collapse is always visible regardless of state
  // because Bootstrap's .navbar-expand-md overrides display.
  const [navOpen, setNavOpen] = useState(false);
  const [showBooks, setShowBooks] = useState(false);
  const location = useLocation();

  // CHANGED: collapse the mobile menu after a nav action so the next page
  // doesn't render with a stray expanded panel covering its content.
  const closeNav = () => setNavOpen(false);

  // CHANGED: highlight the current section so users have spatial context
  // for which page they're on. Active for / and /searchtext (both render
  // text search), and /question and /chat (both render semantic).
  const isSearch = location.pathname === '/' || location.pathname === '/searchtext';
  const isQuestion = location.pathname === '/question' || location.pathname === '/chat';

  return (
    <>
      <nav className="navbar navbar-expand-md navbar-light bg-white border-bottom sticky-top collected-navbar">
        <div className="container-fluid px-3">
          <Link to="/" className="navbar-brand" onClick={closeNav}>
            <img
              src="/images/sri_ma.jpg"
              alt=""
              className="navbar-logo"
            />
            <span className="navbar-title">Collected Works of Sri Aurobindo and The Mother</span>
          </Link>
          <button
            type="button"
            className="navbar-toggler"
            aria-controls="mainNav"
            aria-expanded={navOpen}
            aria-label="Toggle navigation"
            onClick={() => setNavOpen(!navOpen)}
          >
            <span className="navbar-toggler-icon" />
          </button>
          <div
            id="mainNav"
            className={`collapse navbar-collapse${navOpen ? ' show' : ''}`}
          >
            <ul className="navbar-nav ms-auto">
              <li className="nav-item">
                <Link
                  to="/"
                  // CHANGED: push a fresh focusInput stamp on every click
                  // so SearchBar re-focuses its input even when the user
                  // is already on / (no remount → useEffect needs a new
                  // value to re-fire). Date.now() guarantees uniqueness
                  // across rapid clicks.
                  state={{ focusInput: Date.now() }}
                  className={`nav-link${isSearch ? ' active' : ''}`}
                  onClick={closeNav}
                >
                  Search
                </Link>
              </li>
              <li className="nav-item">
                <button
                  type="button"
                  className="nav-link nav-button"
                  onClick={() => { setShowBooks(true); closeNav(); }}
                >
                  Books
                </button>
              </li>
              {/* CHANGED: Savitri wiki link. External href (separate
                  subdomain), opens in a new tab. URL comes from
                  REACT_APP_SAVITRI_WIKI_URL so dev can point at a local
                  static server while prod points at the subdomain. */}
              {process.env.REACT_APP_SAVITRI_WIKI_URL && (
                <li className="nav-item">
                  <a
                    href={process.env.REACT_APP_SAVITRI_WIKI_URL}
                    className="nav-link"
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={closeNav}
                  >
                    Savitri Study
                  </a>
                </li>
              )}
              {/* CHANGED: Question link hidden — semantic-search UX is
                  being rebuilt. Route /question still exists; restore this
                  <li> when the new version is ready. */}
              {false && (
                <li className="nav-item">
                  <Link
                    to="/question"
                    state={{ focusInput: Date.now() }}
                    className={`nav-link${isQuestion ? ' active' : ''}`}
                    onClick={closeNav}
                  >
                    Question
                  </Link>
                </li>
              )}
            </ul>
          </div>
        </div>
      </nav>
      <BooksMenu show={showBooks} onClose={() => setShowBooks(false)} />
    </>
  );
}
