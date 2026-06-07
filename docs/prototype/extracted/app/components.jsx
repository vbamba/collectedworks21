/* ============================================================
   Shared UI components — exported to window
   ============================================================ */
const { useState, useEffect, useRef } = React;

/* ---- Icons (simple line geometry) ------------------------- */
function Icon({ name, size = 22, stroke = 1.7, style }) {
  const p = {
    width: size, height: size, viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: stroke, strokeLinecap: "round",
    strokeLinejoin: "round", style,
  };
  const paths = {
    search: <><circle cx="11" cy="11" r="7" /><line x1="21" y1="21" x2="16.65" y2="16.65" /></>,
    menu: <><line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" /></>,
    close: <><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></>,
    chevronRight: <polyline points="9 6 15 12 9 18" />,
    chevronDown: <polyline points="6 9 12 15 18 9" />,
    chevronLeft: <polyline points="15 6 9 12 15 18" />,
    arrowLeft: <><line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" /></>,
    arrowRight: <><line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" /></>,
    home: <><path d="M3 11l9-8 9 8" /><path d="M5 10v10h14V10" /></>,
    book: <><path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z" /><line x1="9" y1="3" x2="9" y2="19" /></>,
    library: <><line x1="6" y1="4" x2="6" y2="20" /><line x1="11" y1="4" x2="11" y2="20" /><path d="M15 5l4 14" /></>,
    sun: <><circle cx="12" cy="12" r="4.2" /><line x1="12" y1="2.5" x2="12" y2="5" /><line x1="12" y1="19" x2="12" y2="21.5" /><line x1="2.5" y1="12" x2="5" y2="12" /><line x1="19" y1="12" x2="21.5" y2="12" /><line x1="5" y1="5" x2="6.7" y2="6.7" /><line x1="17.3" y1="17.3" x2="19" y2="19" /><line x1="5" y1="19" x2="6.7" y2="17.3" /><line x1="17.3" y1="6.7" x2="19" y2="5" /></>,
    moon: <path d="M21 12.8A8.5 8.5 0 1 1 11.2 3a6.6 6.6 0 0 0 9.8 9.8z" />,
    type: <><polyline points="4 7 4 4 20 4 20 7" /><line x1="12" y1="4" x2="12" y2="20" /><line x1="8" y1="20" x2="16" y2="20" /></>,
    bookmark: <path d="M6 3h12a1 1 0 0 1 1 1v17l-7-4-7 4V4a1 1 0 0 1 1-1z" />,
    play: <polygon points="7 4 20 12 7 20 7 4" />,
    headphones: <><path d="M4 14v-2a8 8 0 0 1 16 0v2" /><rect x="3" y="14" width="4" height="6" rx="1" /><rect x="17" y="14" width="4" height="6" rx="1" /></>,
    film: <><rect x="3" y="4" width="18" height="16" rx="2" /><line x1="8" y1="4" x2="8" y2="20" /><line x1="16" y1="4" x2="16" y2="20" /></>,
    settings: <><circle cx="12" cy="12" r="3" /><path d="M19.4 13a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-2.7 1.1V21a2 2 0 0 1-4 0v-.2A1.6 1.6 0 0 0 7 19.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.6 1.6 0 0 0 3 13H3a2 2 0 0 1 0-4h.1A1.6 1.6 0 0 0 4.6 7L4.5 7a2 2 0 1 1 2.8-2.8l.1.1A1.6 1.6 0 0 0 10 4.6V4a2 2 0 0 1 4 0v.1a1.6 1.6 0 0 0 2.7 1.1l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8V9a2 2 0 0 1 0 4z" /></>,
    minus: <line x1="5" y1="12" x2="19" y2="12" />,
    plus: <><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></>,
    download: <><path d="M12 3v12" /><polyline points="7 11 12 16 17 11" /><path d="M5 20h14" /></>,
    share: <><circle cx="6" cy="12" r="2.4" /><circle cx="18" cy="6" r="2.4" /><circle cx="18" cy="18" r="2.4" /><line x1="8.1" y1="10.9" x2="15.9" y2="7.1" /><line x1="8.1" y1="13.1" x2="15.9" y2="16.9" /></>,
    quote: <><path d="M9.5 6H6a1.2 1.2 0 0 0-1.2 1.2V11a1.2 1.2 0 0 0 1.2 1.2h2.3c0 2.2-.7 3.2-2.3 3.8" /><path d="M19 6h-3.5a1.2 1.2 0 0 0-1.2 1.2V11a1.2 1.2 0 0 0 1.2 1.2h2.3c0 2.2-.7 3.2-2.3 3.8" /></>,
    grid: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
    image: <><rect x="3" y="4" width="18" height="16" rx="2" /><circle cx="8.5" cy="9.5" r="1.6" /><path d="M21 16l-5-5L5 20" /></>,
    clock: <><circle cx="12" cy="12" r="9" /><polyline points="12 7 12 12 15 14" /></>,
    sparkle: <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" />,
  };
  return <svg {...p}>{paths[name] || null}</svg>;
}

/* ---- Striped placeholder (for portraits / imagery) -------- */
function Placeholder({ label, ratio = "3 / 4", rounded = 14, tone = "gold", style }) {
  const hue = tone === "rose" ? "12" : "78";
  return (
    <div style={{
      position: "relative", aspectRatio: ratio, borderRadius: rounded,
      overflow: "hidden",
      background: `repeating-linear-gradient(135deg, oklch(0.93 0.02 ${hue}) 0 10px, oklch(0.9 0.025 ${hue}) 10px 20px)`,
      border: "1px solid var(--line)", ...style,
    }}>
      <span style={{
        position: "absolute", left: "50%", bottom: 12, transform: "translateX(-50%)",
        fontFamily: "var(--ui)", fontSize: 10.5, letterSpacing: "0.08em",
        textTransform: "uppercase", color: "var(--ink-soft)",
        background: "var(--paper)", padding: "3px 8px", borderRadius: 20,
        whiteSpace: "nowrap", border: "1px solid var(--line)",
      }}>{label}</span>
    </div>
  );
}

/* ---- Author sigil (simple geometric mark) ----------------- */
function Sigil({ author, size = 34 }) {
  // Sri Aurobindo -> descending+ascending triangles (square motif), gold
  // The Mother -> concentric petals abstracted to circle+square, rose
  const c = author === "m" ? "var(--rose)" : author === "d" ? "var(--ink-soft)" : "var(--gold)";
  if (author === "d") {
    return (
      <svg width={size} height={size} viewBox="0 0 40 40" fill="none" stroke={c} strokeWidth="1.4">
        <circle cx="20" cy="20" r="13" opacity="0.5" />
        <path d="M20 7 L20 33 M7 20 L33 20" opacity="0.4" />
        <circle cx="20" cy="20" r="4" />
      </svg>
    );
  }
  if (author === "m") {
    return (
      <svg width={size} height={size} viewBox="0 0 40 40" fill="none" stroke={c} strokeWidth="1.4">
        <circle cx="20" cy="20" r="6" />
        <circle cx="20" cy="20" r="12" opacity="0.55" />
        <circle cx="20" cy="20" r="17.5" opacity="0.3" />
      </svg>
    );
  }
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none" stroke={c} strokeWidth="1.4">
      <polygon points="20,5 33,27 7,27" />
      <polygon points="20,35 7,13 33,13" opacity="0.5" />
      <rect x="12.5" y="12.5" width="15" height="15" opacity="0.3" />
    </svg>
  );
}

/* ---- Top bar ---------------------------------------------- */
function TopBar({ onMenu, onSearch, onHome, title, scrolled }) {
  return (
    <header className={"topbar" + (scrolled ? " is-scrolled" : "")}>
      <button className="iconbtn" onClick={onMenu} aria-label="Menu"><Icon name="menu" /></button>
      <button className="topbar-title" onClick={onHome}>
        {title || (<><span className="tb-mark"><Sigil author="sa" size={22} /></span><span>The Library</span></>)}
      </button>
      <button className="iconbtn" onClick={onSearch} aria-label="Search"><Icon name="search" /></button>
    </header>
  );
}

/* ---- Bottom navigation (mobile) --------------------------- */
function BottomNav({ route, go }) {
  const items = [
    { key: "home", label: "Home", icon: "home" },
    { key: "browse", label: "Library", icon: "library" },
    { key: "search", label: "Search", icon: "search" },
    { key: "media", label: "Listen", icon: "headphones" },
    { key: "daily", label: "Today", icon: "sparkle" },
  ];
  return (
    <nav className="bottomnav">
      {items.map((it) => {
        const active = route.name === it.key || (it.key === "browse" && (route.name === "volume" || route.name === "reader"));
        return (
          <button key={it.key} className={"bn-item" + (active ? " active" : "")} onClick={() => go({ name: it.key })}>
            <Icon name={it.icon} size={21} stroke={active ? 2 : 1.6} />
            <span>{it.label}</span>
          </button>
        );
      })}
    </nav>
  );
}

/* ---- Slide-in menu (full nav) ----------------------------- */
function MenuDrawer({ open, onClose, go }) {
  const sa = DATA.COLLECTIONS.filter((c) => c.author === "sa");
  const m = DATA.COLLECTIONS.filter((c) => c.author === "m");
  const d = DATA.COLLECTIONS.filter((c) => c.author === "d");
  return (
    <div className={"drawer-scrim" + (open ? " open" : "")} onClick={onClose}>
      <aside className={"drawer" + (open ? " open" : "")} onClick={(e) => e.stopPropagation()}>
        <div className="drawer-head">
          <span className="eyebrow">Menu</span>
          <button className="iconbtn" onClick={onClose} aria-label="Close"><Icon name="close" /></button>
        </div>
        <div className="drawer-scroll">
          <button className="drawer-link" onClick={() => { go({ name: "home" }); onClose(); }}>Home</button>
          <div className="drawer-group">
            <div className="drawer-group-title"><Sigil author="sa" size={20} /> Sri Aurobindo</div>
            {sa.map((c) => (
              <button key={c.id} className="drawer-sublink" onClick={() => { go({ name: "browse", collection: c.id }); onClose(); }}>
                {c.title} <em>{c.abbr}</em>
              </button>
            ))}
          </div>
          <div className="drawer-group">
            <div className="drawer-group-title"><Sigil author="m" size={20} /> The Mother</div>
            {m.map((c) => (
              <button key={c.id} className="drawer-sublink" onClick={() => { go({ name: "browse", collection: c.id }); onClose(); }}>
                {c.title} <em>{c.abbr}</em>
              </button>
            ))}
          </div>
          <div className="drawer-group">
            <div className="drawer-group-title"><Sigil author="d" size={20} /> The Disciples</div>
            {d.map((c) => (
              <button key={c.id} className="drawer-sublink" onClick={() => { go({ name: "browse", collection: c.id }); onClose(); }}>
                {c.title} <em>{c.abbr}</em>
              </button>
            ))}
          </div>
          <div className="drawer-group">
            <div className="drawer-group-title">Explore</div>
            <button className="drawer-sublink" onClick={() => { go({ name: "browse" }); onClose(); }}>All Volumes</button>
            <button className="drawer-sublink" onClick={() => { go({ name: "search" }); onClose(); }}>Search</button>
            <button className="drawer-sublink" onClick={() => { go({ name: "media" }); onClose(); }}>Audio &amp; Video</button>
            <button className="drawer-sublink" onClick={() => { go({ name: "daily" }); onClose(); }}>Thought for the Day</button>
            <button className="drawer-sublink" onClick={() => { go({ name: "browse", view: "savitri" }); onClose(); }}>Savitri</button>
          </div>
        </div>
      </aside>
    </div>
  );
}

/* ---- Volume card / row ------------------------------------ */
function VolumeCard({ v, go, variant = "card" }) {
  const c = DATA.collectionById(v.collection);
  if (variant === "row") {
    return (
      <button className="vol-row" onClick={() => go({ name: "volume", id: v.id })}>
        <span className="vr-spine" data-author={v.author}>{String(v.num).padStart(2, "0")}</span>
        <span className="vr-body">
          <span className="vr-title">{v.title}</span>
          <span className="vr-meta">{v.part ? v.part + " · " : ""}{c.abbr} · {v.pages} pp</span>
        </span>
        <Icon name="chevronRight" size={18} style={{ color: "var(--ink-faint)", flex: "0 0 auto" }} />
      </button>
    );
  }
  return (
    <button className="vol-card" onClick={() => go({ name: "volume", id: v.id })}>
      <span className="vc-cover" data-author={v.author}>
        <span className="vc-cover-num">{String(v.num).padStart(2, "0")}</span>
        <span className="vc-cover-title">{v.title}</span>
        <span className="vc-cover-sig"><Sigil author={v.author} size={26} /></span>
      </span>
      <span className="vc-title">{v.title}</span>
      <span className="vc-meta">{c.abbr}{v.part ? " · " + v.part : ""}</span>
    </button>
  );
}

/* ---- Section heading -------------------------------------- */
function SectionHead({ eyebrow, title, action, onAction }) {
  return (
    <div className="section-head">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h2 className="section-title">{title}</h2>
      </div>
      {action && <button className="text-link" onClick={onAction}>{action}<Icon name="chevronRight" size={15} /></button>}
    </div>
  );
}

Object.assign(window, { Icon, Placeholder, Sigil, TopBar, BottomNav, MenuDrawer, VolumeCard, SectionHead });
