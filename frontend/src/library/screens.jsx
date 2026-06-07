/* ============================================================
   Screens: Browse, Volume, Search, Media, Daily.
   CHANGED: window globals -> ESM imports/exports.
   SearchScreen is wired to the real backend (Phase 3b); the other
   screens still use stub data (Browse/Volume -> Phase 3c).
   ============================================================ */
import React, { useState, useEffect, useRef } from 'react';
// CHANGED (Phase 3b/3c): SearchScreen uses the real backend; result clicks open
// the in-Library reader (go) instead of navigating away to the old template.
// DOMPurify sanitises backend snippet HTML; api.js provides filters + search.
import DOMPurify from 'dompurify';
import { DATA } from './data.js';
import { Icon, Sigil, SectionHead, BookRow } from './components.jsx';
import { fetchFilters, performTextSearch } from '../services/api';
// CHANGED (Phase 3d): Browse/Volume use the real book list (/api/books) and
// per-book TOC (/api/book_toc) instead of stub data.
import { useBooks, deriveCollections, collectionFullName, authorCode } from './useBooks.js';

/* ---------- BROWSE ----------------------------------------- */
export function BrowseScreen({ route, go }) {
  const books = useBooks();
  const [author, setAuthor] = useState(route.author || "all");
  const activeCollection = route.collection; // a backend group_name (CWSA/CWM/…)

  if (route.view === "savitri") return <SavitriScreen go={go} />;

  const collections = deriveCollections(books);
  let vols = books;
  if (activeCollection) vols = vols.filter((b) => b.group_name === activeCollection);
  else if (author !== "all") vols = vols.filter((b) => authorCode(b.author) === author);

  const col = activeCollection ? collections.find((c) => c.name === activeCollection) : null;

  return (
    <div className="screen">
      <div className="page-hero">
        <div className="eyebrow">{col ? col.name : "The Library"}</div>
        <h1 className="page-title">{col ? collectionFullName(col.name) : "Complete Works"}</h1>
        <p className="page-lede">
          {col ? `${col.count} volumes in this edition.` : "Every volume of Sri Aurobindo and the Mother, freely readable. Browse by collection, author, or subject."}
        </p>
      </div>

      {!activeCollection && (
        <>
          <div className="seg" role="tablist">
            {[["all", "All"], ["sa", "Sri Aurobindo"], ["m", "The Mother"]].map(([k, l]) => (
              <button key={k} className={"seg-btn" + (author === k ? " active" : "")} onClick={() => setAuthor(k)}>{l}</button>
            ))}
          </div>

          <div className="block">
            <SectionHead eyebrow="Collections" title="Editions" />
            <div className="coll-list">
              {collections.map((c) => (
                <button key={c.name} className="coll-card" data-author={c.author} onClick={() => go({ name: "browse", collection: c.name })}>
                  <div className="coll-top">
                    <Sigil author={c.author} size={30} />
                    <span className="coll-count">{c.count} vols</span>
                  </div>
                  <div className="coll-abbr">{c.name}</div>
                  <div className="coll-name">{collectionFullName(c.name)}</div>
                </button>
              ))}
            </div>
          </div>

          <div className="block">
            <SectionHead eyebrow="By theme" title="Browse by subject" />
            <div className="chip-wrap">
              {DATA.SUBJECTS.map((s) => (
                <button key={s} className="chip" onClick={() => go({ name: "search", q: s })}>{s}</button>
              ))}
            </div>
          </div>
        </>
      )}

      <div className="block">
        <SectionHead eyebrow={col ? "In this edition" : "All volumes"} title={`${vols.length} volumes`} />
        <div className="vol-list">
          {vols.map((b) => <BookRow key={`${b.collection}/${b.book_slug}`} b={b} go={go} />)}
        </div>
      </div>
    </div>
  );
}

/* ---------- SAVITRI feature -------------------------------- */
export function SavitriScreen({ go }) {
  return (
    <div className="screen">
      <div className="savitri-hero">
        <div className="eyebrow on-dark">A Legend and a Symbol</div>
        <h1 className="savitri-title">Savitri</h1>
        <p className="savitri-sub">An epic of nearly 24,000 lines — death conquered by love, and the descent of a new consciousness upon earth.</p>
        <div className="hero-actions">
          <button className="btn-primary" onClick={() => go({ name: "reader", id: "savitri" })}><Icon name="book" size={18} /> Read the Poem</button>
          <button className="btn-ghost on-dark" onClick={() => go({ name: "media" })}><Icon name="headphones" size={18} /> Mother's reading</button>
        </div>
      </div>
      <div className="block">
        <SectionHead eyebrow="Editions & study" title="Explore Savitri" />
        <div className="vol-list">
          <button className="vol-row" onClick={() => go({ name: "reader", id: "savitri" })}>
            <span className="vr-spine" data-author="sa">33</span>
            <span className="vr-body"><span className="vr-title">Savitri — CWSA</span><span className="vr-meta">Books I–XII · 816 pp</span></span>
            <Icon name="chevronRight" size={18} style={{ color: "var(--ink-faint)" }} />
          </button>
          {["1950", "1954", "1970"].map((y) => (
            <button key={y} className="vol-row" onClick={() => go({ name: "reader", id: "savitri" })}>
              <span className="vr-spine" data-author="sa">·</span>
              <span className="vr-body"><span className="vr-title">Savitri — {y} Edition</span><span className="vr-meta">Other editions</span></span>
              <Icon name="chevronRight" size={18} style={{ color: "var(--ink-faint)" }} />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ---------- VOLUME DETAIL ---------------------------------- */
export function VolumeScreen({ route, go }) {
  const book = route.book;
  const [toc, setToc] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!book) return;
    let alive = true;
    setToc(null); setErr("");
    fetch(`/api/book_toc?collection_folder=${encodeURIComponent(book.collection)}&book_slug=${encodeURIComponent(book.book_slug)}`)
      .then((r) => { if (!r.ok) throw new Error("toc"); return r.json(); })
      .then((d) => { if (alive) setToc(d); })
      .catch(() => { if (alive) setErr("Couldn’t load the contents."); });
    return () => { alive = false; };
  }, [book?.collection, book?.book_slug]);

  if (!book) return <div className="screen"><p style={{ padding: 24 }}>No book selected.</p></div>;

  const ac = authorCode(book.author);
  const showAuthor = book.author && !/various/i.test(book.author);
  const openReader = (slug) => go({ name: "reader", chapter: { slugMode: true, collection: book.collection, bookSlug: book.book_slug, slug } });
  const firstSlug = book.first_slug || toc?.chapters?.[0]?.slug;

  return (
    <div className="screen">
      <button className="back-link" onClick={() => go({ name: "browse", collection: book.group_name })}><Icon name="arrowLeft" size={18} /> {book.group_name}</button>

      <div className="vol-detail-head">
        <div className="vd-cover" data-author={ac}>
          <span className="vd-cover-title">{book.title}</span>
          {showAuthor && <span className="vd-cover-author">{book.author}</span>}
          <span className="vd-cover-sig"><Sigil author={ac} size={30} /></span>
        </div>
        <div className="vd-info">
          <div className="eyebrow">{collectionFullName(book.group_name)}</div>
          <h1 className="vd-title">{book.title}</h1>
          <div className="vd-stats">
            <span><Icon name="book" size={15} /> {toc ? `${toc.chapters.length} chapters` : "…"}</span>
          </div>
        </div>
      </div>

      <div className="hero-actions sticky-actions">
        <button className="btn-primary" disabled={!firstSlug} onClick={() => firstSlug && openReader(firstSlug)}><Icon name="book" size={18} /> Start Reading</button>
        {book.pdf_url && (
          <a className="iconbtn-lg" href={`/viewer?file=${encodeURIComponent(book.pdf_url)}&page=1`} target="_blank" rel="noopener" aria-label="Open PDF"><Icon name="download" size={20} /></a>
        )}
      </div>

      <div className="block">
        <SectionHead eyebrow="Contents" title="Table of contents" />
        {err && <p className="no-results">{err}</p>}
        {!toc && !err && <p className="search-note" style={{ padding: "12px 0" }}>Loading…</p>}
        {toc && (
          <div className="toc-list">
            {toc.chapters.map((ch, i) => (
              <button key={`${ch.slug}-${i}`} className="toc-row" onClick={() => openReader(ch.slug)}>
                <span className="toc-num">{String(i + 1).padStart(2, "0")}</span>
                <span className="toc-title">{deriveTitle(ch)}</span>
                <Icon name="chevronRight" size={16} style={{ color: "var(--ink-faint)" }} />
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* ---------- SEARCH (wired to the real /api backend) -------- */
// Derive a readable section title from the backend filename, mirroring
// TextResultCard's logic (double-underscore -> " - ", Savitri "Book N" prefix).
function deriveTitle(r) {
  const fn = r.section_filename || "";
  const m = fn.match(/^[^_]+_\d+_(.+)\.txt$/);
  let t = m && m[1] ? m[1].replace(/__/g, " - ").replace(/_/g, " ") : (r.book_title || "Untitled");
  const bookMatch = r.parent_toc_title && r.parent_toc_title.match(/^(Book\s+\S+)/);
  if (bookMatch && /^Canto\b/i.test(t)) t = `${bookMatch[1]}, ${t}`;
  return t;
}

// (authorCode now imported from ./useBooks.js — shared with Browse/Volume.)

// Build the chapter descriptor the Library reader understands (prefer slug mode;
// search results always carry book_slug/slug, so slug mode is the common path).
function chapterTarget(r) {
  const coll = r.collection_folder;
  if (r.book_slug && r.slug && coll) {
    return { slugMode: true, collection: coll, bookSlug: r.book_slug, slug: r.slug };
  }
  return { slugMode: false, collection: coll, bookFolder: r.book_folder, sectionFilename: r.section_filename };
}

// Build the PDF viewer link if the row carries page info.
function pdfPath(r) {
  if (r.start_page === undefined || r.start_page === null) return null;
  let raw;
  if (r.pdf_url) raw = r.pdf_url;
  else if (r.pdf_file) {
    const BE = import.meta.env.VITE_BACKEND_PDF_URL || window.location.origin;
    raw = `${BE}/api/pdfs/${r.pdf_file}`.replace(/([^:]\/)\/+/g, "$1");
  } else return null;
  return `/viewer?file=${encodeURIComponent(raw)}&page=${r.start_page}`;
}

export function SearchScreen({ route, go }) {
  const [q, setQ] = useState(route.q || "");
  const [submitted, setSubmitted] = useState("");
  const [exact, setExact] = useState(false);
  const [group, setGroup] = useState("all");   // backend "group" == collection
  const [book, setBook] = useState("all");      // backend book_title
  const [activePill, setActivePill] = useState("all");
  const [filters, setFilters] = useState({ groups: [], book_titles: [], book_titles_by_group: {} });
  const [results, setResults] = useState([]);
  const [groupCounts, setGroupCounts] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef(null);

  useEffect(() => { inputRef.current && inputRef.current.focus(); }, []);
  useEffect(() => { fetchFilters().then(setFilters).catch(() => {}); }, []);

  const runWith = async (opts = {}) => {
    const term = (opts.query ?? q).trim();
    const g = opts.group ?? group;
    const b = opts.book ?? book;
    const ex = opts.exact ?? exact;
    setSubmitted(term);
    setActivePill("all");
    if (!term) { setResults([]); setGroupCounts({}); return; }
    setLoading(true);
    setError("");
    try {
      const data = await performTextSearch(term, {
        author: "",
        group: g === "all" ? "" : g,
        book_title: b === "all" ? "" : b,
        search_type: ex ? "exact" : "all",
      });
      setResults(data.results || []);
      setGroupCounts(data.group_counts || {});
    } catch {
      setError("Search failed. Try again.");
      setResults([]);
      setGroupCounts({});
    }
    setLoading(false);
  };

  const run = () => runWith();
  const clear = () => {
    setQ(""); setSubmitted(""); setResults([]); setGroupCounts({});
    setGroup("all"); setBook("all"); setActivePill("all");
    inputRef.current && inputRef.current.focus();
  };
  const onKey = (e) => { if (e.key === "Enter") run(); };

  // Run search if we arrived with a query (e.g. a subject chip from Browse).
  useEffect(() => { if (route.q) runWith({ query: route.q }); /* eslint-disable-next-line */ }, []);

  const ql = submitted.toLowerCase();
  const shown = results.filter((r) => activePill === "all" || r.group === activePill);
  const allCount = results.length;
  const bookOptions = group === "all"
    ? (filters.book_titles || [])
    : (filters.book_titles_by_group?.[group] || filters.book_titles || []);

  return (
    <div className="screen search-screen">
      <div className="search-head">
        <h1 className="page-title">Search the works</h1>

        <div className="search-row">
          <div className="search-field">
            <Icon name="search" size={20} style={{ color: "var(--ink-soft)" }} />
            <input ref={inputRef} value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={onKey} placeholder="Search a word or phrase…" />
            {q && <button className="iconbtn sm" onClick={clear} aria-label="Clear"><Icon name="close" size={18} /></button>}
          </div>
          <button className="btn-search" onClick={run}>Search</button>
        </div>

        <div className="search-controls">
          <label className="check">
            <input type="checkbox" checked={exact} onChange={(e) => { setExact(e.target.checked); if (submitted) runWith({ exact: e.target.checked }); }} />
            <span className="check-box"><Icon name="close" size={13} style={{ opacity: exact ? 1 : 0 }} /></span>
            Exact match
          </label>
          <div className="selects">
            <div className="select">
              <select value={group} onChange={(e) => { const g = e.target.value; setGroup(g); setBook("all"); if (submitted) runWith({ group: g, book: "all" }); }}>
                <option value="all">All Collections</option>
                {(filters.groups || []).map((g) => <option key={g} value={g}>{g}</option>)}
              </select>
              <Icon name="chevronDown" size={16} />
            </div>
            <div className="select">
              <select value={book} onChange={(e) => { const b = e.target.value; setBook(b); if (submitted) runWith({ book: b }); }}>
                <option value="all">All Book Titles</option>
                {bookOptions.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
              <Icon name="chevronDown" size={16} />
            </div>
          </div>
        </div>
      </div>

      {error && <p className="no-results">{error}</p>}

      {!ql && !loading && (
        <div className="block">
          <SectionHead eyebrow="Try" title="Popular searches" />
          <div className="chip-wrap">
            {["psychic surrender", "the Divine", "silence", "evolution", "love", "supermind", "consciousness", "aspiration"].map((s) => (
              <button key={s} className="chip" onClick={() => { setQ(s); runWith({ query: s }); }}>{s}</button>
            ))}
          </div>
          <p className="search-note">
            Full-text search across the Complete Works, the Mother's Agenda and the disciples' writings.
          </p>
        </div>
      )}

      {loading && <p className="search-note" style={{ textAlign: "center", padding: "32px 0" }}>Searching…</p>}

      {ql && !loading && (
        <>
          <div className="pills-row">
            <span className="pills-label">Collections found</span>
            <button className={"cpill" + (activePill === "all" ? " active" : "")} onClick={() => setActivePill("all")}>
              All Collections <em>{allCount}</em>
            </button>
            {Object.entries(groupCounts).map(([g, cnt]) => (
              <button key={g} className={"cpill" + (activePill === g ? " active" : "")} onClick={() => setActivePill(g)}>
                {g} <em>{cnt}</em>
              </button>
            ))}
          </div>

          <div className="results">
            {shown.length === 0 && <p className="no-results">No passages found for &ldquo;{submitted}&rdquo;. Try a different word or turn off Exact match.</p>}
            {shown.map((r, i) => {
              const title = deriveTitle(r);
              const openReader = () => go({ name: "reader", chapter: chapterTarget(r), query: submitted, resultType: exact ? "exact" : "all" });
              const pdf = pdfPath(r);
              const ac = authorCode(r.author);
              const snippet = DOMPurify.sanitize(r.snippet || "", { ALLOWED_TAGS: ["b", "mark", "i", "em", "br"] });
              return (
                <article className="result-card" key={`${r.section_filename || "r"}-${i}`}>
                  <button className="rc-title" onClick={openReader}>
                    {r.book_title ? `${r.book_title} — ${title}` : title}
                  </button>
                  {/* CHANGED: clamp to 4 lines — backend snippets can be long
                      (the old TextResultCard capped at 10 <br>-lines), which made
                      each card tall and showed only a few results per screen. */}
                  <p
                    className="rc-snippet"
                    style={{ display: "-webkit-box", WebkitLineClamp: 4, WebkitBoxOrient: "vertical", overflow: "hidden" }}
                    dangerouslySetInnerHTML={{ __html: snippet }}
                  />
                  <div className="rc-foot">
                    <span className="rc-tags">
                      {r.group && <span className="rc-coll" data-author={ac}>{r.group}</span>}
                      {exact && <span className="rc-exact">exact</span>}
                    </span>
                    <span className="rc-actions">
                      {pdf && (
                        <a className="rc-pdf" href={pdf} target="_blank" rel="noopener">
                          <Icon name="download" size={15} /> PDF
                        </a>
                      )}
                      <button className="rc-read" onClick={openReader}>
                        Read <Icon name="arrowRight" size={15} />
                      </button>
                    </span>
                  </div>
                </article>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

/* ---------- MULTIMEDIA ------------------------------------- */
export function MediaScreen({ route, go }) {
  const [filter, setFilter] = useState("all");
  const [nowPlaying, setNowPlaying] = useState(null);
  const list = DATA.MEDIA.filter((m) => filter === "all" || m.kind === filter);
  return (
    <div className="screen">
      <div className="page-hero">
        <div className="eyebrow">Multimedia</div>
        <h1 className="page-title">Audio &amp; Video</h1>
        <p className="page-lede">Recordings of the Mother's voice, readings of Savitri, and archival film.</p>
      </div>
      <div className="seg">
        {[["all", "All"], ["audio", "Audio"], ["video", "Video"]].map(([k, l]) => (
          <button key={k} className={"seg-btn" + (filter === k ? " active" : "")} onClick={() => setFilter(k)}>{l}</button>
        ))}
      </div>
      <div className="block">
        <div className="media-list">
          {list.map((m) => (
            <button key={m.id} className={"media-row" + (nowPlaying === m.id ? " playing" : "")} onClick={() => setNowPlaying(m.id)}>
              <span className="media-thumb" data-kind={m.kind}>
                <Icon name={m.kind === "video" ? "film" : "play"} size={20} />
              </span>
              <span className="media-body">
                <span className="media-title">{m.title}</span>
                <span className="media-meta">{m.meta}</span>
              </span>
              <span className="media-dur">{m.duration}</span>
            </button>
          ))}
        </div>
      </div>
      {nowPlaying && <MiniPlayer media={DATA.MEDIA.find((m) => m.id === nowPlaying)} onClose={() => setNowPlaying(null)} />}
    </div>
  );
}

function MiniPlayer({ media, onClose }) {
  const [playing, setPlaying] = useState(true);
  const [pct, setPct] = useState(28);
  useEffect(() => {
    if (!playing) return;
    const t = setInterval(() => setPct((p) => (p >= 100 ? 0 : p + 0.4)), 300);
    return () => clearInterval(t);
  }, [playing]);
  return (
    <div className="miniplayer">
      <div className="mp-progress"><span style={{ width: pct + "%" }} /></div>
      <div className="mp-inner">
        <span className="media-thumb sm" data-kind={media.kind}><Icon name={media.kind === "video" ? "film" : "headphones"} size={18} /></span>
        <div className="mp-info"><span className="mp-title">{media.title}</span><span className="mp-meta">{media.meta}</span></div>
        <button className="mp-play" onClick={() => setPlaying((p) => !p)}>
          {playing ? <span className="mp-pause"><i /><i /></span> : <Icon name="play" size={20} />}
        </button>
        <button className="iconbtn" onClick={onClose}><Icon name="close" size={20} /></button>
      </div>
    </div>
  );
}

/* ---------- DAILY THOUGHT ---------------------------------- */
export function DailyScreen() {
  const dayIndex = new Date().getDate() % DATA.THOUGHTS.length;
  const [idx, setIdx] = useState(dayIndex);
  const t = DATA.THOUGHTS[idx];
  const today = new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });
  return (
    <div className="screen daily-screen">
      <div className="daily-card">
        <div className="daily-date">{today}</div>
        <div className="daily-mark"><Icon name="quote" size={30} style={{ color: "var(--gold)" }} /></div>
        <blockquote className="daily-quote">{t.text}</blockquote>
        <div className="daily-attr">
          <Sigil author={t.author === "The Mother" ? "m" : "sa"} size={26} />
          <div>
            <div className="daily-author">{t.author}</div>
            <div className="daily-source">{t.source}{t.page ? `, p. ${t.page}` : ""}</div>
          </div>
        </div>
        <div className="daily-actions">
          <button className="btn-ghost" onClick={() => setIdx((idx + 1) % DATA.THOUGHTS.length)}><Icon name="sparkle" size={17} /> Another</button>
          <button className="iconbtn-lg" aria-label="Share"><Icon name="share" size={19} /></button>
          <button className="iconbtn-lg" aria-label="Bookmark"><Icon name="bookmark" size={19} /></button>
        </div>
      </div>
      <p className="daily-foot">A passage offered each day from the works. Return tomorrow for a new one.</p>
    </div>
  );
}
