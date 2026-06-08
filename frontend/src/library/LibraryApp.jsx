/* ============================================================
   Library app shell — ported from prototype app.jsx.
   CHANGED (Phase 3e): the prototype's in-memory state-machine routing is
   replaced with real URLs via react-router, so every view is deep-linkable,
   shareable, crawlable, and the browser Back button works. The screens still
   speak the same `route` object + `go()` API — only the backing store moved
   from useState to the URL.

   LIB_BASE is the path prefix. It's "/library" while the redesign is built
   out alongside the live site; at launch, dropping it to "" moves every view
   onto the canonical paths (/, /read/<coll>/<book>/<slug>, …) with no other
   code change.
   ============================================================ */
import React, { useState, useEffect, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import '../../../design/tokens.css';
import './styles.css';
import { TopBar, BottomNav, MenuDrawer } from './components.jsx';
import { HomeScreen } from './home.jsx';
import { BrowseScreen, VolumeScreen, SearchScreen, MediaScreen, DailyScreen } from './screens.jsx';
import { ReaderScreen } from './reader.jsx';

export const LIB_BASE = '/library';

// URL (pathname + search) -> the `route` object the screens consume.
export function parseRoute(pathname, search) {
  const rel = pathname.replace(new RegExp('^' + LIB_BASE + '/?'), '');
  const parts = rel.split('/').filter(Boolean).map(decodeURIComponent);
  const sp = new URLSearchParams(search);
  if (parts.length === 0) return { name: 'home' };
  const [head, ...rest] = parts;
  switch (head) {
    case 'browse':
      return { name: 'browse', collection: rest[0] || undefined, author: sp.get('a') || 'all' };
    case 'savitri':
      return { name: 'browse', view: 'savitri' };
    case 'search':
      return { name: 'search', q: sp.get('q') || '' };
    case 'volume':
      return { name: 'volume', collection: rest[0], bookSlug: rest[1] };
    case 'read':
      return {
        name: 'reader',
        chapter: { slugMode: true, collection: rest[0], bookSlug: rest[1], slug: rest[2] },
        query: sp.get('q') || '',
        resultType: sp.get('rt') || 'all',
      };
    case 'readq': // query-mode fallback for legacy rows without a slug
      return {
        name: 'reader',
        chapter: { slugMode: false, collection: sp.get('cf'), bookFolder: sp.get('bf'), sectionFilename: sp.get('sf') },
        query: sp.get('q') || '',
        resultType: sp.get('rt') || 'all',
      };
    case 'listen':
      return { name: 'media' };
    case 'today':
      return { name: 'daily' };
    default:
      return { name: 'home' };
  }
}

// `route` object -> URL (pathname + search).
export function routeToPath(r) {
  const e = encodeURIComponent;
  switch (r.name) {
    case 'search':
      return LIB_BASE + '/search' + (r.q ? `?q=${e(r.q)}` : '');
    case 'browse':
      if (r.view === 'savitri') return LIB_BASE + '/savitri';
      if (r.collection) return `${LIB_BASE}/browse/${e(r.collection)}`;
      if (r.author && r.author !== 'all') return `${LIB_BASE}/browse?a=${e(r.author)}`;
      return LIB_BASE + '/browse';
    case 'volume': {
      const b = r.book || {};
      return `${LIB_BASE}/volume/${e(b.collection || r.collection)}/${e(b.book_slug || r.bookSlug)}`;
    }
    case 'media': return LIB_BASE + '/listen';
    case 'daily': return LIB_BASE + '/today';
    case 'reader': {
      const c = r.chapter || {};
      const qs = new URLSearchParams();
      if (r.query) qs.set('q', r.query);
      if (r.resultType && r.resultType !== 'all') qs.set('rt', r.resultType);
      const s = qs.toString();
      if (c.collection && c.bookSlug && c.slug) {
        return `${LIB_BASE}/read/${e(c.collection)}/${e(c.bookSlug)}/${e(c.slug)}` + (s ? `?${s}` : '');
      }
      const p = new URLSearchParams({ cf: c.collection || '', bf: c.bookFolder || '', sf: c.sectionFilename || '' });
      if (r.query) p.set('q', r.query);
      if (r.resultType && r.resultType !== 'all') p.set('rt', r.resultType);
      return `${LIB_BASE}/readq?${p.toString()}`;
    }
    default:
      return LIB_BASE;
  }
}

export default function LibraryApp() {
  const location = useLocation();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  // Merge any navigation state (e.g. the full book object passed to avoid a
  // lookup flash) onto the URL-derived route.
  const route = useMemo(
    () => ({ ...parseRoute(location.pathname, location.search), ...(location.state || {}) }),
    [location.pathname, location.search, location.state]
  );

  const go = (r) => {
    setMenuOpen(false);
    navigate(routeToPath(r), { state: r.book ? { book: r.book } : undefined });
    requestAnimationFrame(() => {
      const m = document.querySelector('.app-main');
      if (m) m.scrollTop = 0;
      window.scrollTo(0, 0);
    });
  };
  const goBack = () => navigate(-1);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  // Reader is a full-screen takeover. The MenuDrawer is still mounted so
  // navigation is reachable while reading.
  if (route.name === 'reader') {
    return (
      <div className="library-root">
        <ReaderScreen route={route} go={go} goBack={goBack} onMenu={() => setMenuOpen(true)} />
        <MenuDrawer open={menuOpen} onClose={() => setMenuOpen(false)} go={go} />
      </div>
    );
  }

  let screen;
  switch (route.name) {
    case 'browse': screen = <BrowseScreen route={route} go={go} />; break;
    case 'volume': screen = <VolumeScreen route={route} go={go} />; break;
    case 'search': screen = <SearchScreen route={route} go={go} />; break;
    case 'media': screen = <MediaScreen route={route} go={go} />; break;
    case 'daily': screen = <DailyScreen route={route} go={go} />; break;
    default: screen = <HomeScreen go={go} />;
  }

  return (
    <div className="library-root">
      <div className="app">
        <TopBar
          scrolled={scrolled}
          onMenu={() => setMenuOpen(true)}
          onSearch={() => go({ name: 'search' })}
          onHome={() => go({ name: 'home' })}
        />
        <main className="app-main">{screen}</main>
        <BottomNav route={route} go={go} />
        <MenuDrawer open={menuOpen} onClose={() => setMenuOpen(false)} go={go} />
      </div>
    </div>
  );
}
