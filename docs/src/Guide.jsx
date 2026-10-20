import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSlug from 'rehype-slug';
import { Link } from 'react-router';
import CodeBlock from './CodeBlock';
import { pageLink } from './content';
import ExecutionDiagram from './ExecutionDiagram';

function Heading({ as: Tag, id, children }) {
  return <Tag id={id}>{children}<Link className="headerlink" to={`#${id}`} aria-label="Link to this section">#</Link></Tag>;
}

const components = {
  h2: ({ id, children }) => <Heading as="h2" id={id}>{children}</Heading>,
  h3: ({ id, children }) => <Heading as="h3" id={id}>{children}</Heading>,
  a: ({ href, children, title }) => /^(?:[a-z][a-z\d+.-]*:|\/\/)/i.test(href || '')
    ? <a href={href} title={title}>{children}</a>
    : <Link to={pageLink(href)} title={title}>{children}</Link>,
  pre: ({ children }) => {
    const child = Array.isArray(children) ? children[0] : children;
    const language = /language-([\w-]+)/.exec(child.props.className || '')?.[1] || 'text';
    return <CodeBlock language={language} code={String(child.props.children)} />;
  },
  table: ({ children }) => <div className="table-scroll" tabIndex={0} role="region" aria-label="Reference table"><table>{children}</table></div>,
};

export default function Guide({ page }) {
  return <><h1>{page.title}</h1><div className="prose">
    {page.slug === 'execution-flow' && <ExecutionDiagram />}
    <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSlug]} components={components}>{page.content}</Markdown>
  </div></>;
}
