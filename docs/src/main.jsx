import React from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation } from 'react-router';
import App from './App';
import { docs } from './content';
import Guide from './Guide';
import Overview from './Overview';
import { legacyRoutes } from './legacy-routes';
import '../assets/site.css';

function NotFound() {
  return <div className="prose"><h1>Page not found</h1><p>This documentation page does not exist.</p><Link className="button" to="/">Back to documentation</Link></div>;
}

function LegacyRedirect({ slug }) {
  const location = useLocation();
  const rule = legacyRoutes[slug];
  const target = rule[location.hash] || `${rule.default}${location.hash}`;
  const [pathname, hash = ''] = target.split('#');
  return <Navigate replace to={{ pathname, search: location.search, hash: hash ? `#${hash}` : '' }} />;
}

createRoot(document.getElementById('root')).render(<React.StrictMode>
  <BrowserRouter basename={import.meta.env.BASE_URL}>
    <Routes>
      <Route element={<App />}>
        <Route index element={<Overview />} />
        {docs.filter((page) => page.slug !== 'index').map((page) => <Route key={page.slug} path={page.slug} element={<Guide page={page} />} />)}
        {Object.keys(legacyRoutes).map((slug) => <Route key={slug} path={slug} element={<LegacyRedirect slug={slug} />} />)}
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  </BrowserRouter>
</React.StrictMode>);
