/* ============================================================
   App shell + router
   ============================================================ */
function App() {
  const [route, setRoute] = useState({ name: "home" });
  const [menuOpen, setMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [homeDir, setHomeDir] = useState(() => localStorage.getItem("sa_homedir") || "serene");

  const setDir = (d) => { setHomeDir(d); localStorage.setItem("sa_homedir", d); };

  const go = (r) => {
    setRoute(r);
    setMenuOpen(false);
    // scroll the main region to top on navigation
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
    return <ReaderScreen route={route} go={go} />;
  }

  let screen;
  switch (route.name) {
    case "browse": screen = <BrowseScreen route={route} go={go} />; break;
    case "volume": screen = <VolumeScreen route={route} go={go} />; break;
    case "search": screen = <SearchScreen route={route} go={go} />; break;
    case "media": screen = <MediaScreen route={route} go={go} />; break;
    case "daily": screen = <DailyScreen route={route} go={go} />; break;
    default: screen = <HomeScreen route={route} go={go} dir={homeDir} setDir={setDir} />;
  }

  const titleMap = { browse: null, volume: null, search: null, media: null, daily: null };

  return (
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
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
