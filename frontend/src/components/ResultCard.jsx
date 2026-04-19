// frontend/src/components/ResultCard.jsx

import React from 'react';
import PropTypes from 'prop-types';
import DOMPurify from 'dompurify';
import { Link } from 'react-router-dom';

/* ────────────────────────────────────────────────────────────────────────────
   NEW: Build version used for cache‑busting. Set REACT_APP_BUILD_VERSION at
   build/deploy time (e.g., a git SHA or date). Fallback ensures development
   gets a per‑reload value, but in production you should set it explicitly.
──────────────────────────────────────────────────────────────────────────── */
const APP_VERSION =
  process.env.REACT_APP_BUILD_VERSION || String(Date.now());

/* ────────────────────────────────────────────────────────────────────────────
   NEW: Helper to append ?v=<version> (or &v=...) to any URL safely.
──────────────────────────────────────────────────────────────────────────── */
function withVersion(url) {
  try {
    const u = new URL(url, window.location.origin);
    u.searchParams.set('v', APP_VERSION);
    return u.toString();
  } catch {
    const sep = url.includes('?') ? '&' : '?';
    return `${url}${sep}v=${encodeURIComponent(APP_VERSION)}`;
  }
}
const ResultCard = ({ result, searchTerm, searchType, maxLines = 15 }) => {
  const { 
    book_title, 
    page_number, 
    pdf_url, 
    snippet, 
    distance 
  } = result;

  // Dynamically determine the backend base URL
  const BACKEND_BASE_URL =
    process.env.REACT_APP_BACKEND_PDF_URL || window.location.origin;

  // Generate the full PDF URL including the page number
  const pdfUrlWithPage = `${BACKEND_BASE_URL}${encodeURI(
    pdf_url.split('#page=')[0]
  )}#page=${page_number}`;

    // Generate the viewer link with the full file URL
  // ── CHANGED: wrap with withVersion() to force fresh load after deploys
  const viewerLink = withVersion(
    `/viewer?file=${encodeURIComponent(
      `${BACKEND_BASE_URL}${pdf_url.split('#')[0]}`
    )}&page=${page_number}`
  );


  // Generate the viewer link with the full file URL
  // const viewerLink = `/viewer?file=${encodeURIComponent(
  //  `${BACKEND_BASE_URL}${pdf_url.split('#')[0]}`
  // )}&page=${page_number}`;

  // Simplified snippet cleaner: just convert newlines to <br/>
  // and remove any completely empty lines. No merging short lines.
  const cleanSnippet = (snippet) => {
    return snippet
      .split('\n')
      .map(line => line.trim())
      .filter(line => line.length > 0)
      .join('<br/>');
  };

  const truncateSnippet = (htmlSnippet, maxLines) => {
    const lines = htmlSnippet.split('<br/>');
    if (lines.length > maxLines) {
      return lines.slice(0, maxLines).join('<br/>') + '<br/>...';
    }
    return htmlSnippet;
  };

  // Convert snippet
  const rawSnippet = snippet || 'No snippet available.';
  // Add highlighting for the searchTerm
  const highlightedSnippet = rawSnippet
    .replace(/\n/g, '\n')
    .replace(new RegExp(`(${searchTerm})`, 'gi'), '<mark>$1</mark>');

  // Clean and then truncate
  const cleaned = cleanSnippet(highlightedSnippet);
  const truncated = truncateSnippet(cleaned, maxLines);

  // Finally sanitize
  const sanitizedSnippet = DOMPurify.sanitize(truncated);

  // If the user did an 'all' search, show distance label
  let distanceLabel = '';
  //if (searchType === 'all') {
    if (distance === 0.0) {
      distanceLabel = 'Exact Match';
    } else if (distance === 0.1) {
      distanceLabel = 'All Words';
    } else if (distance === 0.2) {
      distanceLabel = 'Any Words';
    } else {
      const distValue = distance !== undefined ? distance.toFixed(2) : 'N/A';
      distanceLabel = `Semantic Match (${distValue})`;
    }
  //}

  // Build the title with page number in brackets, e.g. "Book Title [Page 33]"
  // We'll only show [Page X] if page_number is not undefined or 0
  const titleWithPage = page_number
    ? `${book_title || 'Untitled'}  -  page ${page_number}`
    : (book_title || 'Untitled');

  return (
    <div className="card mb-3">
      <div className="card-body">
        <h5 className="card-title">
          <a
            href={viewerLink}
            target="_blank"
            rel="noopener noreferrer"
            className="text-decoration-none"
          >
            {titleWithPage}
          </a>
        </h5>
        <p
          className="card-text"
          dangerouslySetInnerHTML={{ __html: sanitizedSnippet }}
        ></p>
        <div className="d-flex justify-content-between align-items-center">
          <Link to={viewerLink} target="_blank" className="btn btn-primary">
            Open PDF
          </Link>
        </div>
        {/* Only show distance label if searchType='all' */}
        <small className="text-muted">{distanceLabel}</small>
      </div>
    </div>
  );
};

ResultCard.propTypes = {
  result: PropTypes.shape({
    book_title: PropTypes.string,
    page_number: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    pdf_url: PropTypes.string,
    snippet: PropTypes.string,
    distance: PropTypes.number
  }).isRequired,
  searchTerm: PropTypes.string.isRequired,
  searchType: PropTypes.string,
  maxLines: PropTypes.number
};

export default ResultCard;
