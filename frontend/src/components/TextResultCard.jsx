// frontend/src/components/TextResultCard.jsx
import React from 'react';
import PropTypes from 'prop-types';
import DOMPurify from 'dompurify';

/* ────────────────────────────────────────────────────────────────────────────
   NEW: Build version for cache-busting
──────────────────────────────────────────────────────────────────────────── */
const APP_VERSION =
  process.env.REACT_APP_BUILD_VERSION || String(Date.now());

/* ────────────────────────────────────────────────────────────────────────────
   NEW: Feature flag to choose chapter destination
   '1' → use server-rendered chapter.html (chapter_url from backend)
   anything else / unset → use SPA route /chapter (ChapterPage.jsx)
──────────────────────────────────────────────────────────────────────────── */
const USE_SERVER_CHAPTER = process.env.REACT_APP_USE_SERVER_CHAPTER === '1';

/* ────────────────────────────────────────────────────────────────────────────
   Helper to append ?v=<version>
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

const TextResultCard = ({
  result,
  maxLines   = 10,
  bookTitle,
  singleResult = false,
  query        = '',
  searchType   = ''
}) => {
  /* ------------------------------------------------------------------ */
  /*   Pull fields from API payload                                      */
  /* ------------------------------------------------------------------ */
  const {
    snippet,
    chapter_url,            // backend-provided server template URL (legacy, filename-based)
    chapter_slug_url,       // NEW (b.4): backend-provided slug-based URL; preferred when present
    collection_folder,
    book_folder,
    section_filename,
    book_slug,              // NEW (b.4): exposed in case SPA route needs it later
    slug,                   // NEW (b.4): exposed in case SPA route needs it later
    parent_toc_title,       // CHANGED (b.5): journal sub-section breadcrumb from Pass-3; '' for TOC-level entries
    result_type,
    pdf_file,               // optional – legacy
    pdf_url,                // optional – preferred from backend
    start_page
  } = result;

  /* -------------------  Derive a friendly section title  ------------- */
  let sectionTitle = 'Untitled Section';
  if (section_filename) {
    const m = section_filename.match(/^[^_]+_\d+_(.+)\.txt$/);
    // CHANGED: double-underscore in the filename encodes a separator in the
    // original title (e.g. "Canto_Three__The_House..." was "Canto Three: The
    // House..."). Replace __ with " - " first so the rendered title reads
    // "Canto Three - The House..." instead of having an awkward double space.
    if (m && m[1]) sectionTitle = m[1].replace(/__/g, ' - ').replace(/_/g, ' ');
  }

  // CHANGED: for Savitri cantos, prepend the "Book N" prefix from
  // parent_toc_title (e.g. "Book Three — The Book of the Divine Mother")
  // so the hyperlink reads "Book Three, Canto Three: …" instead of just
  // "Canto Three: …". Triggers only when sectionTitle starts with "Canto"
  // and parent_toc_title starts with "Book", so other journal/diary books
  // with date-style parent_toc_titles are unaffected.
  const savitriBookMatch = parent_toc_title && parent_toc_title.match(/^(Book\s+\S+)/);
  const sectionTitleWithBook = savitriBookMatch && /^Canto\b/i.test(sectionTitle)
    ? `${savitriBookMatch[1]}, ${sectionTitle}`
    : sectionTitle;

  const title = singleResult && bookTitle
    ? `${bookTitle} - ${sectionTitleWithBook}`
    :  sectionTitleWithBook;

  // CHANGED: when the "Book N" prefix has been hoisted into the title, strip
  // it from the breadcrumb so the subtitle reads "The Book of the Divine
  // Mother" instead of repeating "Book Three — ...". Splits on em-dash with
  // optional surrounding spaces.
  const breadcrumb = (savitriBookMatch && /^Canto\b/i.test(sectionTitle))
    ? parent_toc_title.replace(/^Book\s+\S+\s*—\s*/, '')
    : parent_toc_title;

  /* -------------------------  Build chapter link  -------------------- */
  let chapterLink;

  if (USE_SERVER_CHAPTER && (chapter_slug_url || chapter_url)) {
    // ── OPTION A: server-rendered chapter.html
    // NEW (b.4): prefer slug-based URL (/read/<coll>/<book-slug>/<slug>) when
    // backend provided one; fall back to legacy filename-based chapter_url for
    // rows that predate slug emission.
    const sourceUrl = chapter_slug_url || chapter_url;
    try {
      const u = new URL(sourceUrl, window.location.origin);
      if (query)       u.searchParams.set('query', query);
      if (result_type) u.searchParams.set('result_type', result_type);
      if (searchType)  u.searchParams.set('search_type', searchType);
      u.searchParams.set('v', APP_VERSION);
      chapterLink = u.toString();
    } catch {
      const sep = sourceUrl.includes('?') ? '&' : '?';
      const params = [];
      if (query)       params.push(`query=${encodeURIComponent(query)}`);
      if (result_type) params.push(`result_type=${encodeURIComponent(result_type)}`);
      if (searchType)  params.push(`search_type=${encodeURIComponent(searchType)}`);
      params.push(`v=${encodeURIComponent(APP_VERSION)}`);
      chapterLink = sourceUrl + sep + params.join('&');
    }
  } else {
    // ── OPTION B: SPA route. Prefer /read/<coll>/<book_slug>/<slug> when both
    //    slugs are present (cleaner URL, matches prod chapter_slug_url). Fall
    //    back to /chapter?...&section_filename= for legacy rows missing a slug.
    // CHANGED: post-migration, App.jsx routes /read/:collection/:bookSlug/:slug
    //    through ChapterPage.jsx too, so this path is now safe in SPA mode.
    const coll = collection_folder || result.collection_folder;
    if (book_slug && slug && coll) {
      const base = `/read/${encodeURIComponent(coll)}` +
                   `/${encodeURIComponent(book_slug)}` +
                   `/${encodeURIComponent(slug)}`;
      const qs = new URLSearchParams();
      if (query)       qs.set('query', query);
      if (result_type) qs.set('result_type', result_type);
      if (searchType)  qs.set('search_type', searchType);
      qs.set('v', APP_VERSION);
      const queryString = qs.toString();
      chapterLink = queryString ? `${base}?${queryString}` : base;
    } else {
      const base = '/chapter';
      try {
        const u = new URL(base, window.location.origin);
        u.searchParams.set('collection_folder', coll);
        u.searchParams.set('book_folder',       book_folder       || result.book_folder);
        u.searchParams.set('section_filename',  section_filename);
        if (query)       u.searchParams.set('query', query);
        if (result_type) u.searchParams.set('result_type', result_type);
        if (searchType)  u.searchParams.set('search_type', searchType);
        u.searchParams.set('v', APP_VERSION);
        chapterLink = u.toString();
      } catch {
        const sep = base.includes('?') ? '&' : '?';
        const params = [
          `collection_folder=${encodeURIComponent(coll)}`,
          `book_folder=${encodeURIComponent(book_folder || result.book_folder)}`,
          `section_filename=${encodeURIComponent(section_filename)}`
        ];
        if (query)       params.push(`query=${encodeURIComponent(query)}`);
        if (result_type) params.push(`result_type=${encodeURIComponent(result_type)}`);
        if (searchType)  params.push(`search_type=${encodeURIComponent(searchType)}`);
        params.push(`v=${encodeURIComponent(APP_VERSION)}`);
        chapterLink = base + sep + params.join('&');
      }
    }
  }

  /* -------------------------  Build PDF link  ------------------------ */
  // CHANGED (2026-07-31): when the reader arrived via a search, send them to
  // /api/pdf_page, which finds the page their match is actually ON and
  // redirects the viewer there. `start_page` is the CHAPTER's first page, so on
  // a long chapter the old direct link landed them pages away from the text
  // they searched for (reported: page 485 for a hit on page 509). The backend
  // falls back to start_page whenever it can't locate the text, so this is
  // never worse. With no query there is nothing to locate — keep the direct
  // link and skip the extra request.
  let viewerLink = null;
  const pdfCollection = collection_folder || result.collection_folder;
  const pdfBookFolder = book_folder || result.book_folder;
  if (query && pdfCollection && pdfBookFolder && section_filename) {
    const qs = new URLSearchParams({
      collection_folder: pdfCollection,
      book_folder:       pdfBookFolder,
      section_filename:  section_filename,
      query:             query
    });
    viewerLink = withVersion(`/api/pdf_page?${qs.toString()}`);
  } else if (start_page !== undefined && start_page !== null) {
    if (pdf_url) {
      // Preferred: use pdf_url exactly as supplied by backend
      viewerLink = withVersion(
        `/viewer?file=${encodeURIComponent(pdf_url)}&page=${start_page}`
      );
    } else if (pdf_file) {
      // Legacy fallback
      const BACKEND =
        process.env.REACT_APP_BACKEND_PDF_URL || window.location.origin;
      const rawPdfUrl = `${BACKEND}/api/pdfs/${pdf_file}`.replace(/([^:]\/)\/+/g, '$1');
      viewerLink = withVersion(
        `/viewer?file=${encodeURIComponent(rawPdfUrl)}&page=${start_page}`
      );
    }
  }

  /* ------------------------  Prepare snippet HTML  ------------------- */
  //const sanitized   = DOMPurify.sanitize(snippet, { ALLOWED_TAGS: ['b', 'mark'] });
  const sanitized   = DOMPurify.sanitize(snippet, { ALLOWED_TAGS: ['b', 'mark', 'i', 'em'] });
  const lines       = sanitized.split(/<br\s*\/?>|\n/);
  const limited     = lines.slice(0, maxLines).join('<br/>') + (lines.length > maxLines ? '<br/>…' : '');

  /* ------------------------------------------------------------------ */
  /*                                JSX                                 */
  /* ------------------------------------------------------------------ */
  return (
    <div className="card mb-3">
      <div className="card-body position-relative">

        <h5 className="card-title">
          <a href={chapterLink} target="_blank" rel="noopener noreferrer">
            {title}
          </a>
        </h5>

        {/* CHANGED (b.5): one-line breadcrumb recovering the parent TOC entry
            buried by Pass-3 sub-section splitting (e.g. "March 14, 1952" for
            Mother Agenda, "Book Three — The Book of the Divine Mother" for a
            Savitri canto). Hidden when empty so non-journal/non-Savitri books
            are unaffected. CHANGED: dropped the "from " prefix — the breadcrumb
            already reads naturally on its own ("Book Three — ..."), and the
            extra word added clutter without disambiguating anything. */}
        {breadcrumb && (
          <div className="text-muted small fst-italic mb-2">
            {breadcrumb}
          </div>
        )}

        <p
          className="card-text"
          dangerouslySetInnerHTML={{ __html: limited }}
        />

        <div className="d-flex justify-content-between align-items-center">
          {result_type && (
            <small className="text-muted">
              {result_type.replace(/_/g, ' ')}
            </small>
          )}
          {viewerLink && (
            <a
              href={viewerLink}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-primary btn-sm"
            >
              Open&nbsp;PDF
            </a>
          )}
        </div>
      </div>
    </div>
  );
};

TextResultCard.propTypes = {
  result: PropTypes.shape({
    collection_folder: PropTypes.string,
    book_folder:       PropTypes.string,
    section_filename:  PropTypes.string.isRequired,
    snippet:           PropTypes.string.isRequired,
    chapter_url:       PropTypes.string, // legacy filename-based, used when USE_SERVER_CHAPTER=1
    chapter_slug_url:  PropTypes.string, // NEW (b.4): slug-based; preferred when present
    book_slug:         PropTypes.string, // NEW (b.4)
    slug:              PropTypes.string, // NEW (b.4)
    parent_toc_title:  PropTypes.string, // CHANGED (b.5): Pass-3 sub-section breadcrumb; may be '' or omitted
    result_type:       PropTypes.string,
    pdf_file:          PropTypes.string,
    pdf_url:           PropTypes.string,
    start_page:        PropTypes.oneOfType([PropTypes.string, PropTypes.number])
  }).isRequired,
  maxLines:     PropTypes.number,
  bookTitle:    PropTypes.string,
  singleResult: PropTypes.bool,
  query:        PropTypes.string,
  searchType:   PropTypes.string
};

export default TextResultCard;
