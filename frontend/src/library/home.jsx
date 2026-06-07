/* ============================================================
   Home — Serene direction only.
   CHANGED: per the redesign decision, the prototype's A/B/C dir-switch
   and the Editorial/Portal variants are dropped; Serene is THE home.
   ============================================================ */
import React from 'react';
import { DATA } from './data.js';
import { Sigil, Icon, SectionHead, BookCard } from './components.jsx';
// CHANGED (Phase 3d): featured + collections come from the real book list.
import { useBooks, deriveCollections, collectionFullName } from './useBooks.js';

function todaysThought() {
  return DATA.THOUGHTS[new Date().getDate() % DATA.THOUGHTS.length];
}

const FEATURED_KEYWORDS = ['life divine', 'synthesis of yoga', 'savitri', 'letters on yoga', 'essays on the gita', 'prayers and meditations'];

export function HomeScreen({ go }) {
  const t = todaysThought();
  const books = useBooks();
  const collections = deriveCollections(books);
  let featured = FEATURED_KEYWORDS
    .map((kw) => books.find((b) => b.title.toLowerCase().includes(kw)))
    .filter(Boolean);
  if (featured.length === 0) featured = books.slice(0, 6);
  return (
    <div className="screen home-screen">
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
            {featured.map((b) => <BookCard key={`${b.collection}/${b.book_slug}`} b={b} go={go} />)}
          </div>
        </section>

        <section className="block">
          <SectionHead eyebrow="Collections" title="Browse editions" />
          <div className="coll-grid-2">
            {collections.map((c) => (
              <button key={c.name} className="coll-mini" data-author={c.author} onClick={() => go({ name: "browse", collection: c.name })}>
                <Sigil author={c.author} size={24} />
                <span className="cm-abbr">{c.name}</span>
                <span className="cm-name">{collectionFullName(c.name)}</span>
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
