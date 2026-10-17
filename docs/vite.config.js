import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Pages serves 404.html for direct requests to client-side routes. Redirect
// through index, which restores the requested URL before React starts.
function githubPagesFallback() {
  let base;
  return {
    name: 'decisionact-github-pages-fallback',
    configResolved(config) { base = config.base; },
    generateBundle() {
      this.emitFile({
        type: 'asset',
        fileName: '404.html',
        source: `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex"><title>DecisionAct documentation</title>
<script>
  const base = ${JSON.stringify(base)};
  if (location.pathname.startsWith(base)) {
    const target = new URL(base, location.origin);
    target.searchParams.set('__docs_route', location.pathname.slice(base.length) + location.search + location.hash);
    location.replace(target.href);
  }
</script></head><body><p>Opening documentation…</p><a href="${base}">Go to DecisionAct documentation</a><noscript><p>JavaScript is required to open this documentation route.</p></noscript></body></html>`,
      });
    },
  };
}

export default defineConfig({
  root: fileURLToPath(new URL('.', import.meta.url)),
  base: '/decisionact/',
  plugins: [react(), githubPagesFallback()],
  server: { host: '127.0.0.1', port: 4173, strictPort: true },
  preview: { host: '127.0.0.1', port: 4173, strictPort: true },
});
