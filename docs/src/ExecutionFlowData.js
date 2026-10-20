// This diagram describes the current local engine, including tool-output candidates.
const messageState = 'Current user message + history permitted by the memory configuration';
const parameterState = `${messageState} + intent context + tool name and description + input name and description + inputs already resolved for this invocation + this turn's ordered tool names, arguments and outputs`;
const turnState = `${messageState} + intent context + this turn's ordered tool names, arguments and outputs`;

const definitions = [
  ['incoming', 'Incoming message', 'Request + supplied history', 'Load session; no model call',
    'Current user message, session ID and saved conversation state.',
    'No model call. Load the session and append the incoming message.'],
  ['continue', '0. Continue a paused input request?', 'Question + message + paused call', 'Noul: does this answer the question?',
    'Prior question, current message, paused intent/tool/input descriptions, possible categories and already collected inputs.',
    'noul(state, "Does the message answer the pending question rather than start a different request?")',
    'Only checked for a pending input. Yes resumes that saved call; no starts intent selection.'],
  ['intent', '1. Select one intent', 'Request + visible history', 'Choice: intent names and descriptions',
    messageState,
    'choice(state, "What does the user want?", {intent name: description})'],
  ['tool', '2a. Select the next tool', 'Request + history + context + calls', 'Choice: permitted tools + none',
    turnState,
    'choice(state, "Which tool should be called next?", {permitted tool name: description, none})',
    'Check max_calls before selection. The default is 6 calls per turn. Budget exhaustion or none exits the tool loop.'],
  ['param-kind', 'Is this parameter optional?', 'Current parameter declaration', 'Python: read Param.optional',
    'For each parameter of the selected tool: its declaration and optional flag.',
    'No model call. Required parameters go directly to value resolution. Optional parameters need the presence check.'],
  ['optional', '2a2. Did the user give a value?', 'Recent history + request + input', 'Noul: did they give or point to a value?',
    'Current message; up to four visible prior messages; intent name, description and context; tool and optional-input descriptions.',
    'noul(state, "Did the user give, choose, or point to a value for this optional input?")',
    'Yes resolves this value. No omits only this argument; other parameters must still be handled.'],
  ['categories', 'Does it declare categories?', 'Param.options', 'Python: check the options dictionary',
    'The current parameter declaration, especially its options dictionary.',
    'No model call. Nonempty options use categorical Choice; otherwise use the text-resolution path.',
    'Nonempty options and a regex pattern cannot both be declared for the same parameter.'],
  ['category-choice', 'Choose a category', 'Request + history + tool/input context', 'Choice: category keys + meanings + none',
    parameterState,
    'choice(state, "Which category does the user give?", {category key: description, none})',
    'A valid selection supplies the declared key. none or low confidence asks the user.'],
  ['regex', 'Find regex matches', 'Message + pattern + earlier tool outputs', 'Python: find matches; add output values',
    'Current message, parameter pattern, earlier tool-call outputs from this turn, previously rejected values and whether an exact value was requested.',
    'No model call. Collect eligible string/number values from earlier tool outputs, then merge with current-message regex matches. Remove duplicates and rejected values. Bind directly only when one value remains and no output candidates were collected. Otherwise use candidate Choice.',
    'Tool-output candidates require Choice even for one remaining value. Exclude error/ignored outputs, booleans, empty values and none; a declared pattern must match the whole output value. Skip output candidates when an exact value was requested. No pattern or no message matches uses the text-candidate path.'],
  ['spans', 'Build text candidates', 'Message + reply + prior value + outputs', 'Python: build candidates; merge outputs',
    'Current message, memory-visible last agent reply, optional-input presence result, supported earlier successful value and collected tool-output candidates.',
    'No model call. For a referenced optional input, try regex matches in the last visible agent reply; otherwise build word-span candidates. Merge with tool-output candidates, deduplicate and exclude rejected values. Every nonempty list goes to candidate Choice, even with one value.',
    'window defaults to 3 words; max_candidates defaults to 40. Tool-output values can supply candidates even when message spans or shown-reply matches supply none.'],
  ['candidate-choice', 'Choose an input value', 'Request + history + input + rejections', 'Choice: candidate text + source + none',
    `${parameterState} + previously rejected text candidates`,
    'choice(state, "Which candidate is this input?", {candidate text: surrounding/source context, none})',
    'Choose among merged message matches, shown-reply matches, word spans and eligible tool-output values. Choices include their surrounding text or source tool call and output path. Tool-output candidates require Choice even when only one merged value remains. none or low confidence asks the user.'],
  ['value', 'Parameter ready', 'Parameter name + selected value', 'Keep the resolved value; continue',
    'Current parameter name and its resolved value.',
    'No model call. Keep the resolved value. Handle the next parameter, or execute the tool once every input has been handled. Saved values are reused without resolving them again.'],
  ['execute', 'Execute the Python tool', 'All resolved inputs; defaults for omissions', 'Middleware, then Tool.run(**args)',
    'Resolved tool arguments after all required inputs and supplied optional inputs are ready.',
    'No decision-model call. Run before_tool middleware, then execute the function and record its arguments and output.',
    'Approval middleware can pause before execution. Ordinary function exceptions become error dictionaries.'],
  ['inspect', '2c. Inspect the tool result', 'Request + history + context + tool calls', 'One request: two Nouls + outcome Choice',
    turnState,
    'nouls_and_choice(state): Noul "Was an input rejected?" + Noul "Is another tool needed?" + Choice {allowed outcome name: description}.',
    'Repair rejected inputs first. Otherwise select another tool if needed; otherwise reuse the outcome selected in this same request.'],
  ['ask', 'Ask for the missing input', 'Missing input + pending tool call', 'Build and send a framework fallback message',
    'Input name and description or categories, pending intent/tool, collected inputs and clarification count.',
    'No model call. Fill a framework-defined question template with parameter names, descriptions or categories supplied by the agent developer. Retain the pending call and return. The next user message goes to step 0.',
    'Missing or low-confidence input can ask immediately. max_param_tries=3 counts tool-rejected values; it does not count every tool error. max_asks defaults to 2 clarification turns for the same pending input.'],
  ['outcome', '3. Resolve the outcome', 'Request + history + context + calls', 'Choice only if the outcome is unresolved',
    turnState,
    'Reuse the accepted outcome from 2c. Otherwise choice(state, "What is the outcome?", {allowed outcome name: description}).',
    'A sole possible outcome needs no additional model call. Visible history depends on memory; it is not always the entire conversation.'],
  ['fallback', 'Return framework fallback', 'Any step: Choice confidence < model.min_conf', 'Send the default fallback message to the user.',
    'An uncaught LowConfidence from intent/tool/outcome selection or post-tool outcome acceptance/repair, plus the current session and execution trace.',
    'No model call. Agent._execute() catches LowConfidence, returns MESSAGES["rephrase"] with outcome rephrase, appends the reply to history and saves the session.',
    'Parameter Choice handles low confidence by asking for the specific missing input instead. This fallback ends the turn without rendering a configured outcome reply.'],
  ['reply', 'Render reply and return', 'Template + inputs + output fields', 'Fill template and save; no model call',
    'Outcome reply template, available tool inputs and dictionary output fields.',
    'No model call. Fill the template, append the reply to history, save session state and return reply plus decision and tool traces.'],
];

const positions = {
  incoming: [350,20,360,110], continue: [350,190,360,160], intent: [350,420,360,140],
  fallback: [830,330,340,180],
  tool: [350,680,360,140],
  'param-kind': [350,1380,360,140], optional: [830,1380,340,170],
  categories: [350,1630,360,140],
  'category-choice': [830,1870,340,190], regex: [350,1870,360,190],
  spans: [350,2140,360,190], 'candidate-choice': [350,2420,360,180],
  value: [350,2710,360,150], execute: [350,3090,360,150], inspect: [350,3340,360,190],
  ask: [830,2780,340,190],
  outcome: [350,3720,360,160], reply: [350,3970,360,130],
};

export const steps = definitions.map(([id,title,state,call,detailState,detailCall,note]) => ({id,title,state:detailState,call:detailCall,note}));
const decisionIds = new Set(['continue','intent','tool','optional','category-choice','candidate-choice','inspect','outcome']);
const nodeNotes = {
  fallback:"Sorry, I didn't quite get that.\nCould you rephrase?\nParameter choices ask for the missing input instead.",
  ask:'The framework builds the fallback message dynamically\nfrom tool parameter definitions and sends it to the user.',
  regex:'Tool outputs need Choice, even for one value.',
  spans:'window = 3; max_candidates = 40',
  inspect:'Repair first; then another tool; then finish.',
};
export const graphNodes = definitions.map(([id,title,state,call,,,note]) => {
  const [x,y,width,height] = positions[id];
  return {id,title,state,call,x,y,width,height,kind:id === 'fallback' ? 'fallback' : decisionIds.has(id) ? 'decision' : 'logic',note:nodeNotes[id]};
});
export const parameterIds = new Set(['categories','category-choice','regex','spans','candidate-choice','value','ask']);
export const parameterBounds = {x:320,y:1600,width:890,height:1420};
// Value-resolution connections meet the 2b boundary; optional checks stay outside.
const nodes = {...Object.fromEntries(graphNodes.map(node => [node.id,node])), parameters: parameterBounds};
function port(node, side, fraction = 0.5) {
  // Connect to the visible oval, rather than its invisible rectangular bounds.
  if (node.kind === 'logic') {
    const radiusX = node.width / 2, radiusY = node.height / 2;
    const offset = Math.sqrt(Math.max(0, 1 - (2 * fraction - 1) ** 2));
    if (side === 'left' || side === 'right') {
      return [node.x + radiusX + (side === 'right' ? 1 : -1) * radiusX * offset, node.y + node.height * fraction];
    }
    return [node.x + node.width * fraction, node.y + radiusY + (side === 'bottom' ? 1 : -1) * radiusY * offset];
  }
  if (side === 'left' || side === 'right') return [node.x + (side === 'right' ? node.width : 0), node.y + node.height * fraction];
  return [node.x + node.width * fraction, node.y + (side === 'bottom' ? node.height : 0)];
}
function edge(id,from,to,{source='bottom',target='top',sourceFraction=0.5,targetFraction=0.5,via,label,labelAt,labelSide,branch=false}={}) {
  const a=port(nodes[from],source,sourceFraction), b=port(nodes[to],target,targetFraction);
  let bends=via ? via(a,b) : [];
  if (!via && a[0]!==b[0] && a[1]!==b[1]) bends = source==='left'||source==='right' ? [[(a[0]+b[0])/2,a[1]],[(a[0]+b[0])/2,b[1]]] : [[a[0],(a[1]+b[1])/2],[b[0],(a[1]+b[1])/2]];
  return {id,from,to,points:[a,...bends,b],label,labelAt,labelSide,branch};
}
const lane = x => (a,b) => [[x,a[1]],[x,b[1]]];
const parameterLevel = y => (y - parameterBounds.y) / parameterBounds.height;

export const graphEdges = [
  edge('start','incoming','continue'),
  edge('new','continue','intent',{label:'No / new request',labelAt:[640,386]}),
  // Return paths enter from above: a horizontal approach from the right would
  // pass through the unrelated optional-value card in the second column.
  edge('resume','continue','param-kind',{source:'right',target:'top',targetFraction:.8,via:(a,b)=>[[1240,a[1]],[1240,1040],[b[0],1040]],label:'Yes: resume saved call',labelAt:[965,254],branch:true}),
  edge('has-tools','intent','tool',{label:'Has tools',labelAt:[600,646]}),
  edge('no-tools','intent','outcome',{source:'left',sourceFraction:.35,target:'left',targetFraction:.7,via:lane(50),label:'No tools',labelAt:[200,453],branch:true}),
  edge('selected','tool','param-kind',{label:'Tool selected: handle each input',labelAt:[715,841]}),
  edge('parameter-entry','parameters','categories',{source:'top',sourceFraction:210/890}),
  edge('none','tool','outcome',{source:'left',sourceFraction:.35,target:'left',targetFraction:.3,via:lane(100),label:'none / max_calls',labelAt:[225,713],branch:true}),
  edge('no-parameters','tool','execute',{source:'left',sourceFraction:.7,target:'left',targetFraction:.2,via:lane(260),label:'No parameters',labelAt:[240,1330],branch:true}),
  edge('all-ready','value','parameters',{target:'bottom',targetFraction:210/890,label:'All parameters ready',labelAt:[650,2995]}),
  edge('parameter-exit','parameters','execute',{sourceFraction:210/890,label:'All inputs ready',labelAt:[640,3055]}),
  edge('optional','param-kind','optional',{source:'right',target:'left',label:'Optional',labelAt:[780,1434]}),
  edge('required','param-kind','parameters',{targetFraction:210/890,label:'Required: resolve',labelAt:[610,1575]}),
  edge('optional-yes','optional','parameters',{source:'left',sourceFraction:.8,targetFraction:350/890,via:(a,b)=>[[790,a[1]],[790,1560],[b[0],1560]],label:'Yes: resolve',labelAt:[780,1592]}),
  edge('optional-next','optional','param-kind',{source:'bottom',sourceFraction:.8,target:'left',targetFraction:.85,via:(a,b)=>[[a[0],1580],[310,1580],[310,b[1]]],label:'No: default; next parameter',labelAt:[1020,1578],branch:true}),
  edge('optional-done','optional','execute',{source:'right',sourceFraction:.75,target:'right',targetFraction:.2,via:lane(1220),label:'No: default; all inputs handled',labelAt:[1050,3050],branch:true}),
  edge('categorical','categories','category-choice',{source:'right',target:'left',via:(a,b)=>[[810,a[1]],[810,b[1]]],label:'Yes: categories',labelAt:[780,1730]}),
  edge('text-input','categories','regex',{label:'No categories',labelAt:[635,1825]}),
  edge('category-value','category-choice','value',{source:'right',target:'right',targetFraction:.18,via:lane(1190),label:'Category selected',labelAt:[1050,2084]}),
  edge('category-missing','category-choice','ask',{source:'right',sourceFraction:.8,target:'right',targetFraction:.3,via:lane(1205),label:'none / low confidence',labelAt:[1100,2115],branch:true}),
  edge('one-match','regex','value',{source:'left',sourceFraction:.4,target:'left',targetFraction:.5,via:lane(334),label:'One value; no outputs',labelAt:[405,2087]}),
  edge('many-matches','regex','candidate-choice',{source:'right',target:'right',targetFraction:.2,via:lane(735),label:'Several matches / outputs',labelAt:[825,2104],labelSide:'above'}),
  edge('fallback','regex','spans',{label:'No pattern / no matches',labelAt:[675,2102]}),
  edge('rejected-matches','regex','ask',{source:'right',sourceFraction:.75,target:'left',targetFraction:.65,via:lane(785),label:'No eligible merged values',labelAt:[850,2190],branch:true}),
  edge('candidates','spans','candidate-choice',{label:'Merged candidates available',labelAt:[670,2370]}),
  edge('no-candidates','spans','ask',{source:'right',target:'left',targetFraction:.2,via:lane(770),label:'No eligible merged values',labelAt:[830,2220],branch:true}),
  edge('chosen','candidate-choice','value',{label:'Value selected',labelAt:[635,2655]}),
  edge('no-value','candidate-choice','ask',{source:'right',target:'left',targetFraction:.4,via:lane(745),label:'none / low confidence',labelAt:[845,2520],branch:true}),
  edge('value-next','value','param-kind',{source:'left',sourceFraction:.8,target:'left',targetFraction:.85,via:lane(326),label:'More parameters: repeat',labelAt:[440,2890],branch:true}),
  edge('result','execute','inspect',{label:'Tool result',labelAt:[625,3290]}),
  edge('retry','inspect','param-kind',{source:'right',target:'top',targetFraction:.95,via:(a,b)=>[[1250,a[1]],[1250,1220],[b[0],1220]],label:'1. Rejected input: retry same tool',labelAt:[1000,3419],branch:true}),
  edge('ask-exact','inspect','parameters',{source:'right',sourceFraction:.8,target:'right',targetFraction:parameterLevel(2875),via:lane(1270),label:'Ask for the exact input',labelAt:[1000,3324],branch:true}),
  edge('parameter-ask','parameters','ask',{source:'right',sourceFraction:parameterLevel(2875),target:'right',branch:true}),
  edge('another','inspect','tool',{source:'left',sourceFraction:.65,target:'left',targetFraction:.8,via:lane(200),label:'2. Otherwise: another tool',labelAt:[190,3485],branch:true}),
  edge('finish','inspect','outcome',{label:'3. Otherwise: keep selected outcome',labelAt:[750,3665]}),
  edge('question-exit','ask','parameters',{target:'right',targetFraction:parameterLevel(2990),via:(a,b)=>[[a[0],2990]],label:'Return question',labelAt:[1095,3005],branch:true}),
  edge('next-message','parameters','continue',{source:'right',sourceFraction:parameterLevel(2990),target:'top',targetFraction:.85,via:(a,b)=>[[1280,a[1]],[1280,155],[b[0],155]],label:'Next user message',labelAt:[990,139],branch:true}),
  edge('render','outcome','reply',{label:'Outcome resolved',labelAt:[650,3920]}),
];

export const loopIds = new Set(graphNodes.filter(node => !['incoming','continue','intent','fallback','outcome','reply'].includes(node.id)).map(node=>node.id));
export const loopBounds = {x:300,y:580,width:930,height:3040};
export const loopSummary = {id:'loop',kind:'group',x:350,y:640,width:360,height:180,title:'2. Execute the tool loop',state:'Selected intent + session + tool-call history',call:'Resolve every parameter, execute, inspect and repeat.',note:'Expand to see each decision and retry.'};
export const overviewNodes = [nodes.incoming,nodes.continue,nodes.intent,nodes.fallback,loopSummary,{...nodes.outcome,y:900},{...nodes.reply,y:1140}];
export const overviewEdges = [
  {id:'start',from:'incoming',to:'continue',points:[[530,130],[530,190]]},
  {id:'new',from:'continue',to:'intent',points:[[530,350],[530,420]],label:'No / new request',labelAt:[640,386]},
  {id:'resume',from:'continue',to:'loop',points:[[710,270],[1240,270],[1240,685],[710,685]],label:'Yes: resume inputs',labelAt:[820,254],branch:true},
  {id:'has-tools',from:'intent',to:'loop',points:[[530,560],[530,640]],label:'Has tools',labelAt:[610,600]},
  {id:'no-tools',from:'intent',to:'outcome',points:[port(nodes.intent,'left',50/140),[160,470],[160,980],[350,980]],label:'No tools',labelAt:[245,454],branch:true},
  {id:'finished',from:'loop',to:'outcome',points:[[530,820],[530,900]],label:'Loop finished / call limit',labelAt:[685,860]},
  {id:'paused',from:'loop',to:'continue',points:[[710,755],[1280,755],[1280,155],[650,155],[650,190]],label:'Question: next message',labelAt:[805,139],branch:true},
  {id:'render',from:'outcome',to:'reply',points:[[530,1060],[530,1140]],label:'Outcome resolved',labelAt:[650,1100]},
];
