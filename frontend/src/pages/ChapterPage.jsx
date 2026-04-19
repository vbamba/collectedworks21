// frontend/src/pages/ChapterPage.jsx
import React, { useState, useEffect, useMemo, useRef, useLayoutEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
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
  const collection         = searchParams.get('collection_folder');
  const bookFolder         = searchParams.get('book_folder');
  const sectionFilename    = searchParams.get('section_filename');
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
  // CHANGED (b.5): hold Pass-3 journal sub-section breadcrumb (e.g. "March 14,
  // 1952") returned by /api/chapter so the header can render "from <parent>".
  const [parentTocTitle, setParentTocTitle] = useState('');
  const [error, setError]           = useState('');
  const contentRef                  = useRef(null);

  // Fetch blocks + metadata
  useEffect(() => {
    if (!(collection && bookFolder && sectionFilename)) {
      setError('Missing URL parameters');
      return;
    }
    fetch(
      `/api/chapter?collection_folder=${encodeURIComponent(collection)}` +
      `&book_folder=${encodeURIComponent(bookFolder)}` +
      `&section_filename=${encodeURIComponent(sectionFilename)}`
    )
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
        // CHANGED (b.5): pick up breadcrumb; default '' for non-journal books
        // and older chapters.db rows that predate the parent_toc_title column.
        setParentTocTitle(data.parent_toc_title || '');
      })
      .catch(err => setError(err.message));
  }, [collection, bookFolder, sectionFilename]);

  // Build sanitized HTML
  // CHANGED (2026-04-19): the backend pre-wraps prose (reflow width=90,
  // non-reflow textwrap width=100) and returns the fragments as a `lines`
  // array. Joining them with <br/> pinned the visible line breaks wherever
  // the server wrapped, producing a ragged column that couldn't reflow on
  // narrow viewports. Now we join with a space so the browser handles word
  // wrap itself, and split on standalone '*' lines — which the source text
  // uses as an asterism — into separate <p>s with a centered divider.
  const htmlContent = useMemo(() => {
    return blocks.map(blk => {
      if (blk.type === 'hr') return '<hr/>';
      const groups = [];
      let buf = [];
      const flush = () => { if (buf.length) { groups.push(buf); buf = []; } };
      for (const line of blk.lines) {
        if (line.trim() === '*') { flush(); groups.push('*'); }
        else buf.push(line);
      }
      flush();
      return groups.map(g => {
        if (g === '*') return '<p class="asterism">*</p>';
        const sanitized = g.map(line => DOMPurify.sanitize(line));
        return `<p>${sanitized.join(' ')}</p>`;
      }).join('');
    }).join('');
  }, [blocks]);

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
      `}</style>

      <div className="chapter-wrapper container">
        {/* Navigation */}
        {/* CHANGED (2026-04-19): expanded from [Prev | title | Next] to
            [First · Prev | title | Next · Last]. First/Last are hidden when
            the reader is already at that boundary, so they never duplicate
            Prev/Next. The URL-building logic is now a single helper to keep
            the four links in sync. */}
        {(() => {
          const buildChapterHref = (target) => {
            const qs = new URLSearchParams();
            qs.set('collection_folder', collection);
            qs.set('book_folder', bookFolder);
            qs.set('section_filename', target);
            if (phrase) qs.set('query', phrase);
            qs.set('result_type', resultType);
            return `/chapter?${qs.toString()}`;
          };
          const showFirst = firstSection && firstSection !== sectionFilename && firstSection !== prevSection;
          const showLast  = lastSection  && lastSection  !== sectionFilename && lastSection  !== nextSection;
          return (
            <div className="d-flex justify-content-between align-items-center mb-4">
              <div className="chapter-nav-side">
                {showFirst && (
                  <Link to={buildChapterHref(firstSection)} className="btn btn-link p-0 me-3">[« First]</Link>
                )}
                {prevSection && (
                  <Link to={buildChapterHref(prevSection)} className="btn btn-link p-0">[Previous]</Link>
                )}
              </div>

              <h1 className="chapter-heading">{bookTitle}</h1>

              <div className="chapter-nav-side text-end">
                {nextSection && (
                  <Link to={buildChapterHref(nextSection)} className="btn btn-link p-0 me-3">[Next]</Link>
                )}
                {showLast && (
                  <Link to={buildChapterHref(lastSection)} className="btn btn-link p-0">[Last »]</Link>
                )}
              </div>
            </div>
          );
        })()}

        {/* CHANGED (b.5): breadcrumb under the nav row — recovers the parent
            TOC entry (e.g. "from March 14, 1952") that Pass-3 sub-section
            splitting would otherwise hide. Rendered only when non-empty so
            TOC-level books (non-journal) keep their original header. */}
        {parentTocTitle && (
          <div className="chapter-subtitle">from {parentTocTitle}</div>
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
