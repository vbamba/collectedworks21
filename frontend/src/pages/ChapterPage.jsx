// frontend/src/pages/ChapterPage.jsx
import React, { useState, useEffect, useMemo, useRef, useLayoutEffect } from 'react';
// CHANGED: also import useParams so this component can serve both URL shapes
//   /chapter?collection_folder=X&book_folder=Y&section_filename=Z   (legacy / query)
//   /read/:collection/:bookSlug/:slug                               (slug, post-migration)
// The slug shape used to be served exclusively by Flask's chapter.html
// template. We now route it through this component so all chapter rendering
// goes through one code path.
import { useSearchParams, useParams, Link } from 'react-router-dom';
// CHANGED (Phase 3c): chapter rendering (fetch + block→HTML + highlight) moved
// to src/lib/chapterRender.js so the new Library reader shares the exact same
// logic and the two can't drift. Behaviour here is unchanged.
import { buildChapterHtml, fetchChapterData, highlightChapter } from '../lib/chapterRender';

const ChapterPage = () => {
  const [searchParams]    = useSearchParams();
  // CHANGED: useParams returns {} when the matched route has no path params
  // (i.e. the /chapter route), and {collection, bookSlug, slug} on the new
  // /read/:collection/:bookSlug/:slug route. slugMode picks the data flow.
  const routeParams        = useParams();
  const slugMode           = !!(routeParams.collection && routeParams.bookSlug && routeParams.slug);

  const collection         = slugMode ? routeParams.collection : searchParams.get('collection_folder');
  const bookFolder         = slugMode ? null : searchParams.get('book_folder');
  const sectionFilename    = slugMode ? null : searchParams.get('section_filename');
  const bookSlug           = slugMode ? routeParams.bookSlug : '';
  const slug               = slugMode ? routeParams.slug : '';
  const phrase             = (searchParams.get('query') || '').trim();
  const resultType         = (searchParams.get('result_type') || 'all').toLowerCase();

  const [blocks, setBlocks]         = useState([]);
  const [bookTitle, setBookTitle]   = useState('');
  const [prevSection, setPrevSection] = useState(null);
  const [nextSection, setNextSection] = useState(null);
  const [firstSection, setFirstSection] = useState(null);
  const [lastSection, setLastSection]   = useState(null);
  const [prevSlug, setPrevSlug] = useState('');
  const [nextSlug, setNextSlug] = useState('');
  const [firstSlug, setFirstSlug] = useState('');
  const [lastSlug, setLastSlug] = useState('');
  const [resolvedBookFolder, setResolvedBookFolder] = useState('');
  const [parentTocTitle, setParentTocTitle] = useState('');
  const [reflowed, setReflowed]     = useState(true);
  const [error, setError]           = useState('');
  const contentRef                  = useRef(null);

  // Fetch blocks + metadata (shared fetch helper).
  useEffect(() => {
    fetchChapterData({ slugMode, collection, bookSlug, slug, bookFolder, sectionFilename })
      .then(data => {
        setBlocks(data.blocks);
        setBookTitle(data.book_title);
        setPrevSection(data.prev_section);
        setNextSection(data.next_section);
        setFirstSection(data.first_section);
        setLastSection(data.last_section);
        setPrevSlug(data.prev_slug || '');
        setNextSlug(data.next_slug || '');
        setFirstSlug(data.first_slug || '');
        setLastSlug(data.last_slug || '');
        setResolvedBookFolder(slugMode ? '' : (bookFolder || ''));
        setParentTocTitle(data.parent_toc_title || '');
        setReflowed(data.reflowed !== false);
      })
      .catch(err => setError(err.message));
  }, [slugMode, collection, bookFolder, sectionFilename, bookSlug, slug]);

  // Build sanitized HTML (shared renderer).
  const htmlContent = useMemo(
    () => buildChapterHtml(blocks, reflowed, bookTitle),
    [blocks, reflowed, bookTitle]
  );

  // Highlight & scroll (shared).
  useLayoutEffect(() => {
    if (!htmlContent) return;
    highlightChapter(contentRef.current, { phrase, resultType });
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
        .chapter-subtitle { text-align: center; color: #6c757d; font-style: italic; margin: -0.5rem 0 1.25rem; font-size: 1rem; }
        .chapter-content p.asterism { text-align: center; letter-spacing: 0.5em; color: #888; margin: 1rem 0; }
        .chapter-content h3.date-heading { font-size: 1.15rem; font-weight: 700; margin: 1.75rem 0 0.75rem; }
        .chapter-content h3.subheading { font-size: 1.15rem; font-weight: 700; margin: 1.75rem 0 0.75rem; }
        .chapter-content p.verse { text-align: left; hyphens: manual; -webkit-hyphens: manual; }
      `}</style>

      <div className="chapter-wrapper container">
        {/* Navigation: [First · Prev | title | Next · Last] */}
        {(() => {
          const buildChapterHref = (targetSection, targetSlug) => {
            if (slugMode && targetSlug) {
              return `/read/${encodeURIComponent(collection)}` +
                     `/${encodeURIComponent(bookSlug)}` +
                     `/${encodeURIComponent(targetSlug)}`;
            }
            const qs = new URLSearchParams();
            qs.set('collection_folder', collection);
            qs.set('book_folder', bookFolder || resolvedBookFolder);
            qs.set('section_filename', targetSection);
            return `/chapter?${qs.toString()}`;
          };
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
