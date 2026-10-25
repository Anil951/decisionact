import pages from './pages.json';

import changelog from '../../CHANGELOG.md?raw';

const sources = {
  ...import.meta.glob('../content/*.md', { query: '?raw', import: 'default', eager: true }),
  '../../CHANGELOG.md': changelog,
};

export function pageLink(href = '') {
  if (/^(?:[a-z][a-z\d+.-]*:|\/\/)/i.test(href)) return href;
  return href.replace(/^docs\/content\//, '').replace(/^(?:\.\.\/)?(README|[\w-]+)\.(?:md|html)(?=[?#]|$)/, (_, slug) => slug === 'README' || slug === 'index' ? '/' : `/${slug === 'CHANGELOG' ? 'changelog' : slug}`);
}

function cleanGuide(text) {
  return text
    .replace(/^\uFEFF/, '')
    .replace(/^# [^\n]+\r?\n/, '')
    .replace(/^\[Documentation\]\((?:\.\.\/)?README\.md\) \/ [^\n]+\r?\n/gm, '')
    .replace(/^Next: .*?$|^\[Back to documentation\].*?$/gm, '')
    .trim();
}

export const docs = pages.map((page) => ({
  ...page,
  url: page.slug === 'index' ? '/' : `/${page.slug}`,
  content: page.file ? cleanGuide(sources[`../${page.file}`]) : '',
}));

const overviewText = `Every action is a decision. Decision-Model-Driven Execution for Structured Agent Workflows.
Python agent framework. pip install decisionact. uv add decisionact. Python 3.10.
Single-agent single-intent execution. Jev and Cloudflare Clef models. Tools parameters intents outcomes.
Conversation memory SQLite checkpoints middleware human approval tool calls decision traces.
v0.1.2 calculator repeated tool calls dependent results structured state input confidence recheck.
max_calls renewable allowance max_call_limit hard cap limit_reached unfinished execution.
Future: single-agent multi-intent and multi-agent workflows.`;

export const searchIndex = docs.map((page) => ({
  ...page,
  text: (page.content || overviewText).replace(/```\w*\n|```|^#+\s*|[*`|]/gm, '').replace(/\s+/g, ' ').trim(),
}));
