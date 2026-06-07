/* ============================================================
   Screens: Browse, Volume, Search, Media, Daily
   ============================================================ */

/* ---------- BROWSE ----------------------------------------- */
function BrowseScreen({ route, go }) {
  const [tab, setTab] = useState(route.collection ? "collections" : "collections");
  const [author, setAuthor] = useState(route.author || "all");
  const activeCollection = route.collection;

  if (route.view === "savitri") return <SavitriScreen go={go} />;

  let vols = DATA.VOLUMES;
  if (activeCollection) vols = vols.filter((v) => v.collection === activeCollection);
  else if (author !== "all") vols = vols.filter((v) => v.author === author);

  const col = activeCollection ? DATA.collectionById(activeCollection) : null;

  return (
    <div className="screen">
      <div className="page-hero">
        <div className="eyebrow">{col ? col.abbr : "The Library"}</div>
        <h1 className="page-title">{col ? col.title : "Complete Works"}</h1>
        <p className="page-lede">
          {col ? col.blurb : "Every volume of Sri Aurobindo and the Mother, freely readable. Browse by collection, author, or subject."}
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
              {DATA.COLLECTIONS.filter((c) => author === "all" || c.author === author).map((c) => (
                <button key={c.id} className="coll-card" data-author={c.author} onClick={() => go({ name: "browse", collection: c.id })}>
                  <div className="coll-top">
                    <Sigil author={c.author} size={30} />
                    <span className="coll-count">{c.count} vols</span>
                  </div>
                  <div className="coll-abbr">{c.abbr}</div>
                  <div className="coll-name">{c.title}</div>
                  <div className="coll-blurb">{c.blurb}</div>
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
        <SectionHead eyebrow={col ? "In this edition" : "All volumes"} title={col ? `${vols.length} volumes` : "Volumes"} />
        <div className="vol-list">
          {vols.map((v) => <VolumeCard key={v.id} v={v} go={go} variant="row" />)}
        </div>
      </div>
    </div>
  );
}

/* ---------- SAVITRI feature -------------------------------- */
function SavitriScreen({ go }) {
  const v = DATA.volumeById("savitri");
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
function VolumeScreen({ route, go }) {
  const v = DATA.volumeById(route.id);
  if (!v) return <div className="screen"><p style={{ padding: 24 }}>Not found.</p></div>;
  const c = DATA.collectionById(v.collection);
  const toc = DATA.sampleFor(v.sample).filter((b) => b.type === "h2").map((b) => b.text);
  // synthesize a believable table of contents
  const chapters = v.sample === "savitri"
    ? ["Book One — The Book of Beginnings", "Book Two — The Book of the Traveller of the Worlds", "Book Three — The Book of the Divine Mother", "Book Four — The Book of Birth and Quest", "Book Five — The Book of Love", "Book Six — The Book of Fate"]
    : v.sample === "prayers"
    ? ["1912", "1913", "1914", "1916", "1917", "1920"]
    : ["The Human Aspiration", "The Two Negations — The Materialist Denial", "The Two Negations — The Refusal of the Ascetic", "Reality Omnipresent", "The Destiny of the Individual", "Man in the Universe"];

  return (
    <div className="screen">
      <button className="back-link" onClick={() => go({ name: "browse", collection: v.collection })}><Icon name="arrowLeft" size={18} /> {c.abbr}</button>

      <div className="vol-detail-head">
        <div className="vd-cover" data-author={v.author}>
          <span className="vd-cover-num">{String(v.num).padStart(2, "0")}</span>
          <span className="vd-cover-title">{v.title}</span>
          <span className="vd-cover-author">{v.author === "m" ? "The Mother" : "Sri Aurobindo"}</span>
          <span className="vd-cover-sig"><Sigil author={v.author} size={30} /></span>
        </div>
        <div className="vd-info">
          <div className="eyebrow">{c.title}</div>
          <h1 className="vd-title">{v.title}</h1>
          {v.part && <div className="vd-part">{v.part}</div>}
          <div className="vd-stats">
            <span><Icon name="book" size={15} /> {v.pages} pages</span>
            <span><Icon name="clock" size={15} /> {v.year}</span>
            <span>Vol. {v.num}</span>
          </div>
        </div>
      </div>

      <div className="hero-actions sticky-actions">
        <button className="btn-primary" onClick={() => go({ name: "reader", id: v.id })}><Icon name="book" size={18} /> Start Reading</button>
        <button className="iconbtn-lg" aria-label="Bookmark"><Icon name="bookmark" size={20} /></button>
        <a className="iconbtn-lg" href={DATA.readUrl(v)} target="_blank" rel="noopener" aria-label="Open on archive"><Icon name="download" size={20} /></a>
      </div>

      <div className="block">
        <p className="vd-desc">{v.desc}</p>
      </div>

      <div className="block">
        <SectionHead eyebrow="Contents" title="Table of contents" />
        <div className="toc-list">
          {chapters.map((ch, i) => (
            <button key={i} className="toc-row" onClick={() => go({ name: "reader", id: v.id, chapter: i })}>
              <span className="toc-num">{String(i + 1).padStart(2, "0")}</span>
              <span className="toc-title">{ch}</span>
              <Icon name="chevronRight" size={16} style={{ color: "var(--ink-faint)" }} />
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ---------- SEARCH (mirrors ask.collectedworks functionality) ---- */
function SearchScreen({ route, go }) {
  const [q, setQ] = useState(route.q || "");
  const [submitted, setSubmitted] = useState(route.q || "");
  const [exact, setExact] = useState(false);
  const [collection, setCollection] = useState("all");
  const [book, setBook] = useState("all");
  const [activePill, setActivePill] = useState("all");
  const inputRef = useRef(null);
  useEffect(() => { inputRef.current && inputRef.current.focus(); }, []);

  const run = () => { setSubmitted(q.trim()); setActivePill("all"); };
  const clear = () => { setQ(""); setSubmitted(""); setCollection("all"); setBook("all"); setActivePill("all"); inputRef.current && inputRef.current.focus(); };
  const onKey = (e) => { if (e.key === "Enter") run(); };

  const ql = submitted.toLowerCase();
  // Build the full result set, then apply filters
  let results = ql ? buildResults(ql, exact) : [];
  results = results.filter((r) => {
    const v = DATA.volumeById(r.vid);
    if (collection !== "all" && v.collection !== collection) return false;
    if (book !== "all" && r.vid !== book) return false;
    if (activePill !== "all" && v.collection !== activePill) return false;
    return true;
  });

  // collection counts (ignore the pill filter, honor dropdowns)
  const pillBase = ql ? buildResults(ql, exact).filter((r) => {
    const v = DATA.volumeById(r.vid);
    if (collection !== "all" && v.collection !== collection) return false;
    if (book !== "all" && r.vid !== book) return false;
    return true;
  }) : [];
  const counts = {};
  pillBase.forEach((r) => { const c = DATA.volumeById(r.vid).collection; counts[c] = (counts[c] || 0) + 1; });

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
            <input type="checkbox" checked={exact} onChange={(e) => setExact(e.target.checked)} />
            <span className="check-box"><Icon name="close" size={13} style={{ opacity: exact ? 1 : 0 }} /></span>
            Exact match
          </label>
          <div className="selects">
            <div className="select">
              <select value={collection} onChange={(e) => { setCollection(e.target.value); setBook("all"); }}>
                <option value="all">All Collections</option>
                {DATA.COLLECTIONS.map((c) => <option key={c.id} value={c.id}>{c.abbr}</option>)}
              </select>
              <Icon name="chevronDown" size={16} />
            </div>
            <div className="select">
              <select value={book} onChange={(e) => setBook(e.target.value)}>
                <option value="all">All Book Titles</option>
                {DATA.VOLUMES.filter((v) => collection === "all" || v.collection === collection).map((v) => (
                  <option key={v.id} value={v.id}>{v.title}{v.part ? " — " + v.part : ""}</option>
                ))}
              </select>
              <Icon name="chevronDown" size={16} />
            </div>
          </div>
        </div>
      </div>

      {!ql && (
        <div className="block">
          <SectionHead eyebrow="Try" title="Popular searches" />
          <div className="chip-wrap">
            {["psychic surrender", "the Divine", "silence", "evolution", "love", "supermind", "consciousness", "aspiration"].map((s) => (
              <button key={s} className="chip" onClick={() => { setQ(s); setSubmitted(s); setActivePill("all"); }}>{s}</button>
            ))}
          </div>
          <p className="search-note">
            Full-text search across the Complete Works, the Mother's Agenda and the disciples' writings —
            powered by the archive at ask.collectedworksofsriaurobindo.com.
          </p>
        </div>
      )}

      {ql && (
        <>
          <div className="pills-row">
            <span className="pills-label">Collections found</span>
            <button className={"cpill" + (activePill === "all" ? " active" : "")} onClick={() => setActivePill("all")}>
              All Collections <em>{pillBase.length}</em>
            </button>
            {DATA.COLLECTIONS.filter((c) => counts[c.id]).map((c) => (
              <button key={c.id} className={"cpill" + (activePill === c.id ? " active" : "")} data-author={c.author} onClick={() => setActivePill(c.id)}>
                {c.abbr} <em>{counts[c.id]}</em>
              </button>
            ))}
          </div>

          <div className="results">
            {results.length === 0 && <p className="no-results">No passages found for &ldquo;{submitted}&rdquo;. Try a different word or turn off Exact match.</p>}
            {results.map((r, i) => {
              const v = DATA.volumeById(r.vid);
              return (
                <article className="result-card" key={i}>
                  <button className="rc-title" onClick={() => go({ name: "reader", id: r.vid, chapter: r.chapterIndex })}>
                    {v.title} — {r.chapterTitle}
                  </button>
                  <p className="rc-snippet" dangerouslySetInnerHTML={{ __html: r.html }} />
                  <div className="rc-foot">
                    <span className="rc-tags">
                      <span className="rc-coll" data-author={v.author}>{DATA.collectionById(v.collection).abbr}</span>
                      {r.exact && <span className="rc-exact">exact</span>}
                    </span>
                    <span className="rc-actions">
                      <a className="rc-pdf" href={DATA.readUrl(v, r.chapterTitle, r.chapterIndex)} target="_blank" rel="noopener">
                        <Icon name="download" size={15} /> PDF
                      </a>
                      <button className="rc-read" onClick={() => go({ name: "reader", id: r.vid, chapter: r.chapterIndex })}>
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

// Corpus of representative passages. In production these come from the
// archive's full-text index; here we filter a sample + synthesize hits.
const SEARCH_CORPUS = [
  { vid: "letters-yoga-1", chapterIndex: 6, chapterTitle: "Surrender", exact: true,
    text: "It is the @ in the physical that you have begun to experience. All the parts are essentially offered, but the surrender has to be made complete by the growth of the psychic self-offering in all of them." },
  { vid: "life-divine-1", chapterIndex: 0, chapterTitle: "The Human Aspiration", exact: false,
    text: "The earliest preoccupation of man in his awakened thoughts—the divination of Godhead, the impulse towards perfection, the search after pure Truth—returns to the question of @ after every banishment." },
  { vid: "synthesis-yoga", chapterIndex: 0, chapterTitle: "The Conditions of the Synthesis", exact: false,
    text: "All life is Yoga. By @ the seeker widens the narrow movements of the ego into the large and luminous workings of a greater Consciousness." },
  { vid: "savitri", chapterIndex: 0, chapterTitle: "The Symbol Dawn", exact: false,
    text: "Across the path of the divine Event the soul learns @, and a light that was not yet on earth begins its slow descent into the hours." },
  { vid: "prayers", chapterIndex: 0, chapterTitle: "November 1912", exact: true,
    text: "O Lord, in the silence of @ my adoration is beyond all words, my reverence is silent, and my heart overflows with gratitude." },
  { vid: "agenda-1", chapterIndex: 0, chapterTitle: "1958", exact: false,
    text: "The work of @ goes on in the cells of the body, slow and sure, until the old habit of death is undone and a new functioning is born." },
  { vid: "evening-talks", chapterIndex: 0, chapterTitle: "1923", exact: true,
    text: "When asked about @, Sri Aurobindo replied that the true movement is not effort but a quiet opening of the whole being to the Mother's force." },
];

function buildResults(ql, exact) {
  const safe = ql.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const re = new RegExp("(" + safe + ")", "ig");
  const out = [];
  SEARCH_CORPUS.forEach((c) => {
    const literal = c.text.replace("@", ql);
    const hasLiteral = literal.toLowerCase().includes(ql);
    if (exact && !c.exact && !hasLiteral) return;
    // place the query into the @ slot so every card reads naturally
    const filled = c.text.includes("@") ? c.text.replace("@", ql) : c.text;
    out.push({ ...c, html: filled.replace(re, "<mark>$1</mark>") });
  });
  return out;
}

/* ---------- MULTIMEDIA ------------------------------------- */
function MediaScreen({ route, go }) {
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
function DailyScreen({ route, go }) {
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

Object.assign(window, { BrowseScreen, VolumeScreen, SearchScreen, MediaScreen, DailyScreen, SavitriScreen });
