import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import { attachLabelsToEdges } from './ExecutionLabels';
import { graphNodes as sourceNodes, graphEdges as sourceEdges, loopIds, loopBounds as sourceLoopBounds, parameterIds, parameterBounds as sourceParameterBounds, overviewNodes as sourceOverviewNodes, overviewEdges as sourceOverviewEdges } from './ExecutionFlowData';

// Widen cards and reserve a larger routing gutter between the two columns.
// Map every card, group, connection and label together so endpoints stay attached.
const horizontalStops = [[0,0],[300,150],[320,170],[350,220],[710,640],[830,900],[1170,1320],[1300,1500]];
function spreadX(x) {
  const index = horizontalStops.findIndex(([position]) => position >= x);
  if (index === 0) return horizontalStops[0][1];
  const end = index < 0 ? horizontalStops.length - 1 : index;
  const [left,expandedLeft] = horizontalStops[end - 1];
  const [right,expandedRight] = horizontalStops[end];
  return expandedLeft + (x - left) * (expandedRight - expandedLeft) / (right - left);
}
function spreadY(y, compact = false) {
  // Reserve a routing band above 2b, moving its contents and later steps together.
  const parameterGap = compact ? Math.max(0, Math.min(1, (y - 1550) / 50)) * 120 : 0;
  // Close the space formerly occupied by the iterator and cached-input cards.
  if (compact && y > 840) y = y >= 1380 ? y - 480 : 840 + (y - 840) / 9;
  return (y + parameterGap) * 1.08;
}
const spreadPoint = ([x,y], compact = false) => [spreadX(x),spreadY(y,compact)];
function spreadRect(rect, compact = false) {
  return {...rect,x:spreadX(rect.x),y:spreadY(rect.y,compact),width:spreadX(rect.x + rect.width) - spreadX(rect.x),height:spreadY(rect.y + rect.height,compact) - spreadY(rect.y,compact)};
}
const spreadEdge = (edge, compact = false) => ({...edge,points:edge.points.map(point => spreadPoint(point,compact)),labelAt:edge.labelAt ? spreadPoint(edge.labelAt,compact) : undefined});
const graphNodes = sourceNodes.map(node => spreadRect(node,true));
const mappedGraphEdges = sourceEdges.map(edge => spreadEdge(edge,true));
const overviewNodes = sourceOverviewNodes.map(node => spreadRect(node));
const mappedOverviewEdges = sourceOverviewEdges.map(edge => spreadEdge(edge));
const loopBounds = spreadRect(sourceLoopBounds,true);
const parameterBounds = spreadRect(sourceParameterBounds,true);
// Leave the main vertical connector clear of the tool-loop heading.
const loopHeading = spreadRect({x:740,y:596,width:466,height:42});
const parameterHeading = spreadRect({x:740,y:1616,width:440,height:60},true);
const parameterSummary = {
  id:'parameters',kind:'group',x:graphNodes[0].x,y:parameterBounds.y,width:graphNodes[0].width,height:180,
  title:'2b. Resolve tool parameters',state:'Current parameter + collected inputs',
  call:'Resolve categories, text and tool-output candidates.',
  note:'Expand to see each parameter-resolution step.',
};

function cardPort(node,side,fraction = .5) {
  const horizontal = side === 'left' || side === 'right';
  const direction = side === 'right' || side === 'bottom' ? 1 : -1;
  const curve = node.kind === 'logic' ? Math.sqrt(Math.max(0,1 - (2 * fraction - 1) ** 2)) : 1;
  return horizontal
    ? [node.x + node.width / 2 * (1 + direction * curve),node.y + node.height * fraction]
    : [node.x + node.width * fraction,node.y + node.height / 2 * (1 + direction * curve)];
}

function collapsedParameterEdges(edges,nodes) {
  const byId = Object.fromEntries(nodes.map(item => [item.id,item]));
  const summary = byId.parameters;
  const result = edges.map(edge => {
    if (edge.id === 'required') {
      return {...edge,points:[cardPort(byId['param-kind'],'bottom'),cardPort(summary,'top')]};
    }
    if (edge.id === 'optional-yes') {
      const a = cardPort(byId.optional,'left',.8), b = cardPort(summary,'top',.85);
      const gutter = (byId.optional.x + summary.x + summary.width) / 2;
      return {...edge,points:[a,[gutter,a[1]],[gutter,b[1] - 34],[b[0],b[1] - 34],b]};
    }
    if (edge.id === 'parameter-exit') {
      return {...edge,points:[cardPort(summary,'bottom'),cardPort(byId.execute,'top')]};
    }
    if (edge.id === 'ask-exact') {
      const a = cardPort(byId.inspect,'right',.8), b = cardPort(summary,'right',.35);
      const gutter = edge.points[1][0];
      return {...edge,points:[a,[gutter,a[1]],[gutter,b[1]],b]};
    }
    if (edge.id === 'next-message') {
      const a = cardPort(summary,'right',.75), b = cardPort(byId.continue,'top',.85);
      const gutter = edge.points[1][0], top = edge.points[2][1];
      return {...edge,label:'Question: next message',points:[a,[gutter,a[1]],[gutter,top],[b[0],top],b]};
    }
    return edge;
  });
  const a = cardPort(summary,'left',.55), b = cardPort(byId['param-kind'],'left',.85);
  const gutter = Math.min(summary.x,byId['param-kind'].x) - 40;
  result.push({id:'parameter-repeat',from:'parameters',to:'param-kind',branch:true,label:'More parameters: repeat',labelAt:[a[0] - 100,a[1] - 20],points:[a,[gutter,a[1]],[gutter,b[1]],b]});
  return result;
}

function resizeEdgeAnchors(edges,originalNodes,resizedNodes) {
  const originalById = Object.fromEntries(originalNodes.map(node => [node.id,node]));
  const resizedById = Object.fromEntries(resizedNodes.map(node => [node.id,node]));
  function anchor(id,point,neighbour) {
    const original = originalById[id], resized = resizedById[id];
    if (!original || !resized) return point;
    const horizontal = Math.abs(neighbour[0] - point[0]) > Math.abs(neighbour[1] - point[1]);
    const direction = Math.sign(horizontal ? neighbour[0] - point[0] : neighbour[1] - point[1]);
    const fraction = Math.max(0,Math.min(1,horizontal ? (point[1] - original.y) / original.height : (point[0] - original.x) / original.width));
    const curve = resized.kind === 'logic' ? Math.sqrt(Math.max(0,1 - (2 * fraction - 1) ** 2)) : 1;
    return horizontal
      ? [resized.x + resized.width / 2 * (1 + direction * curve),resized.y + resized.height * fraction]
      : [resized.x + resized.width * fraction,resized.y + resized.height / 2 * (1 + direction * curve)];
  }
  return edges.map(edge => {
    const old = edge.points;
    const points = old.map(point => [...point]);
    const last = points.length - 1;
    points[0] = anchor(edge.from,old[0],old[1]);
    points[last] = anchor(edge.to,old[last],old[last - 1]);
    if (last > 1) {
      if (old[0][1] === old[1][1]) points[1][1] = points[0][1];
      else points[1][0] = points[0][0];
      if (old[last][1] === old[last - 1][1]) points[last - 1][1] = points[last][1];
      else points[last - 1][0] = points[last][0];
    }
    return {...edge,points};
  });
}

function connectParameterRoutes(edges) {
  // The green frame is decorative. Join its split connections so selection
  // highlights one complete route between the actual source and target cards.
  const byId = Object.fromEntries(edges.map(edge => [edge.id,edge]));
  const routes = [
    ['required','parameter-entry'],
    ['optional-yes','parameter-entry'],
    ['all-ready','parameter-exit'],
    ['ask-exact','parameter-ask'],
    ['question-exit','next-message'],
  ];
  const continuations = new Set(routes.map(([,continuation]) => continuation));
  const targets = Object.fromEntries(routes);
  return edges.flatMap(edge => {
    if (continuations.has(edge.id)) return [];
    const continuation = byId[targets[edge.id]];
    if (!continuation) return [edge];
    const points = [...edge.points];
    for (const point of continuation.points) {
      const previous = points[points.length - 1];
      if (previous[0] === point[0] && previous[1] === point[1]) continue;
      if (previous[0] !== point[0] && previous[1] !== point[1]) points.push([previous[0],point[1]]);
      points.push(point);
    }
    const label = edge.id === 'question-exit' ? 'Return question; next user message'
      : edge.id === 'all-ready' ? 'All inputs ready' : edge.label || continuation.label;
    return [{...edge,to:continuation.to,points,label,branch:edge.branch || continuation.branch}];
  });
}

function edgePath(points) {
  return points.map(([x, y], i) => `${i ? 'L' : 'M'}${x},${y}`).join(' ');
}

function roundedFallbackPath({x,y,width,height}) {
  const inset = 28, radius = 16;
  const corners = [[x + inset,y],[x + width - inset,y],[x + width,y + height],[x,y + height]];
  const towards = (point,other) => {
    const distance = Math.hypot(other[0] - point[0],other[1] - point[1]);
    const fraction = Math.min(radius / distance,.3);
    return point.map((value,index) => value + (other[index] - value) * fraction);
  };
  return corners.map((corner,index) => {
    const entry = towards(corner,corners[(index + 3) % 4]);
    const exit = towards(corner,corners[(index + 1) % 4]);
    return `${index ? 'L' : 'M'}${entry.join(',')} Q${corner.join(',')} ${exit.join(',')}`;
  }).join(' ') + ' Z';
}

function insideBounds([x,y],bounds) {
  return x >= bounds.x && x <= bounds.x + bounds.width && y >= bounds.y && y <= bounds.y + bounds.height;
}

export default function ExecutionDiagram() {
  const [selected, setSelected] = useState('intent');
  const [loopExpanded, setLoopExpanded] = useState(false);
  const [parametersExpanded, setParametersExpanded] = useState(false);
  const [cardSizes, setCardSizes] = useState({});
  const cardElements = useRef(new Map());
  const toggleButton = useRef(null);
  const parameterToggleButton = useRef(null);
  const restoreFocus = useRef(false);
  const restoreParameterFocus = useRef(false);
  useLayoutEffect(() => {
    // Measure natural HTML content, in SVG layout units, without its display scale.
    const cards = [...cardElements.current.entries()];
    function measureCards() {
      setCardSizes(previous => {
        let next = previous;
        for (const [id,element] of cards) {
          const width = Math.ceil(element.offsetWidth);
          let height = Math.ceil(element.offsetHeight);
          if (id === 'fallback') {
            // Fit the separate SVG outline to the text rows and even padding,
            // rather than retaining surplus height from the button's box.
            const style = getComputedStyle(element);
            const rows = [...element.children];
            const contentHeight = rows.reduce((sum,row) => sum + (parseFloat(getComputedStyle(row).height) || row.offsetHeight),0);
            height = Math.ceil(contentHeight + Math.max(0,rows.length - 1) * (parseFloat(style.rowGap) || 0)
              + parseFloat(style.paddingTop) + parseFloat(style.paddingBottom)
              + (parseFloat(style.borderTopWidth) || 0) + (parseFloat(style.borderBottomWidth) || 0));
          }
          if (width > 0 && height > 0 && (previous[id]?.width !== width || previous[id]?.height !== height)) {
            if (next === previous) next = {...previous};
            next[id] = {width,height};
          }
        }
        return next;
      });
    }
    measureCards();
    const observer = new ResizeObserver(measureCards);
    cards.forEach(([,element]) => observer.observe(element));
    return () => observer.disconnect();
  }, [loopExpanded,parametersExpanded]);
  const {nodes:visibleNodes,edges:visibleEdges,loop:visibleLoopBounds,height:diagramHeight} = useMemo(() => {
    let originalNodes = loopExpanded ? graphNodes : overviewNodes;
    let originalEdges = loopExpanded ? mappedGraphEdges : mappedOverviewEdges;
    let removedHeight = 0;
    if (loopExpanded && !parametersExpanded) {
      const summaryHeight = cardSizes.parameters?.height ?? parameterSummary.height;
      removedHeight = parameterBounds.height - summaryHeight;
      const compressY = y => y <= parameterBounds.y ? y : y >= parameterBounds.y + parameterBounds.height
        ? y - removedHeight : parameterBounds.y + (y - parameterBounds.y) * summaryHeight / parameterBounds.height;
      originalNodes = graphNodes.filter(item => !parameterIds.has(item.id)).map(item => ({...item,y:compressY(item.y)}));
      originalNodes.push({...parameterSummary,height:summaryHeight});
      originalEdges = mappedGraphEdges.filter(edge => !parameterIds.has(edge.from) && !parameterIds.has(edge.to)).map(edge => ({
        ...edge,points:edge.points.map(([x,y]) => [x,compressY(y)]),
        labelAt:edge.labelAt ? [edge.labelAt[0],compressY(edge.labelAt[1])] : undefined,
      }));
    }
    const nodes = originalNodes.map(item => {
      const width = item.kind === 'logic' || item.kind === 'fallback' ? cardSizes[item.id]?.width ?? (item.kind === 'logic' ? 320 : item.width) : item.width;
      return {...item,x:item.x + (item.width - width) / 2,width,height:cardSizes[item.id]?.height ?? item.height};
    });
    let edges = resizeEdgeAnchors(originalEdges,originalNodes.filter(item => item.id !== 'parameters'),nodes);
    if (loopExpanded && !parametersExpanded) edges = collapsedParameterEdges(edges,nodes);
    if (loopExpanded && parametersExpanded) edges = connectParameterRoutes(edges);
    const fallback = nodes.find(item => item.id === 'fallback');
    if (fallback) {
      const directions = [
        ['top',.35],['top',.5],['top',.65],
        ['bottom',.35],['bottom',.5],['bottom',.65],
        ['left',.5],['right',.5],
      ];
      for (const [index,[side,fraction]] of directions.entries()) {
        const end = cardPort(fallback,side,fraction);
        // Meet the sloped sides of the rounded trapezoid, not its outer box.
        if (side === 'left' || side === 'right') end[0] += (side === 'left' ? 1 : -1) * 28 * (1 - fraction);
        const offset = side === 'top' ? [0,-52] : side === 'bottom' ? [0,52] : side === 'left' ? [-52,0] : [52,0];
        edges.push({id:`confidence-fallback-${index}`,from:`confidence-source-${index}`,to:'fallback',branch:true,floating:true,points:[[end[0] + offset[0],end[1] + offset[1]],end]});
      }
    }
    return {
      nodes,edges:attachLabelsToEdges(edges,nodes,loopExpanded ? parametersExpanded ? [loopHeading,parameterHeading] : [loopHeading] : []),
      loop:{...loopBounds,height:loopBounds.height - removedHeight},
      height:loopExpanded ? 3695 - removedHeight * .9 : 1264,
    };
  }, [cardSizes,loopExpanded,parametersExpanded]);
  useLayoutEffect(() => {
    if (restoreFocus.current) {
      toggleButton.current?.focus({ preventScroll: true });
      restoreFocus.current = false;
    }
    if (restoreParameterFocus.current) {
      parameterToggleButton.current?.focus({ preventScroll: true });
      restoreParameterFocus.current = false;
    }
  }, [loopExpanded,parametersExpanded]);
  const related = edge => edge.from === selected || edge.to === selected;
  // Shared route segments must keep the selected colour above inactive lines.
  const orderedEdges = [...visibleEdges].sort((a,b) => Number(related(a)) - Number(related(b)));
  const choose = id => setSelected(id);
  function toggleLoop() {
    if (loopExpanded && (loopIds.has(selected) || selected === 'parameters')) setSelected('loop');
    if (loopExpanded) setParametersExpanded(false);
    restoreFocus.current = true;
    setLoopExpanded(value => !value);
  }
  function toggleParameters() {
    if (parametersExpanded && parameterIds.has(selected)) setSelected('parameters');
    restoreParameterFocus.current = true;
    setParametersExpanded(value => !value);
  }
  const expandArrow = <button ref={toggleButton} type="button" className="execution-loop-toggle" onClick={toggleLoop}
    aria-expanded={loopExpanded} aria-controls="execution-flow-map"
    aria-label={loopExpanded ? 'Collapse tool-call loop' : 'Expand tool-call loop'}>
    <svg viewBox="0 0 20 20" aria-hidden="true"><path d={loopExpanded ? 'M5 12 10 7 15 12' : 'M5 8 10 13 15 8'} /></svg>
  </button>;
  const parameterExpandArrow = <button ref={parameterToggleButton} type="button" className="execution-loop-toggle" onClick={toggleParameters}
    aria-expanded={parametersExpanded} aria-controls="execution-flow-map"
    aria-label={parametersExpanded ? 'Collapse parameter resolution' : 'Expand parameter resolution'}>
    <svg viewBox="0 0 20 20" aria-hidden="true"><path d={parametersExpanded ? 'M5 12 10 7 15 12' : 'M5 8 10 13 15 8'} /></svg>
  </button>;

  return <section className="execution-diagram" aria-labelledby="framework-workflow">
    <h2 id="framework-workflow">Framework workflow</h2>
    <p className="execution-help">Use the arrows to expand the tool loop and its parameter-resolution steps. Select a step to highlight its connected arrows.</p>
    <div className="execution-shape-key" aria-label="Card shapes"><span className="logic">Python logic: oval</span><span className="decision">Decision-model call: rectangular</span><span className="fallback">Framework fallback: rounded trapezoid</span></div>
    <p className="execution-help execution-confidence-note">When a decision-model Choice confidence is below <code>model.min_conf</code>, the framework sends its default rephrase message shown below. Parameter choices ask for the missing input instead.</p>
    <div className="execution-arrow-key" aria-label="Arrow styles">
      <span><svg viewBox="0 0 64 16" aria-hidden="true"><path d="M2 8 H60" /><path className="execution-key-arrowhead" d="M52 3 L61 8 L52 13 Z" /></svg>Solid arrows follow execution.</span>
      <span><svg viewBox="0 0 64 16" aria-hidden="true"><path className="execution-key-dashed" d="M2 8 H60" /><path className="execution-key-arrowhead" d="M52 3 L61 8 L52 13 Z" /></svg>Dashed arrows show bypasses and pauses.</span>
    </div>
    <figure className="execution-figure" aria-label="Branching single-intent execution graph">
      <svg id="execution-flow-map" className="execution-map" viewBox={`0 0 1500 ${diagramHeight}`} role="group" aria-label="Execution decisions and connected branches">
        <defs>{['main', 'branch', 'active'].map(kind => <marker key={kind} id={`flow-${kind}-head`} viewBox="0 0 12 12" refX="12" refY="6" markerWidth="18" markerHeight="18" orient="auto" markerUnits="userSpaceOnUse"><path className={kind} d="M1 1 L12 6 L1 11 Z" /></marker>)}</defs>
        <g transform="translate(75 0) scale(0.9)">
        {loopExpanded && <g className="execution-loop-boundary"><rect {...visibleLoopBounds} rx="18" /><foreignObject {...loopHeading}><div className="execution-loop-heading"><strong>2. Execute the tool loop</strong>{expandArrow}</div></foreignObject></g>}
        {loopExpanded && parametersExpanded && <g className="execution-parameter-boundary" data-graph-group="parameters" role="group" aria-label="2b. Resolve tool parameters">
          <rect {...parameterBounds} rx="14" />
          <foreignObject {...parameterHeading}><div className="execution-parameter-heading"><div className="execution-parameter-title"><strong>2b. Resolve tool parameters</strong>{parameterExpandArrow}</div><span>Resolve required values and optional values the user gave.</span></div></foreignObject>
        </g>}
        {visibleNodes.filter(item => item.kind === 'fallback').map(item => <path key={item.id} className={`execution-fallback-outline${item.id === selected ? ' active' : ''}`} d={roundedFallbackPath(item)} />)}
        <g className="execution-edges">{orderedEdges.map(edge => {
          const kind = related(edge) ? 'active' : edge.branch ? 'branch' : 'main';
          return <g key={edge.id} data-edge={edge.id} data-from={edge.from} data-to={edge.to}>
            <path className={`execution-edge ${edge.branch ? 'branch ' : ''}${kind}`} d={edgePath(edge.points)} markerEnd={`url(#flow-${kind}-head)`} />
            {!edge.floating && <circle className={`execution-origin ${kind}`} cx={edge.points[0][0]} cy={edge.points[0][1]} r="3" />}
          </g>;
        })}</g>
        <g>{visibleNodes.map(item => <foreignObject key={item.id} x={item.x} y={item.y} width={item.width} height={item.height} data-graph-node={item.id} className={loopExpanded && (loopIds.has(item.id) || item.id === 'parameters') ? `execution-tool-node${parameterIds.has(item.id) || item.id === 'parameters' ? ' execution-parameter-node' : ''}` : undefined}>
          <div className={`execution-node-shell${item.id === 'loop' || item.id === 'parameters' ? ' execution-loop-summary' : ''}`}>
          <button ref={element => { if (element) cardElements.current.set(item.id,element); else cardElements.current.delete(item.id); }} style={item.kind === 'fallback' ? {height:cardSizes[item.id]?.height ?? 'auto'} : undefined} type="button" className={`execution-graph-node execution-node-${item.kind}${item.id === selected ? ' selected' : ''}`} onClick={() => choose(item.id)} aria-pressed={item.id === selected}>
            {item.id === 'param-kind' && <small>For each parameter of the selected tool</small>}
            <strong>{item.title}</strong>
            <span><b>State</b> {item.state}</span>
            <span><b>{item.kind === 'decision' || item.kind === 'group' ? 'Call' : 'Action'}</b> {item.call}</span>
            {item.note && <small>{item.note}</small>}
          </button>
          {item.id === 'loop' && expandArrow}
          {item.id === 'parameters' && parameterExpandArrow}
          </div>
        </foreignObject>)}</g>
        <g className="execution-edge-labels">{orderedEdges.filter(edge => edge.label).map(edge => <g key={edge.id} data-label-for={edge.id} className={`execution-edge-caption${related(edge) ? ' active' : ''} ${loopExpanded && parametersExpanded && insideBounds(edge.labelAt,parameterBounds) ? 'execution-parameter-label' : loopExpanded && insideBounds(edge.labelAt,visibleLoopBounds) ? 'execution-loop-label' : ''}`}>
          {edge.labelPointer && <><path className="execution-label-pointer" d={edgePath(edge.labelPointer)} /><circle className="execution-label-anchor" cx={edge.labelAnchor[0]} cy={edge.labelAnchor[1]} r="2.5" /></>}
          <g transform={`translate(${edge.labelAt.join(' ')})`}>
            <rect x={-edge.labelWidth / 2} y={-edge.labelHeight / 2} width={edge.labelWidth} height={edge.labelHeight} rx="7" />
            <text className={related(edge) ? 'active' : undefined} textAnchor="middle" dominantBaseline="middle">{edge.label}</text>
          </g>
        </g>)}</g>
        </g>
      </svg>
    </figure>
  </section>;
}

