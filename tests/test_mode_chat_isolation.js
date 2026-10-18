// Offline regression for gaemi/info/pro transcript isolation and restored history.
// Uses an in-memory DOM and localStorage; makes no provider, DB or network calls.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

class Node {
  constructor(tag = 'div') {
    this.tagName = tag;
    this.children = [];
    this.parent = null;
    this._text = '';
    this.dataset = {};
    this.hidden = false;
    this.isFragment = tag === '#fragment';
    this.classes = new Set();
    this.classList = {
      contains: (name) => this.classes.has(name),
      add: (name) => this.classes.add(name),
      remove: (name) => this.classes.delete(name),
    };
  }
  set className(value) { this.classes = new Set(String(value).split(/\\s+/).filter(Boolean)); }
  get className() { return [...this.classes].join(' '); }
  set textContent(value) { this.children.forEach(node => { node.parent = null; }); this.children = []; this._text = String(value); }
  get textContent() { return this._text + this.children.map(n => n.textContent).join(''); }
  get firstChild() { return this.children[0] || null; }
  appendChild(node) {
    if (node.isFragment) { while (node.firstChild) this.appendChild(node.firstChild); return node; }
    if (node.parent) node.parent.removeChild(node);
    this.children.push(node);
    node.parent = this;
    return node;
  }
  removeChild(node) {
    const i = this.children.indexOf(node);
    if (i !== -1) this.children.splice(i, 1);
    node.parent = null;
  }
  replaceChildren(...nodes) {
    this.children.forEach(n => { n.parent = null; });
    this.children = []; this._text = '';
    nodes.forEach(n => this.appendChild(n));
  }
  remove() { this.parent?.removeChild(this); }
  querySelectorAll(selector) {
    const found = [];
    const traverse = (node) => {
      for (const child of node.children) {
        if (selector.startsWith('.') && child.classList.contains(selector.slice(1))) found.push(child);
        traverse(child);
      }
    };
    traverse(this);
    return found;
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  setAttribute(key, value) { this[key] = String(value); }
}

const HISTORY_KEY = 'gaemiGTP_chat_history_v1';
const RECENT_KEY = 'gaemiGTP_recent_searches_v1';
function boot(store) {
  const root = {
    chatArea: new Node('div'),
    leftSidebarHomeRecentList: new Node('ul'),
    leftSidebarHomeRecentEmpty: new Node('p'),
  };
  const localStorage = {
    getItem: key => store.has(key) ? store.get(key) : null,
    setItem: (key,value) => { store.set(key, String(value)); },
  };
  const document = {
    getElementById: (key) => root[key] || null,
    createElement: tag => new Node(tag),
    createDocumentFragment: () => new Node('#fragment'),
    addEventListener: () => {},
  };
  const window = {
    location: { hostname:'gaemi-gtp.onrender.com', origin:'https://gaemi-gtp.onrender.com' },
    addEventListener: () => {},
    innerWidth: 1400,
    GaemiGTPCenterAIChat: {
      create: (ctx) => ({
        submitQuestion: (question, {newConversation=false}={}) => {
          if (newConversation || !ctx.getSession()) ctx.beginChatSession();
          const sessionId = ctx.getSession().id;
          const row = ctx.appendChatMessage('user', question, 'question', sessionId);
          if (!row) return false;
          window.GaemiGTPApp.linkRecentConversation('question', question);
          return true;
        },
        appendChatReply: () => false,
      })
    },
    GaemiGTPCenterAnalysisFlow: { create: (ctx) => ({
      requestStock: (name) => {
        const session = ctx.beginChatSession(name);
        ctx.appendChatMessage('user', name, 'stock', session.id);
        window.GaemiGTPApp.linkRecentConversation('stock', name);
      }
    }) },
    GaemiGTPCenterChatSearch: {
      selectAppMode: mode => window.GaemiGTPAppState.setCurrentAppMode(mode),
    },
  };
  const context = {window, document, localStorage, console, AbortController, setTimeout, clearTimeout};
  for (const path of [
    'frontend/shell/left-sidebar-home/left-sidebar-home.js',
    'frontend/js/app.js'
  ]) vm.runInNewContext(fs.readFileSync(path,'utf8'), context, {filename:path});
  return {window, root, store};
}
function texts(area) { return [...area.children].map(node => node.textContent); }

const store = new Map();
let {window:w, root:r} = boot(store);
const mode = w.GaemiGTPAppState;
const app = w.GaemiGTPApp;
assert.equal(mode.getCurrentAppMode(), 'gaemi');
assert.equal(app.submitQuestion('개미 전용 질문', {newConversation:true}), true);
const gaemiId = app.getChatState().id;
assert.deepEqual(texts(r.chatArea), ['개미 전용 질문']);
mode.setCurrentAppMode('info');
assert.deepEqual(texts(r.chatArea), [], 'info must not contain gaemi messages');
assert.equal(app.submitQuestion('인포 전용 질문'), true);
const infoId = app.getChatState().id;
assert.equal(app.getChatState().mode, 'info');
assert.deepEqual(texts(r.chatArea), ['인포 전용 질문']);
mode.setCurrentAppMode('pro');
assert.deepEqual(texts(r.chatArea), [], 'pro must not contain info messages');
assert.equal(app.submitQuestion('프로 전용 질문'), true);
const proId = app.getChatState().id;
assert.equal(app.getChatState().mode, 'pro');
mode.setCurrentAppMode('info');
assert.deepEqual(texts(r.chatArea), ['인포 전용 질문']);
assert.notEqual(app.getChatState().id, infoId, 'return should invalidate old callbacks');
mode.setCurrentAppMode('gaemi');
assert.deepEqual(texts(r.chatArea), ['개미 전용 질문']);
assert.notEqual(app.getChatState().id, gaemiId);
mode.setCurrentAppMode('pro');
assert.deepEqual(texts(r.chatArea), ['프로 전용 질문']);
assert.notEqual(app.getChatState().id, proId);
const saved = JSON.parse(store.get(HISTORY_KEY));
assert.equal(Object.values(saved).filter(v=>v.mode==='gaemi').length, 1);
assert.equal(Object.values(saved).filter(v=>v.mode==='info').length, 1);
assert.equal(Object.values(saved).filter(v=>v.mode==='pro').length, 1);
const recents = JSON.parse(store.get(RECENT_KEY));
assert.equal(recents.length, 3);
assert.deepEqual(recents.map(v=>v.mode), ['pro','info','gaemi']);
w.GaemiGTPSidebarHome.renderRecent();
assert.deepEqual(r.leftSidebarHomeRecentList.children.map(li=>li.textContent), ['프로 전용 질문']);
mode.setCurrentAppMode('info');
assert.deepEqual(r.leftSidebarHomeRecentList.children.map(li=>li.textContent), ['인포 전용 질문']);

// New current-mode thread must not replace the other two.
assert.equal(app.submitQuestion('인포 새 질문', {newConversation:true}), true);
mode.setCurrentAppMode('gaemi');
assert.deepEqual(texts(r.chatArea), ['개미 전용 질문']);
mode.setCurrentAppMode('info');
assert.deepEqual(texts(r.chatArea), ['인포 새 질문']);

// Page reload should rehydrate the last conversation for each mode.
({window:w,root:r} = boot(store));
w.GaemiGTPAppState.setCurrentAppMode('info');
assert.deepEqual(texts(r.chatArea), ['인포 새 질문']);
w.GaemiGTPAppState.setCurrentAppMode('pro');
assert.deepEqual(texts(r.chatArea), ['프로 전용 질문']);
w.GaemiGTPAppState.setCurrentAppMode('gaemi');
assert.deepEqual(texts(r.chatArea), ['개미 전용 질문']);

// Clicking saved info thread from gaemi must switch the selected mode.
const savedInfo = JSON.parse(store.get(RECENT_KEY)).find(item=>item.mode==='info');
assert.equal(w.GaemiGTPApp.restoreRecentConversation(savedInfo.id), true);
assert.equal(w.GaemiGTPAppState.getCurrentAppMode(), 'info');
assert.deepEqual(texts(r.chatArea), ['인포 새 질문']);

// Previously saved unlabelled history remains readable from the current mode.
const legacyId = 'conversation:legacy';
const h = JSON.parse(store.get(HISTORY_KEY));
h[legacyId] = {stock:null,messages:[{role:'user',kind:'question',text:'기존 대화'}]};
store.set(HISTORY_KEY,JSON.stringify(h));
assert.equal(w.GaemiGTPApp.restoreRecentConversation(legacyId), true);
assert.equal(w.GaemiGTPAppState.getCurrentAppMode(), 'info');
assert.deepEqual(texts(r.chatArea), ['기존 대화']);

// Sidebars keep ten recent items per mode, not ten globally.
for (const m of ['gaemi','pro','info']) {
  w.GaemiGTPAppState.setCurrentAppMode(m);
  for (let i=0;i<12;i++) w.GaemiGTPApp.submitQuestion(m+'_'+i,{newConversation:true});
}
const perMode = JSON.parse(store.get(RECENT_KEY));
for (const m of ['gaemi','info','pro']) {
  assert.equal(perMode.filter(v=>v.mode===m).length,10,m+' retains 10 items');
  w.GaemiGTPAppState.setCurrentAppMode(m);
  w.GaemiGTPSidebarHome.renderRecent();
  assert.equal(r.leftSidebarHomeRecentList.children.length,10,m+' sidebar has 10 items');
}
console.log('MODE_CHATS_ISOLATED_RESTORED_RECENTS_OK');
