import { useLayoutEffect, useRef, useState } from 'react';
import { Link } from 'react-router';

const steps = [
  {
    label: '01 / Understand', title: 'Select an intent',
    text: 'The decision model uses intent descriptions to identify what the user needs.',
    options: [{ title: 'Memory', href: '/memory-and-checkpoints#memory-chooses-what-the-model-sees', text: 'Control the conversation history supplied to decisions.' }],
  },
  {
    label: '02 / Prepare', title: 'Choose tools & params',
    text: "Use the selected intent's context to choose tools and resolve their params. Ask for missing inputs when needed.",
    options: [],
  },
  {
    label: '03 / Act', title: 'Execute Python functions',
    text: 'Your functions run the tools. Use their results to continue with more tool calls when needed.',
    options: [
      { title: 'Middleware', href: '/middleware-and-approval#define-middleware', text: 'Run hooks before and after tool execution.' },
      { title: 'Human approval', href: '/middleware-and-approval#add-human-approval', text: 'Pause selected actions for review before they run.' },
    ],
  },
  {
    label: '04 / Respond', title: 'Select an outcome & reply',
    text: 'The decision model selects an allowed outcome using its description and the current state. Fill its predefined reply template.',
    options: [{ title: 'Checkpointer', href: '/memory-and-checkpoints#sqlite-stores-the-conversation', text: 'Save session state between turns and restore it on the next request.' }],
  },
];

export default function Workflow() {
  const diagram = useRef(null);
  const [paths, setPaths] = useState([]);

  useLayoutEffect(() => {
    const element = diagram.current;
    function measure() {
      const bounds = element.getBoundingClientRect();
      const cards = [...element.querySelectorAll('.flow-card')].map((node) => {
        const rect = node.getBoundingClientRect();
        return { left: rect.left - bounds.left, right: rect.right - bounds.left, top: rect.top - bounds.top, bottom: rect.bottom - bounds.top, x: rect.left - bounds.left + rect.width / 2, y: rect.top - bounds.top + rect.height / 2 };
      });
      setPaths(cards.slice(0, -1).map((card, index) => {
        const next = cards[index + 1];
        if (Math.abs(card.top - next.top) < 2) return `M${card.right},${card.y} H${next.left - 3}`;
        // Wrap the main flow through the row gap, clear of optional branches.
        if (next.left < card.left - 2) {
          const gap = next.top - 22;
          return `M${card.x},${card.bottom} V${gap} H${next.x} V${next.top - 3}`;
        }
        // On mobile, run the main connector down the outer gutter so optional
        // cards remain separate from the required execution sequence.
        return `M${card.left},${card.y} H4 V${next.y} H${next.left - 3}`;
      }));
    }
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    element.querySelectorAll('.flow-card').forEach((node) => observer.observe(node));
    return () => observer.disconnect();
  }, []);

  return <div className="workflow-diagram" ref={diagram}>
    <svg className="flow-connectors" aria-hidden="true">
      <defs><marker id="workflow-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M1 1 7 4 1 7" /></marker></defs>
      {paths.map((path, index) => <path key={index} d={path} markerEnd="url(#workflow-arrow)" />)}
    </svg>
    <ol className="flow" aria-label="Main execution flow with optional capabilities">
      {steps.map((step) => <li className="flow-step" key={step.label}>
        <div className="flow-card"><small>{step.label}</small><h3>{step.title}</h3><p>{step.text}</p></div>
        {step.options.length > 0 && <div className="flow-branches" role="group" aria-label={`Optional capabilities for ${step.title}`}>
          <ul className={`flow-option-list${step.options.length > 1 ? ' multiple' : ''}`}>
            {step.options.map((option) => <li className="flow-option" key={option.title}><Link to={option.href}>{option.title}</Link><p>{option.text}</p></li>)}
          </ul>
        </div>}
      </li>)}
    </ol>
  </div>;
}
