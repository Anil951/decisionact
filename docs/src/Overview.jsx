import CodeBlock from './CodeBlock';
import Icon from './Icon';
import Workflow from './Workflow';
import { Link } from 'react-router';

const cards = [
  ['quickstart', 'Your first agent', 'code', 'Install the package and run an order-status agent, step by step.'],
  ['tools', 'Explore core concepts', 'layers', 'Understand tools, parameters, intents, and outcomes with independent examples.'],
  ['models', 'Choose a decision model', 'model', 'Connect Jev or Cloudflare Clef with your provider credentials.'],
  ['middleware-and-approval', 'Add memory & approval', 'approval', 'Keep context, persist sessions, and review actions before they run.'],
];

function Section({ id, children }) {
  return <h2 id={id}>{children}<Link className="headerlink" to={`#${id}`} aria-label="Link to this section">#</Link></h2>;
}

export default function Overview() {
  return <>
    <section className="hero">
      <div className="eyebrow"><span className="status-dot" />Python agent framework · v0.1.1</div>
      <h1>Every action is a <em>decision.</em></h1>
      <p className="hero-subtitle">Decision-Model-Driven Execution for Structured Agent Workflows</p>
    </section>
    <section className="workflow" aria-label="How DecisionAct handles a request">
      <div className="workflow-setup">
        <p className="workflow-label">Configuration</p>
        <p>Define <Link to="/intents">intents</Link>, <Link to="/tools">tools</Link>, and <Link to="/parameters">params</Link> with descriptions. Add intent context to guide the workflow, and define <Link to="/outcomes">outcomes</Link> with descriptions and reply templates. Use <Link to="/models">decision models</Link> to guide execution.</p>
        <p className="workflow-summary">Your agent goes beyond fixed if/else rules: decision models interpret natural-language requests and choose actions, while replies come from your predefined templates.</p>
      </div>
      <Workflow />
      <p className="workflow-note">Some intents can reach an outcome without running tools. Missing-input questions can pause the flow until the user replies.</p>
    </section>
    <div className="prose">
      <Section id="installation">A small install. A structured start.</Section>
      <p>Use Python 3.10 or newer. Install with pip, or add DecisionAct to your uv project.</p>
      <div className="install-grid"><CodeBlock code="pip install decisionact" language="bash" /><CodeBlock code="uv add decisionact" language="bash" /></div>
      <p>Jev and Clef run on their providers’ servers. The package includes the HTTP client and TypeSafe SDK; model weights are not downloaded.</p>
      <p>See <Link to="/installation">Installation</Link> for requirements and an installation check.</p>
      <Section id="start-building">Find your next step</Section>
      <div className="guide-grid">{cards.map(([slug, title, icon, text]) => <Link className="guide-card" to={`/${slug}`} key={slug}>
        <div className="card-top"><Icon name={icon} /><Icon name="arrow" /></div><strong>{title}</strong><p>{text}</p>
      </Link>)}</div>
      <Section id="available-now">Available in v0.1.1 <span className="tag">Latest version</span></Section>
      <p>One agent handles one intent per message. An intent can involve several tool calls, missing-input questions, and approval steps.</p>
      <ul>
        <li>Jev and Cloudflare Clef decision-model adapters.</li>
        <li>Python tools with described parameters, intent selection, and predefined outcome replies.</li>
        <li>Conversation memory and SQLite session checkpoints.</li>
        <li>Middleware hooks and human approval before selected actions.</li>
        <li>Turn results with tool calls and decision traces.</li>
        <li>Order-support and flight-desk example agents.</li>
      </ul>
      <div className="note"><strong>Decisions are probabilistic. Your tools enforce the rules.</strong><p>Validate business inputs and permissions inside your Python functions. Low confidence can lead to a follow-up question or a rephrasing request. See the <Link to="/api-reference#operational-limits">operational limits</Link> before integrating external actions.</p></div>
      <Section id="coming-next">Room to grow</Section>
      <p>Future versions are planned to support broader workflows. These capabilities are not included in v0.1.1.</p>
      <div className="roadmap"><span className="tag">Single-agent, multi-intent</span><span className="tag">Multi-agent workflows</span></div>
    </div>
  </>;
}
