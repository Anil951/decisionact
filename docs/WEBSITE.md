# Working on the documentation website

The website uses React, React Router, and Vite. All website source, dependencies, and generated
output stay inside this `docs/` directory. Node.js 22.12 or newer is required.

From this directory:

```bash
npm install
npm run dev
```

Open http://127.0.0.1:4173/decisionact/ for the local preview. On Windows PowerShell, use
`npm.cmd` if your execution policy blocks `npm.ps1`.

To check the production build:

```bash
npm run build
npm run preview
```

Stop the development server before starting the production preview; both use port
4173. The static website is generated in `docs/dist/`. That directory is ignored
by Git and is the directory to upload when configuring a GitHub Pages deployment.
Building or previewing does not publish the website.

## Editing content and appearance

- Edit the Markdown guides in `docs/content/`.
- Edit `src/Overview.jsx` for the overview page.
- Edit `src/pages.json` for page order, titles, sidebar groups, source files, and nested section links.
- Edit the repository's `CHANGELOG.md` for release notes; the Changelog page renders that file directly.
- Keep old shared URLs working with redirects in `src/legacy-routes.js`.
- Edit `assets/site.css` for styles and responsive layouts.
- Shared React components in `src/` handle layout, themes, search, and code copying.

## Routes and deployment

The website is a single React application. Routes such as `/decisionact/quickstart`,
`/decisionact/models`, and `/decisionact/api-reference#model-adapters` switch content
inside the shared layout without reloading the document. Browser back/forward,
search results, and previous/next navigation use the same routes.

Only `index.html` is the application entry. The build also creates a small
`404.html` fallback for GitHub Pages. Opening or refreshing a direct route briefly
redirects through the entry page, then restores its path, query, and section before
React starts. There are no generated HTML files per guide. Unknown routes show
a page-not-found view with a link back to the documentation.

The base path is `/decisionact/` in `vite.config.js`, for local and GitHub Pages
URLs. The documentation workflow builds with `npm ci` and `npm run build`, then
uploads `docs/dist` to GitHub Pages. Publishing requires pushing the changes;
building or previewing locally does not deploy anything. The Python package and
PyPI publishing workflow remain separate.

## Documentation structure

The sidebar follows five sections: Get started, Core concepts, Examples, API
reference, and Releases. Releases contains the Changelog, also linked from the
version label in the sidebar footer. Core concepts contains Tools, Parameters, Intents, Outcomes, Decision
models, Memory and checkpoints, Middleware and human approval, and Execution flow.

Each concept explains its purpose, usage, behavior and limitations, and relevant
API links. Examples are independent of the order-agent tutorial; provider-backed
scripts state their environment requirements and include their own definitions.
Order and flight application walkthroughs stay in Quickstart and Examples.

Jev and Cloudflare Clef share the models page with nested section links. API
reference stays on one page with nested links to the public API groups.

The `pages.json` order also drives previous/next navigation and search. A page's
optional `sections` list contains `title` and `anchor` values for nested links;
each anchor must match a heading in that page. Content remains in `docs/content/`.
