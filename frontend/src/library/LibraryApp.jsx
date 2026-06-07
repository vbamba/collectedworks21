/* ============================================================
   Library app shell — ported from prototype app.jsx.
   CHANGED: ESM; Serene-fixed (homeDir/dir-switch removed); wrapped in
   .library-root so the scoped prototype styles never touch the existing
   Bootstrap pages. Internal state-machine routing (the prototype's own
   `route` object) is preserved for now; URL deep-linking comes later.
   ============================================================ */
import React, { useState, useEffect } from 'react';
import '../../../design/tokens.css';
import './styles.css';
import { TopBar, BottomNav, MenuDrawer } from './components.jsx';
import { HomeScreen } from './home.jsx';
import { BrowseScreen, VolumeScreen, SearchScreen, MediaScreen, DailyScreen } from './screens.jsx';
import { ReaderScreen } from './reader.jsx';

export default function LibraryApp() {
  const [route, setRoute] = useState({ name: "home" });
  const [menuOpen, setMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  const go = (r) => {
    setRoute(r);
    setMenuOpen(false);
    requestAnimationFrame(() => {
      const m = document.querySelector(".app-main");
      if (m) m.scrollTop = 0;
      window.scrollTo(0, 0);
    });
  };

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Reader is a full-screen takeover
  if (route.name === "reader") {
    return <div className="library-root"><ReaderScreen route={route} go={go} /></div>;
  }

  let screen;
  switch (route.name) {
    case "browse": screen = <BrowseScreen route={route} go={go} />; break;
    case "volume": screen = <VolumeScreen route={route} go={go} />; break;
    case "search": screen = <SearchScreen route={route} go={go} />; break;
    case "media": screen = <MediaScreen route={route} go={go} />; break;
    case "daily": screen = <DailyScreen route={route} go={go} />; break;
    default: screen = <HomeScreen go={go} />;
  }

  return (
    <div className="library-root">
      <div className="app">
        <TopBar
          scrolled={scrolled}
          onMenu={() => setMenuOpen(true)}
          onSearch={() => go({ name: "search" })}
          onHome={() => go({ name: "home" })}
        />
        <main className="app-main">{screen}</main>
        <BottomNav route={route} go={go} />
        <MenuDrawer open={menuOpen} onClose={() => setMenuOpen(false)} go={go} />
      </div>
    </div>
  );
}
