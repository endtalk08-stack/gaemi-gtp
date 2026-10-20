// Offline regression: info/pro must use their own AI models, not gaemi US-close API.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

class Node {
  constructor(tag) {
    this.tagName = tag;
    this.children = [];
    this.isConnected = true;
    this.dataset = {chatMessageId: '1'};
    this.className = '';
    this._text = '';
    this.classList = {
      add() {}, remove() {}, contains() {return false;}
    };
  }
  set textContent(value) {this._text = String(value);this.children = [];}
  get textContent() {return this._text+this.children.map(child=>child.textContent).join('');}
  appendChild(node) {this.children.push(node);return node;}
  querySelector() {return null;}
  scrollIntoView() {}
  remove() {this.isConnected=false;}
  setAttribute() {}
}

async function routeFor(mode) {
  const session = {id:1,mode,stock:''};
  const calls = [];
  const rows = [];
  let pending = 1;
  const chatArea = new Node('div');
  const document = {
    head:new Node('head'),
    getElementById: id => id === 'chatArea' ? chatArea : null,
    createElement:tag=>new Node(tag)
  };
  const window = {
    GaemiGTPAppState:{getCurrentAppMode:()=>mode},
    GaemiGTPCenterChatSearch:{resolveStockMention:()=>''},
    GaemiGTPFirstReplyActions:{appendFirstReplyActions:()=>null}
  };
  const fetch = async (url, options={}) => {
    calls.push({url,options});
    const close = url.endsWith('/api/market/us-close');
    return {
      ok:true,
      json:async()=>close
        ? {ok:true,available:true,content:'시장 마감',presentation:null}
        : {ok:true,answer:'AI 모델의 실제 답변'}
    };
  };
  const sandbox = {
    window,document,fetch,AbortController,
    setTimeout:cb=>{Promise.resolve().then(cb);return 1;},
    clearTimeout:()=>{}
  };
  vm.runInNewContext(
    fs.readFileSync('frontend/shell/center-chat/ai-chat.js','utf8'), sandbox
  );
  const ai=window.GaemiGTPCenterAIChat.create({
    backendUrl:'https://fake-local.test',
    getSession:()=>session,
    getPendingAnalysis:()=>null,
    getPendingQuestionSessionId:()=>pending,
    setPendingQuestionSessionId:v=>{pending=v;},
    getActiveQuestionController:()=>null,
    setActiveQuestionController:()=>{},
    appendChatMessage:(_role,text)=>{
      const row=new Node('div');
      row.textContent=text;
      rows.push(row);
      return row;
    }
  });
  await ai.requestChatAnswer('미국장 어땠어?',1,[]);
  assert.equal(calls.length,1,mode+' should make exactly one request');
  if (mode === 'gaemi') {
    assert.ok(calls[0].url.endsWith('/api/market/us-close'));
    assert.equal(calls[0].options.method,'GET');
  } else {
    assert.ok(calls[0].url.endsWith('/api/ai-test/chat'),mode+' must not be hijacked by close API');
    assert.equal(calls[0].options.method,'POST');
    const body=JSON.parse(calls[0].options.body);
    assert.equal(body.app_mode,mode);
    assert.equal(body.question,'미국장 어땠어?');
  }
  assert.ok(rows.some(row=>row.textContent.includes(
    mode === 'gaemi' ? '시장 마감' : 'AI 모델의 실제 답변'
  )),mode+' must show reply');
}

async function main() {
  for (const mode of ['gaemi','info','pro']) await routeFor(mode);
  const flow=fs.readFileSync('frontend/shell/center-chat/analysis-flow.js','utf8');
  assert.match(flow,/const isGaemiMode = \(\) => ctx\.getSession\(\)\?\.mode === 'gaemi'/);
  assert.ok(!flow.includes('if (!isGaemiMode()) choices.querySelector'), 'info/pro US option must remain visible');
  assert.ok(flow.includes("window.GaemiGTPApp?.submitQuestion?.('미국장 어땠어?')"),
            'info/pro follow-up must use their independent AI model');
  assert.ok(flow.includes("'#미국장_어땠어?'"), 'requested hashtag must be visible');
  assert.match(flow,/if \(!isGaemiMode\(\) \|\| mainContainer\.querySelector/);
  assert.match(flow,/answer\.textContent = verifiedContent \|\| replyText \|\| '미국장 마감시황을 불러오지 못했어\.'/);
  console.log('US_CLOSE_GAEMI_ONLY_INFO_PRO_MODEL_ROUTES_PASS');
}
main().catch(e=>{console.error(e);process.exitCode=1;});
