import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, Outlet, useLocation } from 'react-router';
import { docs } from './content';
import Icon from './Icon';
import Search from './Search';

const REPO = 'https://github.com/Anil951/decisionact';

function useMedia(query) {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const media = window.matchMedia(query);
    const update = (event) => setMatches(event.matches);
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, [query]);
  return matches;
}

function useTheme() {
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme || 'light');
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.querySelector('meta[name="theme-color"]').content = theme === 'dark' ? '#171a19' : '#f7f7f0';
  }, [theme]);
  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    function update(event) {
      let saved;
      try { saved = localStorage.getItem('decisionact-theme'); } catch { /* Device theme remains available. */ }
      if (saved !== 'light' && saved !== 'dark') setTheme(event.matches ? 'dark' : 'light');
    }
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  const toggle = () => {
    const next = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    try { localStorage.setItem('decisionact-theme', next); } catch { /* Keep the in-page setting. */ }
  };
  return [theme, toggle];
}

function Sidebar({ page, mobile, open, onNavigate }) {
  const location = useLocation();
  const groups = [...new Set(docs.map((item) => item.group))];
  return <aside className="sidebar" id="sidebar" aria-label="Documentation sidebar" inert={mobile && !open}>
    <nav aria-label="Documentation">{groups.map((group) => <div className="nav-group" key={group}>
      <p className="nav-label">{group}</p>
      {docs.filter((item) => item.group === group).map((item) => <div key={item.slug}>
        <Link className="nav-link" to={item.url} aria-current={item.slug === page.slug ? 'page' : undefined} onClick={onNavigate}><Icon name={item.icon} />{item.title}</Link>
        {item.sections && <div className="nav-subnav">{item.sections.map((section) => <Link key={section.anchor} className="nav-sublink" to={`${item.url}#${section.anchor}`} aria-current={item.slug === page.slug && location.hash === `#${section.anchor}` ? 'location' : undefined} onClick={onNavigate}>{section.title}</Link>)}</div>}
      </div>)}
    </div>)}</nav>
    <div className="sidebar-footer"><div className="version"><span className="status-dot" />v0.1.1 <span className="tag">Latest</span></div>Every action is a decision.</div>
  </aside>;
}

function TableOfContents({ content, page }) {
  const [headings, setHeadings] = useState([]);
  const [active, setActive] = useState('');
  useEffect(() => {
    setActive('');
    const nodes = [...content.current.querySelectorAll('h2[id], h3[id]')];
    setHeadings(nodes.map((node) => ({
      id: node.id,
      level: node.tagName,
      title: [...node.childNodes].filter((child) => !child.classList?.contains('headerlink') && !child.classList?.contains('tag')).map((child) => child.textContent).join('').trim(),
    })));
    if (!('IntersectionObserver' in window)) return;
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => { if (entry.isIntersecting) setActive(entry.target.id); });
    }, { rootMargin: '-90px 0px -65% 0px' });
    nodes.forEach((node) => observer.observe(node));
    return () => observer.disconnect();
  }, [content, page.slug]);

  const source = page.file || 'src/Overview.jsx';
  return <aside className="toc" aria-label="On this page"><p className="toc-title">On this page</p>
    <nav className="toc-sections">{headings.map((heading) => <Link key={heading.id} to={`${page.url}#${heading.id}`} className={`${heading.level === 'H3' ? 'subheading ' : ''}${active === heading.id ? 'active' : ''}`}>{heading.title}</Link>)}</nav>
    <div className="toc-bottom"><a href={`${REPO}/blob/main/docs/${source}`} target="_blank" rel="noopener noreferrer">View page source ↗</a><a href={`${REPO}/issues`} target="_blank" rel="noopener noreferrer">Report an issue ↗</a></div>
  </aside>;
}

function PageNavigation({ index }) {
  const previous = docs[index - 1];
  const next = docs[index + 1];
  return <nav className="page-nav" aria-label="Previous and next pages">
    {previous && <Link to={previous.url} rel="prev"><small>← Previous</small><span>{previous.title}</span></Link>}
    {next && <Link className="next" to={next.url} rel="next"><small>Next →</small><span>{next.title}</span></Link>}
  </nav>;
}

export default function App() {
  const location = useLocation();
  const index = docs.findIndex((item) => item.url === (location.pathname.replace(/\/$/, '') || '/'));
  const page = docs[index] || { slug: 'not-found', title: 'Page not found' };
  const [theme, toggleTheme] = useTheme();
  const mobile = useMedia('(max-width: 900px)');
  const [menuOpen, setMenuOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const menuButton = useRef(null);
  const content = useRef(null);
  const closeSearch = useCallback(() => setSearchOpen(false), []);
  const openSearch = useCallback(() => { setMenuOpen(false); setSearchOpen(true); }, []);

  useEffect(() => { setMenuOpen(false); }, [mobile]);
  useEffect(() => { setMenuOpen(false); setSearchOpen(false); }, [location.pathname]);
  useEffect(() => {
    document.body.classList.toggle('menu-open', mobile && menuOpen);
    return () => document.body.classList.remove('menu-open');
  }, [mobile, menuOpen]);
  useEffect(() => {
    function keydown(event) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); openSearch(); }
      if (event.key === 'Escape' && menuOpen) { setMenuOpen(false); menuButton.current.focus(); }
    }
    document.addEventListener('keydown', keydown);
    return () => document.removeEventListener('keydown', keydown);
  }, [menuOpen, openSearch]);
  useEffect(() => {
    document.title = `${page.title} · DecisionAct`;
    if (location.hash) {
      try { document.getElementById(decodeURIComponent(location.hash.slice(1)))?.scrollIntoView({ behavior: 'instant', block: 'start' }); } catch { /* Ignore malformed hashes. */ }
    } else {
      window.scrollTo({ top: 0, behavior: 'instant' });
    }
  }, [location.pathname, location.hash, location.key, page.title]);

  return <>
    <Link className="skip-link" to={`${location.pathname}#main-content`}>Skip to content</Link>
    <header className="topbar">
      <button ref={menuButton} className="icon-button menu-button" type="button" data-menu-toggle onClick={() => setMenuOpen(!menuOpen)} aria-label={`${menuOpen ? 'Close' : 'Open'} navigation`} aria-expanded={menuOpen} aria-controls="sidebar"><Icon name="menu" /></button>
      <Link className="brand" to="/" aria-label="DecisionAct documentation home"><span className="brand-wordmark"><em>Decision</em><span className="brand-act">Act</span></span><span className="brand-divider" /><span className="brand-docs">docs</span></Link>
      <div className="top-actions">
        <button className="header-search" type="button" data-search-open onClick={openSearch} aria-label="Search documentation" aria-haspopup="dialog" title="Search documentation (Ctrl K)"><Icon name="search" /><span>Search docs…</span></button>
        <a className="top-link" href={REPO} target="_blank" rel="noopener noreferrer">GitHub <Icon name="external" /></a>
        <a className="top-link pypi-link" href="https://pypi.org/project/decisionact/" target="_blank" rel="noopener noreferrer">PyPI <Icon name="external" /></a>
        <button className="icon-button" type="button" data-theme-toggle onClick={toggleTheme} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`} title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}><Icon name="moon" className="theme-moon" /><Icon name="sun" className="theme-sun" /></button>
      </div>
    </header>
    <button className="mobile-backdrop" type="button" onClick={() => setMenuOpen(false)} aria-label="Close navigation" />
    <Sidebar page={page} mobile={mobile} open={menuOpen} onNavigate={() => setMenuOpen(false)} />
    <div className="layout">
      <main ref={content} id="main-content" tabIndex={-1}>
        <div className="page-topline">
          <div className="breadcrumb"><Link to="/">Documentation</Link><Icon name="chevron" />{page.group && <><span>{page.group}</span><Icon name="chevron" /></>}<span>{page.title}</span></div>
          {page.slug === 'index' && <div className="hero-actions"><Link className="button primary" to="/quickstart">Build your first agent <Icon name="arrow" /></Link><Link className="button" to="/api-reference">Explore the API</Link></div>}
        </div>
        <Outlet />
        {index >= 0 && <PageNavigation index={index} />}
        <footer className="page-footer"><span>© 2026 AnilKumarBorige · MIT License</span><a href={`${REPO}/issues`} target="_blank" rel="noopener noreferrer">Help improve these docs ↗</a></footer>
      </main>
      {index >= 0 && <TableOfContents content={content} page={page} />}
    </div>
    <Search open={searchOpen} onClose={closeSearch} />
  </>;
}
