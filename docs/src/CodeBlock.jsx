import { useEffect, useMemo, useRef, useState } from 'react';
import hljs from 'highlight.js/lib/core';
import python from 'highlight.js/lib/languages/python';
import bash from 'highlight.js/lib/languages/bash';
import powershell from 'highlight.js/lib/languages/powershell';
import plaintext from 'highlight.js/lib/languages/plaintext';
import Icon from './Icon';

hljs.registerLanguage('python', python);
hljs.registerLanguage('bash', bash);
hljs.registerLanguage('powershell', powershell);
hljs.registerLanguage('text', plaintext);

async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    try { await navigator.clipboard.writeText(text); return; } catch { /* Try selection fallback. */ }
  }
  const input = document.createElement('textarea');
  input.value = text;
  input.setAttribute('readonly', '');
  input.style.cssText = 'position:fixed;top:-9999px;left:-9999px';
  document.body.append(input);
  try {
    input.select();
    if (!document.execCommand('copy')) throw new Error('Clipboard unavailable');
  } finally { input.remove(); }
}

export default function CodeBlock({ code, language = 'text' }) {
  const [status, setStatus] = useState('Copy');
  const pre = useRef(null);
  const timer = useRef(null);
  const highlighted = useMemo(() => hljs.highlight(code, {
    language: hljs.getLanguage(language) ? language : 'text',
  }).value, [code, language]);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  async function copy() {
    window.clearTimeout(timer.current);
    try {
      await copyText(code.replace(/\n$/, ''));
      setStatus('Copied!');
    } catch {
      setStatus('Select code');
      const range = document.createRange();
      range.selectNodeContents(pre.current);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
    }
    timer.current = window.setTimeout(() => setStatus('Copy'), 2000);
  }

  const label = { python: 'Python', bash: 'Terminal', powershell: 'PowerShell', text: 'Output' }[language] || language;
  return <div className="code-block">
    <div className="code-header"><span>{label}</span>
      <button className="copy-code" type="button" onClick={copy} aria-label={status === 'Copied!' ? 'Code copied' : 'Copy code to clipboard'}>
        <Icon name="copy" /><span aria-live="polite">{status}</span>
      </button>
    </div>
    <div className="codehilite"><pre ref={pre} tabIndex={0}><code dangerouslySetInnerHTML={{ __html: highlighted }} /></pre></div>
  </div>;
}
