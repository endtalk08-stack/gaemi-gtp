// Simulates the actual #미국장 follow-up handler including 5-second wait,
// a valid saved Neon brief, optional table rendering, and failure recovery.
// No network access, no market/AI calls, no production writes.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');

class Element {
  constructor(tag, registry) {
    this.tagName = tag;
    this.children = [];
    this.isConnected = true;
    this._text = '';
    this.registry = registry;
    this.className = '';
    this.classList = {
      add() {}, remove() {}, contains() { return false; }
    };
  }
  set textContent(v) { this._text = String(v); this.children = []; }
  get textContent() { return this._text + this.children.map(x => x.textContent).join(''); }
  appendChild(child) { this.children.push(child); return child; }
  append(...children) { children.forEach(child => this.appendChild(child)); }
  replaceChildren(...children) { this.children = children; this._text = ''; }
  insertAdjacentElement(_position, child) {
    this.registry.inserted.push(child);
    return child;
  }
  scrollIntoView() {}
  setAttribute() {}
  querySelector() { return null; }
  remove() { this.isConnected = false; }
}

const flowSource = fs.readFileSync('frontend/shell/center-chat/analysis-flow.js','utf8');
const start = flowSource.indexOf("        const isGaemiMode = () =>");
const end = flowSource.indexOf("        const appendRemainingChoices =",start);
assert.ok(start > 0 && end > start,'real gaemi followup handler must exist');
const segment = flowSource.slice(start,end);
const presenter = fs.readFileSync('frontend/shell/center-chat/us-close-reply.js','utf8');

const original = {
  session_date_et:'2026-10-19',
  market_indices:[
    {name:'다우존스',close:51966.03,change_pct:-0.07},
    {name:'나스닥 종합',close:26430.89,change_pct:1.11},
    {name:'S&P 500',close:7690.73,change_pct:0.41}
  ],
  issues:[{headline:'AI·반도체 반등',summary:'10월 19일 미국증시는 혼조로 마감했어.',
    tags:['#AI반등','#나스닥상승','#금리불안']}]
};
const savedText='AI·반도체 반등\n\n다우존스 51,966.03 (-0.07%)\n\n나스닥 종합 26,430.89 (+1.11%)\n\nS&P 500 7,690.73 (+0.41%)\n\n10월 19일 미국증시는 혼조로 마감했어.\n\n#AI반등 #나스닥상승 #금리불안';

async function scenario(failure) {
  const registry = {inserted:[], warnings:[], actions:[], fetches:[], timers:[]};
  const document = {createElement: tag => new Element(tag,registry)};
  const window = {GaemiGTPFirstReplyActions:{appendFirstReplyActions(...args) {
    registry.actions.push(args);
  }}};
  const ctx = {
    backendUrl:'https://fake-render.test',
    getSession:()=>({mode:'gaemi'}),
    getActiveAnalysisRequestId:()=>8
  };
  const fetch = async (url,options) => {
    registry.fetches.push({url,options});
    return {ok:true,json:async()=>({ok:true,available:true,
      content:savedText,presentation:original})};
  };
  const makeUserPrompt=()=>new Element('div',registry);
  const choices=new Element('section',registry);
  const mainContainer=new Element('div',registry);
  const typeText=async (element,value) => {
    if (failure==='typewriter') throw new Error('simulated typing error');
    element.textContent=value;
  };
  const context = {
    document,window,ctx,fetch,makeUserPrompt,choices,mainContainer,typeText,
    requestId:8,responseMessageClass:'gtp-chat-copy',stockName:'SK하이닉스',
    Intl,setTimeout:fn => {registry.timers.push(true);fn();},console:{
      warn:(...args)=>registry.warnings.push(args.map(String).join(' '))
    }
  };
  vm.runInNewContext(presenter,context);
  assert.ok(window.GaemiGTPUSCloseReply.normalize(original),
    'renderer must accept actual saved-data fixture');
  assert.ok(window.GaemiGTPUSCloseReply.plainText(original).includes('나스닥 종합'),
    'renderer must format actual fixture');
  if (failure==='table') {
    window.GaemiGTPUSCloseReply.render=async()=>{throw new Error('simulated table error');};
  }
  if (failure==='normalize') {
    window.GaemiGTPUSCloseReply.normalize=()=>{throw new Error('simulated normalize error');};
  }
  await vm.runInNewContext('(async () => {'+segment+
    ' await appendUsMarketPrompt(); })()',context);
  assert.equal(registry.fetches.length,1);
  assert.match(registry.fetches[0].url,/\/api\/market\/us-close$/);
  assert.equal(registry.fetches[0].options.method,'GET');
  assert.ok(registry.timers.length,'should wait for the existing 5-second transition');
  const answer=registry.inserted.find(n=>n.className==='gtp-chat-copy mt-4');
  assert.ok(answer,'answer container must always be mounted after thinking');
  assert.ok(answer.textContent.includes('AI·반도체 반등'));
  assert.ok(answer.textContent.includes('10월 19일 미국증시는'));
  assert.ok(!answer.textContent.includes('미국장 마감시황을 표시하지 못했어.'));
  assert.equal(registry.actions.length,1,'existing copy/share/like controls must be kept');
  if (!failure) {
    const issue=answer.children[0];
    assert.ok(issue && issue.children[1]?.children[0]?.tagName==='table',
      'successful render must show a real table under the headline: '+JSON.stringify({
        warnings:registry.warnings,answerChildren:answer.children.length,
        issueChildren:issue?.children?.length,reply:answer.textContent.slice(0,120)}));
    assert.ok(issue.children[0].textContent.includes('AI·반도체 반등'));
    assert.ok(issue.children[2].textContent.includes('10월 19일'));
  } else {
    assert.ok(answer.textContent.includes('다우존스 51,966.03'),
      'on error restore saved backend content and three index closes');
  }
}

(async()=>{
  for (const scenarioType of [null,'table','normalize','typewriter']) {
    await scenario(scenarioType);
  }
  console.log('US_CLOSE_FOLLOWUP_ERROR_RECOVERY_AND_TABLE_PASS');
})().catch(error=>{console.error(error);process.exitCode=1;});
