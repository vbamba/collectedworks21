/* ============================================================
   Home — three switchable directions (A Serene, B Editorial, C Portal)
   ============================================================ */

function HomeScreen({ route, go, dir, setDir }) {
  return (
    <div className="screen home-screen">
      <div className="dir-switch">
        <span className="dir-label">Home direction</span>
        <div className="seg sm">
          {[["serene", "Serene"], ["editorial", "Editorial"], ["portal", "Portal"]].map(([k, l]) => (
            <button key={k} className={"seg-btn" + (dir === k ? " active" : "")} onClick={() => setDir(k)}>{l}</button>
          ))}
        </div>
      </div>
      {dir === "serene" && <HomeSerene go={go} />}
      {dir === "editorial" && <HomeEditorial go={go} />}
      {dir === "portal" && <HomePortal go={go} />}
    </div>
  );
}

function todaysThought() {
  return DATA.THOUGHTS[new Date().getDate() % DATA.THOUGHTS.length];
}

/* ---------- A · SERENE ------------------------------------- */
function HomeSerene({ go }) {
  const t = todaysThought();
  return (
    <div className="home home-serene">
      <section className="serene-hero">
        <div className="serene-sig"><Sigil author="sa" size={46} /></div>
        <h1 className="serene-h1">The Collected Works</h1>
        <p className="serene-sub">of Sri Aurobindo &amp; the Mother</p>
        <button className="search-pill" onClick={() => go({ name: "search" })}>
          <Icon name="search" size={18} /> Search the works…
        </button>
      </section>

      <section className="serene-quote">
        <Icon name="quote" size={26} style={{ color: "var(--gold)" }} />
        <blockquote>{t.text}</blockquote>
        <cite>{t.author} · {t.source}</cite>
        <button className="text-link center" onClick={() => go({ name: "daily" })}>Thought for the day <Icon name="chevronRight" size={15} /></button>
      </section>

      <section className="block">
        <SectionHead eyebrow="Begin here" title="Featured" action="All volumes" onAction={() => go({ name: "browse" })} />
        <div className="hscroll">
          {DATA.featured.map((v) => <VolumeCard key={v.id} v={v} go={go} />)}
        </div>
      </section>

      <section className="block">
        <SectionHead eyebrow="Collections" title="Browse editions" />
        <div className="coll-grid-2">
          {DATA.COLLECTIONS.map((c) => (
            <button key={c.id} className="coll-mini" data-author={c.author} onClick={() => go({ name: "browse", collection: c.id })}>
              <Sigil author={c.author} size={24} />
              <span className="cm-abbr">{c.abbr}</span>
              <span className="cm-name">{c.title}</span>
              <span className="cm-count">{c.count} volumes</span>
            </button>
          ))}
          <button className="coll-mini savitri-mini" onClick={() => go({ name: "browse", view: "savitri" })}>
            <Icon name="sparkle" size={22} style={{ color: "var(--gold)" }} />
            <span className="cm-abbr">SAVITRI</span>
            <span className="cm-name">The epic poem</span>
            <span className="cm-count">Read &amp; listen</span>
          </button>
        </div>
      </section>

      <ListenStrip go={go} />
    </div>
  );
}

/* ---------- B · EDITORIAL ---------------------------------- */
function HomeEditorial({ go }) {
  const t = todaysThought();
  const savitri = DATA.volumeById("savitri");
  return (
    <div className="home home-editorial">
      <section className="ed-masthead">
        <div className="ed-rule"><span>The Collected Works</span><span>est. Pondicherry</span></div>
        <h1 className="ed-title">Sri Aurobindo<span>&amp; the Mother</span></h1>
        <p className="ed-lede">The complete writings — philosophy, poetry, yoga and the record of an evolutionary adventure — freely readable in one library.</p>
      </section>

      <button className="ed-feature" onClick={() => go({ name: "reader", id: savitri.id })}>
        <Placeholder label="cover art — Savitri" ratio="16 / 10" rounded={0} style={{ borderRadius: 16 }} />
        <div className="ed-feature-body">
          <div className="eyebrow">Featured · Poetry</div>
          <h2>Savitri</h2>
          <p>A Legend and a Symbol — the epic in nearly 24,000 lines.</p>
          <span className="text-link">Read the poem <Icon name="arrowRight" size={16} /></span>
        </div>
      </button>

      <section className="ed-grid">
        <div className="ed-quote">
          <Icon name="quote" size={24} style={{ color: "var(--gold)" }} />
          <blockquote>{t.text}</blockquote>
          <cite>— {t.author}, {t.source}</cite>
        </div>
        <div className="ed-list">
          <div className="result-label">More to read</div>
          {DATA.featured.concat(DATA.volumeById("essays-gita")).slice(0, 4).map((v) => (
            <VolumeCard key={v.id} v={v} go={go} variant="row" />
          ))}
        </div>
      </section>

      <section className="block">
        <SectionHead eyebrow="Editions" title="The collections" action="See all" onAction={() => go({ name: "browse" })} />
        <div className="ed-coll-row">
          {DATA.COLLECTIONS.map((c) => (
            <button key={c.id} className="ed-coll" data-author={c.author} onClick={() => go({ name: "browse", collection: c.id })}>
              <span className="ed-coll-abbr">{c.abbr}</span>
              <span className="ed-coll-count">{c.count}</span>
            </button>
          ))}
        </div>
      </section>

      <ListenStrip go={go} />
    </div>
  );
}

/* ---------- C · PORTAL ------------------------------------- */
function HomePortal({ go }) {
  const t = todaysThought();
  return (
    <div className="home home-portal">
      <section className="portal-split">
        <button className="portal-half sa" onClick={() => go({ name: "browse", author: "sa" })}>
          <Placeholder label="photo" ratio="1 / 1" tone="gold" rounded={999} style={{ width: 96, margin: "0 auto" }} />
          <Sigil author="sa" size={30} />
          <span className="portal-name">Sri Aurobindo</span>
          <span className="portal-meta">Philosophy · Yoga · Poetry</span>
          <span className="portal-enter">Enter <Icon name="arrowRight" size={15} /></span>
        </button>
        <button className="portal-half m" onClick={() => go({ name: "browse", author: "m" })}>
          <Placeholder label="photo" ratio="1 / 1" tone="rose" rounded={999} style={{ width: 96, margin: "0 auto" }} />
          <Sigil author="m" size={30} />
          <span className="portal-name">The Mother</span>
          <span className="portal-meta">Prayers · Talks · Agenda</span>
          <span className="portal-enter">Enter <Icon name="arrowRight" size={15} /></span>
        </button>
      </section>

      <button className="portal-quote" onClick={() => go({ name: "daily" })}>
        <blockquote>{t.text}</blockquote>
        <cite>{t.author}</cite>
      </button>

      <section className="block">
        <SectionHead eyebrow="Quick access" title="Open a volume" action="Library" onAction={() => go({ name: "browse" })} />
        <div className="hscroll">
          {DATA.featured.map((v) => <VolumeCard key={v.id} v={v} go={go} />)}
        </div>
      </section>

      <section className="block">
        <div className="portal-tiles">
          <button className="ptile" onClick={() => go({ name: "browse", view: "savitri" })}><Icon name="sparkle" size={20} /><span>Savitri</span></button>
          <button className="ptile" onClick={() => go({ name: "media" })}><Icon name="headphones" size={20} /><span>Listen</span></button>
          <button className="ptile" onClick={() => go({ name: "search" })}><Icon name="search" size={20} /><span>Search</span></button>
          <button className="ptile" onClick={() => go({ name: "daily" })}><Icon name="sparkle" size={20} /><span>Today</span></button>
        </div>
      </section>
    </div>
  );
}

/* ---------- shared listen strip ---------------------------- */
function ListenStrip({ go }) {
  return (
    <section className="block">
      <SectionHead eyebrow="Multimedia" title="Listen" action="All audio" onAction={() => go({ name: "media" })} />
      <div className="hscroll">
        {DATA.MEDIA.filter((m) => m.kind === "audio").slice(0, 4).map((m) => (
          <button key={m.id} className="listen-card" onClick={() => go({ name: "media" })}>
            <span className="lc-thumb" data-kind="audio"><Icon name="play" size={20} /></span>
            <span className="lc-title">{m.title}</span>
            <span className="lc-meta">{m.duration}</span>
          </button>
        ))}
      </div>
    </section>
  );
}

Object.assign(window, { HomeScreen });
