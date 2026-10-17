import { useEffect, useMemo, useRef, useState } from 'react';
import { searchIndex } from './content';
import { Link } from 'react-router';
import Icon from './Icon';

export default function Search({ open, onClose }) {
  const dialog = useRef(null);
  const input = useRef(null);
  const results = useRef(null);
  const [query, setQuery] = useState('');

  useEffect(() => {
    if (open) {
      if (!dialog.current.open) dialog.current.showModal();
      input.current.focus();
    } else if (dialog.current.open) dialog.current.close();
  }, [open]);

  const matches = useMemo(() => {
    const words = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
    return searchIndex.map((page) => {
      const text = `${page.title} ${page.text}`.toLowerCase();
      const score = words.every((word) => text.includes(word))
        ? words.reduce((sum, word) => sum + (page.title.toLowerCase().includes(word) ? 10 : 1), 0) : -1;
      const position = words.length ? page.text.toLowerCase().indexOf(words[0]) : 0;
      const start = Math.max(0, position - 50);
      return { ...page, score, excerpt: `${start ? '…' : ''}${page.text.slice(start, start + 145)}…` };
    }).filter((page) => page.score >= 0).sort((a, b) => b.score - a.score).slice(0, 9);
  }, [query]);

  function onKeyDown(event) {
    if (event.key === 'ArrowDown') { event.preventDefault(); results.current.querySelector('a')?.focus(); }
    if (event.key === 'Enter') results.current.querySelector('a')?.click();
  }

  return <dialog ref={dialog} className="search-dialog" aria-label="Search documentation" onClose={onClose} onCancel={onClose} onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <div className="search-bar"><Icon name="search" /><label className="sr-only" htmlFor="docs-search">Search documentation</label>
      <input ref={input} id="docs-search" type="search" placeholder="Search the documentation…" autoComplete="off" value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={onKeyDown} />
      <button className="icon-button" data-search-close type="button" onClick={onClose} aria-label="Close search"><Icon name="close" /></button>
    </div>
    <div ref={results} className="search-results" aria-live="polite">{matches.length
      ? matches.map((page) => <Link className="search-result" to={page.url} key={page.slug} onClick={onClose}><strong>{page.title}</strong><span>{page.excerpt}</span></Link>)
      : <p className="search-empty">No matching pages. Try “model”, “approval”, or “Agent.turn”.</p>}
    </div>
    <div className="search-footer">Search all guides and API reference · ↓ to results · Esc to close</div>
  </dialog>;
}
