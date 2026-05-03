// frontend/src/pages/ChapterPage.jsx
import React, { useState, useEffect, useMemo, useRef, useLayoutEffect } from 'react';
// CHANGED: also import useParams so this component can serve both URL shapes
//   /chapter?collection_folder=X&book_folder=Y&section_filename=Z   (legacy / query)
//   /read/:collection/:bookSlug/:slug                               (slug, post-migration)
// The slug shape used to be served exclusively by Flask's chapter.html
// template. We now route it through this component so all chapter rendering
// goes through one code path.
import { useSearchParams, useParams, Link } from 'react-router-dom';
import DOMPurify from 'dompurify';
import Mark from 'mark.js';
const MarkClass = Mark.default || Mark;

// Stop-words (same as backend)
const STOPWORDS = new Set([
  'a','an','and','are','as','at','be','but','by','for','from','had','has','have',
  'he','her','his','in','is','it','its','of','on','or','she','that','the','their',
  'there','they','to','was','were','which','will','with','would','this','those',
  'these','your','you','i','we','our','us'
]);

// CHANGED: matches a verse line that ends a sentence — .?! optionally
// followed by a closing quote/paren, then optional trailing whitespace.
// Used for Savitri's render-time sentence-stanza splitting (see htmlContent
// useMemo). Module-scoped so it's a single shared regex, not re-allocated
// per render, and so React's exhaustive-deps lint doesn't flag it.
const SENTENCE_END_RE = /[.?!][)"'”’]?\s*$/;

// NEW: normalize ligatures/nbsp & collapse whitespace (client-side)
function normalizeCompat(str) {
  if (!str) return '';
  return str
    .replace(/\uFB01/g, 'fi')  // ﬁ
    .replace(/\uFB02/g, 'fl')  // ﬂ
    .replace(/\u00A0/g, ' ')   // nbsp
    .replace(/\s+/g, ' ');
}
// NEW: ligature-aware escape
function ligatureRegexEscape(str) {
  const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return esc(str)
    .replace(/fi/gi, '(?:fi|\\uFB01)')
    .replace(/fl/gi, '(?:fl|\\uFB02)');
}

const ChapterPage = () => {
  const [searchParams]    = useSearchParams();
  // CHANGED: useParams returns {} when the matched route has no path params
  // (i.e. the /chapter route), and {collection, bookSlug, slug} on the new
  // /read/:collection/:bookSlug/:slug route. slugMode picks the data flow.
  const routeParams        = useParams();
  const slugMode           = !!(routeParams.collection && routeParams.bookSlug && routeParams.slug);

  // Effective identifiers used by the rest of the component.
  // - slug mode: the path tells us which collection + book_slug + slug to load,
  //   and the backend resolves to (book_folder, section_filename) internally.
  //   We don't have book_folder/section_filename until the API responds, so we
  //   only carry the slug-form fields and use them to build /read/... nav URLs.
  // - query mode: the URL already carries collection_folder/book_folder/section_filename
  //   so behavior matches the pre-migration component exactly.
  const collection         = slugMode ? routeParams.collection : searchParams.get('collection_folder');
  const bookFolder         = slugMode ? null : searchParams.get('book_folder');
  const sectionFilename    = slugMode ? null : searchParams.get('section_filename');
  const bookSlug           = slugMode ? routeParams.bookSlug : '';
  const slug               = slugMode ? routeParams.slug : '';
  const phrase             = (searchParams.get('query') || '').trim();
  const resultType         = (searchParams.get('result_type') || 'all').toLowerCase(); // NEW

  const [blocks, setBlocks]         = useState([]);
  const [bookTitle, setBookTitle]   = useState('');
  const [prevSection, setPrevSection] = useState(null);
  const [nextSection, setNextSection] = useState(null);
  // CHANGED (2026-04-19): First/Last boundary nav — lets the reader jump to
  // chapter 1 or the final chapter without clicking prev/next repeatedly.
  const [firstSection, setFirstSection] = useState(null);
  const [lastSection, setLastSection]   = useState(null);
  // CHANGED: parallel slug-form nav targets returned by /api/chapter. When
  // slugMode is true the nav links are built as /read/.../<slug>; when a slug
  // is missing (legacy row predating the slug column) we fall back to the
  // section_filename + /chapter?... URL.
  const [prevSlug, setPrevSlug] = useState('');
  const [nextSlug, setNextSlug] = useState('');
  const [firstSlug, setFirstSlug] = useState('');
  const [lastSlug, setLastSlug] = useState('');
  // CHANGED: resolved book_folder for the /chapter?... fallback URL when the
  // current section has no slug (legacy rows). In slug mode we don't know
  // book_folder, but slug-mode nav builds /read/... URLs that don't need it,
  // so this stays empty there. In query mode it mirrors the URL's
  // book_folder param.
  const [resolvedBookFolder, setResolvedBookFolder] = useState('');
  // CHANGED (b.5): hold Pass-3 journal sub-section breadcrumb (e.g. "March 14,
  // 1952") returned by /api/chapter so the header can render "from <parent>".
  const [parentTocTitle, setParentTocTitle] = useState('');
  // CHANGED (2026-04-20): reflow flag from /api/chapter. When false (verse, e.g.
  // Savitri), lines must be joined with <br/> to preserve the poet's breaks;
  // when true the block was prose-reflowed server-side and can be joined with
  // a space so the browser handles word-wrap. Default true keeps old prose
  // behavior if an older backend returns no flag.
  const [reflowed, setReflowed]     = useState(true);
  const [error, setError]           = useState('');
  const contentRef                  = useRef(null);

  // Fetch blocks + metadata
  useEffect(() => {
    // CHANGED: choose endpoint based on URL shape.
    //   slug mode → /api/chapter_by_slug?collection=...&book_slug=...&slug=...
    //               (Flask returns a 307 redirect to /api/chapter, fetch follows
    //                it transparently and we get the same JSON shape back)
    //   query mode → /api/chapter?collection_folder=...&book_folder=...&section_filename=...
    let url;
    if (slugMode) {
      // CHANGED: param name is `collection_folder` (matches /api/chapter); the
      // /api/chapter_by_slug endpoint validates this exact key and 400s otherwise.
      url = `/api/chapter_by_slug?collection_folder=${encodeURIComponent(collection)}` +
            `&book_slug=${encodeURIComponent(bookSlug)}` +
            `&slug=${encodeURIComponent(slug)}`;
    } else if (collection && bookFolder && sectionFilename) {
      url = `/api/chapter?collection_folder=${encodeURIComponent(collection)}` +
            `&book_folder=${encodeURIComponent(bookFolder)}` +
            `&section_filename=${encodeURIComponent(sectionFilename)}`;
    } else {
      setError('Missing URL parameters');
      return;
    }
    fetch(url)
      .then(res => {
        if (!res.ok) throw new Error('Failed to load chapter data');
        return res.json();
      })
      .then(data => {
        setBlocks(data.blocks);
        setBookTitle(data.book_title);
        setPrevSection(data.prev_section);
        setNextSection(data.next_section);
        // CHANGED (2026-04-19): boundary nav state; backend returns null when
        // the book has no sections, which shouldn't happen but is handled.
        setFirstSection(data.first_section);
        setLastSection(data.last_section);
        // CHANGED: slug-form nav targets for slugMode link building. Empty
        // strings fall through to /chapter?... fallbacks below.
        setPrevSlug(data.prev_slug || '');
        setNextSlug(data.next_slug || '');
        setFirstSlug(data.first_slug || '');
        setLastSlug(data.last_slug || '');
        // CHANGED: only used by the /chapter?... fallback href when a slug is
        // missing. Empty in slug mode (which builds /read/... URLs that don't
        // need book_folder).
        setResolvedBookFolder(slugMode ? '' : (bookFolder || ''));
        // CHANGED (b.5): pick up breadcrumb; default '' for non-journal books
        // and older chapters.db rows that predate the parent_toc_title column.
        setParentTocTitle(data.parent_toc_title || '');
        // CHANGED (2026-04-20): pick up reflow flag (backend /api/chapter).
        // Default true preserves prior prose behavior if the field is missing.
        setReflowed(data.reflowed !== false);
      })
      .catch(err => setError(err.message));
  }, [slugMode, collection, bookFolder, sectionFilename, bookSlug, slug]);

  // Build sanitized HTML
  // CHANGED (2026-04-19): the backend pre-wraps prose (reflow width=90,
  // non-reflow textwrap width=100) and returns the fragments as a `lines`
  // array. Joining them with <br/> pinned the visible line breaks wherever
  // the server wrapped, producing a ragged column that couldn't reflow on
  // narrow viewports. Now we join with a space so the browser handles word
  // wrap itself, and split on standalone '*' lines — which the source text
  // uses as an asterism — into separate <p>s with a centered divider.
  // CHANGED (2026-04-20): when `reflowed` is false the backend deliberately
  // kept the source's hard line breaks (e.g. Savitri and other verse, which
  // _should_reflow() rejects via REFLOW_DENY_RE or poetry heuristic). In that
  // case join with <br/> so each verse line renders on its own line instead
  // of collapsing into a contiguous paragraph.
  // CHANGED: Savitri-only sentence-stanza splitting. When the line ends a
  // sentence (.?! optionally followed by a closing quote/paren), we flush the
  // current group so each sentence renders as its own <p class="verse">,
  // visually separated by the existing 1rem paragraph margin. Other verse
  // books (Collected Poems, Translations) keep the single-paragraph-per-stanza
  // behavior — splitting their short poems would put a stray gap before each
  // poem's title. Detection uses bookTitle (server-supplied, unambiguous);
  // bookFolder/bookSlug would also work but require knowing both URL forms.
  const splitSavitriSentences = bookTitle === 'Savitri' && !reflowed;
  const htmlContent = useMemo(() => {
    const lineJoin = reflowed ? ' ' : '<br/>';
    return blocks.map(blk => {
      if (blk.type === 'hr') return '<hr/>';
      const groups = [];
      let buf = [];
      const flush = () => { if (buf.length) { groups.push(buf); buf = []; } };
      for (const line of blk.lines) {
        if (line.trim() === '*') { flush(); groups.push('*'); }
        else {
          buf.push(line);
          // CHANGED: flush mid-stanza on sentence-ending lines for Savitri.
          if (splitSavitriSentences && SENTENCE_END_RE.test(line)) flush();
        }
      }
      flush();
      return groups.map(g => {
        if (g === '*') return '<p class="asterism">*</p>';
        const sanitized = g.map(line => DOMPurify.sanitize(line));
        // CHANGED (2026-04-20): verse branch adds a `verse` class so CSS can
        // left-align the text (justified verse looks awful on short lines).
        const cls = reflowed ? '' : ' class="verse"';
        return `<p${cls}>${sanitized.join(lineJoin)}</p>`;
      }).join('');
    }).join('');
  }, [blocks, reflowed, splitSavitriSentences]);

  // Highlight & scroll
  useLayoutEffect(() => {
    const ctx = contentRef.current;
    if (!htmlContent || !phrase || !ctx) return;

    const markIns = new MarkClass(ctx);

    markIns.unmark({
      done: () => {
        const scroll = () => {
          const el = ctx.querySelector('mark');
          if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        };

        const markOpts = {
          acrossElements: true,
          ignorePunctuation: ":;.,–—()[]'\"-_",
          diacritics: true,
          ignoreJoiners: true,
        };

        if (resultType === 'exact') {
          // Try exact phrase first
          markIns.mark(phrase, {
            ...markOpts,
            separateWordSearch: false,
            done: count => {
              if (count > 0) {
                const exact = Array.from(ctx.querySelectorAll('mark'))
                  .find(el => el.textContent.trim().toLowerCase() === phrase.toLowerCase());
                (exact || ctx.querySelector('mark'))?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                return;
              }
              // Fallback: ligature-tolerant first occurrence
              try {
                const normPhrase = normalizeCompat(phrase);
                const pattern = ligatureRegexEscape(normPhrase).replace(/\s+/g, '\\s+');
                const rx = new RegExp(pattern, 'i');

                const html = ctx.innerHTML;
                const normalizedHTML = normalizeCompat(html);
                if (rx.test(normalizedHTML)) {
                  const displayRx = new RegExp(ligatureRegexEscape(phrase), 'i');
                  ctx.innerHTML = html.replace(displayRx, '<mark>$&</mark>');
                  scroll();
                  return;
                }
              } catch {}
              // Final fallback: highlight individual non-stopwords
              const words = phrase.split(/\s+/).filter(w => w && !STOPWORDS.has(w.toLowerCase()));
              if (!words.length) return;
              markIns.mark(words, { ...markOpts, separateWordSearch: true, done: scroll });
            }
          });
        } else {
          // ALL/ANY: non-stopword terms
          const words = normalizeCompat(phrase)
            .split(/\s+/)
            .filter(w => w && !STOPWORDS.has(w.toLowerCase()));
          if (!words.length) return;

          markIns.mark(words, {
            ...markOpts,
            separateWordSearch: true,
            done: () => {
              if (!ctx.querySelector('mark')) {
                // ligature-tolerant per-term fallback
                let html = ctx.innerHTML;
                for (const t of words) {
                  const rx = new RegExp('\\b(' + ligatureRegexEscape(t) + ')\\b', 'gi');
                  html = html.replace(rx, '<mark>$1</mark>');
                }
                ctx.innerHTML = html;
              }
              scroll();
            }
          });
        }
      }
    });
  }, [htmlContent, phrase, resultType]);

  if (error) return <div className="alert alert-danger">{error}</div>;
  if (!blocks.length) return <div>Loading…</div>;

  return (
    <>
      <style>{`
        .chapter-wrapper { padding: 2rem; font-size: 1.125rem; }
        .chapter-wrapper h1 { margin-bottom: 0; font-size: 1.25rem; font-weight: 700; }
        .chapter-heading { display: block; font-weight: 700; margin-bottom: 1rem; font-size: 1.5rem; }
        .chapter-content { max-width: 70ch; hyphens: auto; -webkit-hyphens: auto; }
        .chapter-content p { text-align: justify; line-height: 1.75; margin-bottom: 1rem; }
        .chapter-content hr { border: 0; border-top: 1px solid #ccc; margin: 2rem 0; }
        .chapter-content mark { background-color: #fff3a3; font-weight: 600; padding: 0 0.05em; border-radius: 2px; }
        /* CHANGED (b.5): subdued italic subtitle for the Pass-3 breadcrumb
           so it reads as metadata rather than part of the chapter title. */
        .chapter-subtitle { text-align: center; color: #6c757d; font-style: italic; margin: -0.5rem 0 1.25rem; font-size: 1rem; }
        /* CHANGED (2026-04-19): in-block asterism separator (the '*' line the
           source uses between sub-sections of a paragraph group). */
        .chapter-content p.asterism { text-align: center; letter-spacing: 0.5em; color: #888; margin: 1rem 0; }
        /* CHANGED (2026-04-20): verse blocks keep server-side line breaks
           (<br/>-joined). Left-align and drop hyphenation — justified verse
           with hyphens mangles the meter. */
        .chapter-content p.verse { text-align: left; hyphens: manual; -webkit-hyphens: manual; }
      `}</style>

      <div className="chapter-wrapper container">
        {/* Navigation */}
        {/* CHANGED (2026-04-19): expanded from [Prev | title | Next] to
            [First · Prev | title | Next · Last]. First/Last are hidden when
            the reader is already at that boundary, so they never duplicate
            Prev/Next. The URL-building logic is now a single helper to keep
            the four links in sync. */}
        {(() => {
          // CHANGED: nav-href builder now emits a /read/... URL when this
          // component is mounted on the slug route AND the target neighbor has
          // a slug. Otherwise it falls back to /chapter?...&section_filename=,
          // which keeps legacy data (rows without slugs) working.
          //
          // CHANGED: prev/next/first/last deliberately drop `query` and
          // `result_type` from the nav target. Highlighting is only useful on
          // the chapter the user opened from a search result; once they
          // navigate to a neighbor, mark.js would (a) highlight unrelated text
          // and (b) auto-scroll past the top of the chapter. Plain nav
          // re-opens the next chapter from the top with no marks. The current
          // page still highlights because the URL the user *arrived at* still
          // carries the query string.
          const buildChapterHref = (targetSection, targetSlug) => {
            if (slugMode && targetSlug) {
              return `/read/${encodeURIComponent(collection)}` +
                     `/${encodeURIComponent(bookSlug)}` +
                     `/${encodeURIComponent(targetSlug)}`;
            }
            // Fallback: /chapter?... query form (no query/result_type carried).
            const qs = new URLSearchParams();
            qs.set('collection_folder', collection);
            qs.set('book_folder', bookFolder || resolvedBookFolder);
            qs.set('section_filename', targetSection);
            return `/chapter?${qs.toString()}`;
          };
          // CHANGED: boundary detection in slug mode compares slugs (the URL
          // identifier we actually have) — sectionFilename is null on /read/...
          // routes, so the legacy `firstSection !== sectionFilename` check
          // would never match and First/Last would always show.
          const atFirst = slugMode ? (firstSlug && firstSlug === slug)
                                   : (firstSection && firstSection === sectionFilename);
          const atLast  = slugMode ? (lastSlug && lastSlug === slug)
                                   : (lastSection && lastSection === sectionFilename);
          const showFirst = firstSection && !atFirst && firstSection !== prevSection;
          const showLast  = lastSection  && !atLast  && lastSection  !== nextSection;
          return (
            <div className="d-flex justify-content-between align-items-center mb-4">
              <div className="chapter-nav-side">
                {showFirst && (
                  <Link to={buildChapterHref(firstSection, firstSlug)} className="btn btn-link p-0 me-3">[« First]</Link>
                )}
                {prevSection && (
                  <Link to={buildChapterHref(prevSection, prevSlug)} className="btn btn-link p-0">[Previous]</Link>
                )}
              </div>

              <h1 className="chapter-heading">{bookTitle}</h1>

              <div className="chapter-nav-side text-end">
                {nextSection && (
                  <Link to={buildChapterHref(nextSection, nextSlug)} className="btn btn-link p-0 me-3">[Next]</Link>
                )}
                {showLast && (
                  <Link to={buildChapterHref(lastSection, lastSlug)} className="btn btn-link p-0">[Last »]</Link>
                )}
              </div>
            </div>
          );
        })()}

        {/* CHANGED (b.5): breadcrumb under the nav row — recovers the parent
            TOC entry (e.g. "March 14, 1952" for Mother Agenda, "Book Three —
            The Book of the Divine Mother" for a Savitri canto). Rendered
            only when non-empty so non-journal/non-Savitri books keep their
            original header.
            CHANGED: dropped the "from " prefix — the breadcrumb reads as a
            standalone subtitle now, matching what the user expects to see
            (just the parent title, no leading preposition). */}
        {parentTocTitle && (
          <div className="chapter-subtitle">{parentTocTitle}</div>
        )}

        <div
          ref={contentRef}
          className="chapter-content"
          dangerouslySetInnerHTML={{ __html: htmlContent }}
        />
      </div>
    </>
  );
};

export default ChapterPage;
