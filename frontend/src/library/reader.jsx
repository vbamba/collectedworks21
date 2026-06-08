/* ============================================================
   The Library Reader — Phase 3c.
   CHANGED: the prototype's stub-text reader is replaced with a real
   reader. It fetches the chapter from the backend and renders it with
   the SHARED renderer (src/lib/chapterRender) — the exact logic the
   legacy ChapterPage uses — inside the Serene reader chrome. So reading
   from a Library search result stays in the new design instead of
   handing off to the old template.
   ============================================================ */
import React, { useState, useEffect, useRef } from 'react';
import './reader-content.css';
import { Icon } from './components.jsx';
import { buildChapterHtml, fetchChapterData, highlightChapter } from '../lib/chapterRender';

const READER_DEFAULTS = { size: 20, theme: "paper", spacing: 1.75, width: "normal", font: "spectral" };

function loadReaderPrefs() {
  try { return { ...READER_DEFAULTS, ...JSON.parse(localStorage.getItem("sa_reader") || "{}") }; }
  catch (e) { return { ...READER_DEFAULTS }; }
}

export function ReaderScreen({ route, go, onMenu }) {
  const ch = route.chapter || {};
  const query = route.query || "";
  const resultType = route.resultType || "all";

  const [prefs, setPrefs] = useState(loadReaderPrefs);
  const [showSettings, setShowSettings] = useState(false);
  const [chrome, setChrome] = useState(true);
  const [progress, setProgress] = useState(0);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const scrollRef = useRef(null);
  const contentRef = useRef(null);

  useEffect(() => { localStorage.setItem("sa_reader", JSON.stringify(prefs)); }, [prefs]);

  // Fetch the chapter whenever the target changes.
  useEffect(() => {
    let alive = true;
    setData(null); setError("");
    fetchChapterData(ch)
      .then((d) => { if (alive) setData(d); })
      .catch((e) => { if (alive) setError(e.message); });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ch.collection, ch.bookSlug, ch.slug, ch.bookFolder, ch.sectionFilename, ch.slugMode]);

  const html = data ? buildChapterHtml(data.blocks, data.reflowed !== false, data.book_title) : "";

  // Highlight the search phrase once the chapter HTML is in the DOM.
  useEffect(() => {
    if (html && contentRef.current) highlightChapter(contentRef.current, { phrase: query, resultType });
  }, [html, query, resultType]);

  // Reading progress bar.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const onScroll = () => {
      const max = el.scrollHeight - el.clientHeight;
      setProgress(max > 0 ? el.scrollTop / max : 0);
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => el.removeEventListener("scroll", onScroll);
  }, [html]);

  const set = (k, val) => setPrefs((p) => ({ ...p, [k]: val }));
  const widthPx = prefs.width === "narrow" ? 540 : prefs.width === "wide" ? 760 : 640;
  const fontStack = prefs.font === "lora" ? "'Lora', Georgia, serif"
    : prefs.font === "cormorant" ? "'Cormorant Garamond', Georgia, serif"
    : "'Spectral', Georgia, serif";

  // Back to search, carrying the query so the results reappear.
  const back = () => go({ name: "search", q: query });

  // Prev/Next within the book (slug mode only — search results always carry
  // book_slug/slug). Disabled when the neighbour or book slug is unavailable.
  const canNav = !!(ch.collection && ch.bookSlug);
  const navTo = (targetSlug) => {
    if (!canNav || !targetSlug) return;
    go({ name: "reader", chapter: { slugMode: true, collection: ch.collection, bookSlug: ch.bookSlug, slug: targetSlug } });
  };

  const bookTitle = data?.book_title || "";

  return (
    <div className={"reader theme-" + prefs.theme}>
      <div className="reader-progress"><span style={{ width: progress * 100 + "%" }} /></div>

      <header className={"reader-bar top" + (chrome ? "" : " hidden")}>
        <button className="iconbtn" onClick={onMenu} aria-label="Menu"><Icon name="menu" /></button>
        <button className="iconbtn" onClick={back} aria-label="Back"><Icon name="arrowLeft" /></button>
        <div className="reader-bar-title"><span>{bookTitle || "Reading"}</span>{data?.parent_toc_title && <em>{data.parent_toc_title}</em>}</div>
        <button className="iconbtn" onClick={() => setShowSettings(true)} aria-label="Reading settings"><Icon name="type" /></button>
      </header>

      {/* CHANGED: persistent menu button so navigation stays reachable even when
          the reading chrome is hidden (tap-to-immerse). */}
      {!chrome && (
        <button className="reader-fab-menu" onClick={(e) => { e.stopPropagation(); onMenu(); }} aria-label="Menu">
          <Icon name="menu" size={20} />
        </button>
      )}

      <div className="reader-scroll" ref={scrollRef} onClick={() => setChrome((c) => !c)}>
        <article className="reader-article" style={{ maxWidth: widthPx, fontSize: prefs.size, lineHeight: prefs.spacing, fontFamily: fontStack }}>
          {bookTitle && (
            <div className="reader-volhead">
              <div className="rv-title">{bookTitle}</div>
              {data?.parent_toc_title && <div className="rv-part">{data.parent_toc_title}</div>}
            </div>
          )}

          {!data && !error && <p style={{ textAlign: "center", color: "var(--ink-soft)", padding: "40px 0" }}>Loading…</p>}
          {error && <p style={{ textAlign: "center", color: "var(--ink-soft)", padding: "40px 0" }}>Couldn’t load this text. {error}</p>}

          <div className="chapter-body" ref={contentRef} dangerouslySetInnerHTML={{ __html: html }} />

          {data && (
            <div className="reader-end">
              <span>∗ ∗ ∗</span>
              <button className="btn-ghost" onClick={back}>Back to results</button>
            </div>
          )}
        </article>
      </div>

      <footer className={"reader-bar bottom" + (chrome ? "" : " hidden")}>
        <button className="reader-nav" disabled={!canNav || !data?.prev_slug} onClick={(e) => { e.stopPropagation(); navTo(data?.prev_slug); }}>
          <Icon name="chevronLeft" size={18} /> Prev
        </button>
        <span className="reader-pageno">{Math.round(progress * 100)}%</span>
        <button className="reader-nav" disabled={!canNav || !data?.next_slug} onClick={(e) => { e.stopPropagation(); navTo(data?.next_slug); }}>
          Next <Icon name="chevronRight" size={18} />
        </button>
      </footer>

      {showSettings && <ReaderSettings prefs={prefs} set={set} reset={() => setPrefs({ ...READER_DEFAULTS })} onClose={() => setShowSettings(false)} />}
    </div>
  );
}

function ReaderSettings({ prefs, set, reset, onClose }) {
  return (
    <div className="sheet-scrim" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <div className="sheet-grab" />
        <div className="sheet-head">
          <h3>Reading</h3>
          <button className="iconbtn" onClick={onClose}><Icon name="close" /></button>
        </div>

        <div className="set-row">
          <label>Text size</label>
          <div className="stepper">
            <button onClick={() => set("size", Math.max(15, prefs.size - 1))}><Icon name="minus" size={18} /></button>
            <span>{prefs.size}px</span>
            <button onClick={() => set("size", Math.min(30, prefs.size + 1))}><Icon name="plus" size={18} /></button>
          </div>
        </div>

        <div className="set-row col">
          <label>Theme</label>
          <div className="theme-swatches">
            {[["paper", "Light", "#FAF6EE", "#2A2620"], ["sepia", "Sepia", "#F2E4CB", "#4a3c28"], ["night", "Dark", "#14140f", "#cfc8ba"]].map(([k, l, bg, fg]) => (
              <button key={k} className={"swatch" + (prefs.theme === k ? " active" : "")} onClick={() => set("theme", k)}>
                <span className="sw-chip" style={{ background: bg, color: fg }}>Aa</span>
                <span>{l}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="set-row col">
          <label>Typeface</label>
          <div className="seg full">
            {[["spectral", "Spectral"], ["lora", "Lora"], ["cormorant", "Cormorant"]].map(([k, l]) => (
              <button key={k} className={"seg-btn" + (prefs.font === k ? " active" : "")} onClick={() => set("font", k)} style={{ fontFamily: k === "lora" ? "Lora,serif" : k === "cormorant" ? "'Cormorant Garamond',serif" : "Spectral,serif" }}>{l}</button>
            ))}
          </div>
        </div>

        <div className="set-row">
          <label>Line spacing</label>
          <div className="stepper">
            <button onClick={() => set("spacing", Math.max(1.4, +(prefs.spacing - 0.1).toFixed(2)))}><Icon name="minus" size={18} /></button>
            <span>{prefs.spacing.toFixed(1)}</span>
            <button onClick={() => set("spacing", Math.min(2.4, +(prefs.spacing + 0.1).toFixed(2)))}><Icon name="plus" size={18} /></button>
          </div>
        </div>

        <div className="set-row col">
          <label>Column width</label>
          <div className="seg full">
            {[["narrow", "Narrow"], ["normal", "Normal"], ["wide", "Wide"]].map(([k, l]) => (
              <button key={k} className={"seg-btn" + (prefs.width === k ? " active" : "")} onClick={() => set("width", k)}>{l}</button>
            ))}
          </div>
        </div>

        <button className="sheet-reset" onClick={reset}>Reset to defaults</button>
      </div>
    </div>
  );
}
