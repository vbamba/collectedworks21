/* ============================================================
   The Reader + reading settings.
   CHANGED: window globals -> ESM imports/exports. Still renders the
   prototype's stub sample text; Phase 3c swaps the body for real
   chapter content from the existing ChapterPage/backend path.
   ============================================================ */
import React, { useState, useEffect, useRef } from 'react';
import { DATA } from './data.js';
import { Icon, Sigil } from './components.jsx';

const READER_DEFAULTS = { size: 20, theme: "paper", spacing: 1.75, width: "normal", font: "spectral" };

function loadReaderPrefs() {
  try { return { ...READER_DEFAULTS, ...JSON.parse(localStorage.getItem("sa_reader") || "{}") }; }
  catch (e) { return { ...READER_DEFAULTS }; }
}

export function ReaderScreen({ route, go }) {
  const v = DATA.volumeById(route.id) || DATA.volumeById("life-divine-1");
  const blocks = DATA.sampleFor(v.sample);
  const c = DATA.collectionById(v.collection);
  const [prefs, setPrefs] = useState(loadReaderPrefs);
  const [showSettings, setShowSettings] = useState(false);
  const [chrome, setChrome] = useState(true);
  const [progress, setProgress] = useState(0);
  const [bookmarked, setBookmarked] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => { localStorage.setItem("sa_reader", JSON.stringify(prefs)); }, [prefs]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const key = "sa_pos_" + v.id;
    const saved = parseFloat(localStorage.getItem(key) || "0");
    if (saved) el.scrollTop = saved * (el.scrollHeight - el.clientHeight);
    const onScroll = () => {
      const max = el.scrollHeight - el.clientHeight;
      const p = max > 0 ? el.scrollTop / max : 0;
      setProgress(p);
      localStorage.setItem(key, String(p));
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => el.removeEventListener("scroll", onScroll);
  }, [v.id]);

  const set = (k, val) => setPrefs((p) => ({ ...p, [k]: val }));
  const widthPx = prefs.width === "narrow" ? 540 : prefs.width === "wide" ? 760 : 640;
  const fontStack = prefs.font === "lora" ? "'Lora', Georgia, serif"
    : prefs.font === "cormorant" ? "'Cormorant Garamond', Georgia, serif"
    : "'Spectral', Georgia, serif";

  return (
    <div className={"reader theme-" + prefs.theme}>
      <div className="reader-progress"><span style={{ width: progress * 100 + "%" }} /></div>

      <header className={"reader-bar top" + (chrome ? "" : " hidden")}>
        <button className="iconbtn" onClick={() => go({ name: "volume", id: v.id })} aria-label="Back"><Icon name="arrowLeft" /></button>
        <div className="reader-bar-title"><span>{v.title}</span><em>{c.abbr}</em></div>
        <button className="iconbtn" onClick={() => setBookmarked((b) => !b)} aria-label="Bookmark" style={{ color: bookmarked ? "var(--gold)" : "inherit" }}>
          <Icon name="bookmark" style={{ fill: bookmarked ? "var(--gold)" : "none" }} />
        </button>
        <button className="iconbtn" onClick={() => setShowSettings(true)} aria-label="Reading settings"><Icon name="type" /></button>
      </header>

      <div className="reader-scroll" ref={scrollRef} onClick={() => setChrome((c) => !c)}>
        <article className="reader-article" style={{ maxWidth: widthPx, fontSize: prefs.size, lineHeight: prefs.spacing, fontFamily: fontStack }}>
          <div className="reader-volhead">
            <Sigil author={v.author} size={30} />
            <div className="rv-collection">{c.title}</div>
            <h1 className="rv-title">{v.title}</h1>
            {v.part && <div className="rv-part">{v.part}</div>}
          </div>
          {blocks.map((b, i) => <Block key={i} b={b} />)}
          <div className="reader-end">
            <span>∗ ∗ ∗</span>
            <a className="archive-link" href={DATA.readUrl(v, null, route.chapter)} target="_blank" rel="noopener">
              <Icon name="share" size={15} /> Open this text on the archive
            </a>
            <button className="btn-ghost" onClick={() => go({ name: "volume", id: v.id })}>Back to contents</button>
          </div>
        </article>
      </div>

      <footer className={"reader-bar bottom" + (chrome ? "" : " hidden")}>
        <button className="reader-nav" onClick={(e) => e.stopPropagation()}><Icon name="chevronLeft" size={18} /> Prev</button>
        <span className="reader-pageno">{Math.round(progress * v.pages) || 1} / {v.pages}</span>
        <button className="reader-nav" onClick={(e) => e.stopPropagation()}>Next <Icon name="chevronRight" size={18} /></button>
      </footer>

      {showSettings && <ReaderSettings prefs={prefs} set={set} reset={() => setPrefs({ ...READER_DEFAULTS })} onClose={() => setShowSettings(false)} />}
    </div>
  );
}

function Block({ b }) {
  if (b.type === "h2") return <h2 className="r-h2">{b.text}</h2>;
  if (b.type === "epigraph") return <div className="r-epigraph"><p>{b.text}</p><cite>— {b.cite}</cite></div>;
  if (b.type === "verse") return <div className="r-verse">{b.lines.map((l, i) => <span key={i}>{l}</span>)}</div>;
  return <p className="r-p">{b.text}</p>;
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
