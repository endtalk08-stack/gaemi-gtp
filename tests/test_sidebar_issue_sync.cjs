'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const test = require('node:test');

const sidebarSource = fs.readFileSync('frontend/shell/left-market-sidebar/market-sidebar.js', 'utf8');
const stockMarksSource = fs.readFileSync('frontend/shell/left-market-sidebar/stock-marks.js', 'utf8');
const sidebarCss = fs.readFileSync('frontend/shell/left-market-sidebar/market-sidebar.css', 'utf8');
const analysisSource = fs.readFileSync('frontend/shell/center-chat/analysis-flow.js', 'utf8');

class Element {
  constructor(tagName = 'div') {
    this.tagName = tagName;
    this.dataset = {};
    this.children = [];
    this.listeners = {};
    this.classList = { toggle() {} };
    this.style = {};
    this.textContent = '';
    this.innerHTML = '';
  }
  addEventListener(name, handler) { (this.listeners[name] ||= []).push(handler); }
  click() { for (const fn of this.listeners.click || []) fn(); }
  setAttribute() {}
  append(...nodes) { for (const node of nodes) this.appendChild(node); }
  appendChild(child) {
    this.children = this.children.filter((node) => node !== child);
    this.children.push(child);
    return child;
  }
  insertBefore(child, sibling) {
    this.children = this.children.filter((node) => node !== child);
    const index = this.children.indexOf(sibling);
    if (index < 0) this.children.push(child);
    else this.children.splice(index, 0, child);
    return child;
  }
  focus() {}
  replaceChildren(...nodes) { this.children = [...nodes]; }
  contains(child) { return this.children.includes(child); }
  querySelectorAll(selector) {
    if (selector === ':scope > button[data-original-index]') {
      return this.children.filter((item) => item.tagName === 'button' && 'originalIndex' in item.dataset);
    }
    return [];
  }
  querySelector(selector) {
    const key = selector === '[data-market-rank]' ? 'marketRank' :
      selector === '[data-stock-issue]' ? 'stockIssue' : null;
    if (!key) return null;
    const search = (node) => {
      if (node.dataset[key]) return node;
      for (const child of node.children) {
        const found = search(child);
        if (found) return found;
      }
      return null;
    };
    return search(this);
  }
}

const flush = () => new Promise((resolve) => setImmediate(resolve));

function setup({ deferred = false, initialOrder = [] } = {}) {
  const storage = new Map([[
    'gaemiGTP_market_sidebar_order_us_value_v1', JSON.stringify(initialOrder)
  ]]);
  const localStorage = {
    getItem(key) { return storage.get(key) || null; },
    setItem(key, value) { storage.set(key, value); }
  };
  const list = new Element('div');
  const title = new Element();
  const metric = new Element();
  const subtitle = new Element();
  const realtimeTab = new Element('button'); realtimeTab.dataset.infoTabAction = 'realtime';
  const valueTab = new Element('button'); valueTab.dataset.infoTabAction = 'value';
  const gainTab = new Element('button'); gainTab.dataset.infoTabAction = 'gain';
  const lossTab = new Element('button'); lossTab.dataset.infoTabAction = 'loss';
  const sidebar = new Element();
  sidebar.querySelector = (selector) => ({
    '#marketRankingList': list,
    '#rightListTitle': title,
    '#rightListMetric': metric,
    '.market-sidebar-subtitle': subtitle
  })[selector] || null;
  sidebar.querySelectorAll = (selector) =>
    selector === '[data-info-tab-action]' ? [realtimeTab, valueTab, gainTab, lossTab] : [];
  const documentListeners = {};
  const logoImages = [];
  const document = {
    body: { classList: { contains() { return false; }, remove() {}, toggle() {} } },
    getElementById(id) { return id === 'leftMarketSidebar' ? sidebar : null; },
    createElement(tagName) {
      const element = new Element(tagName);
      if (tagName === 'img') logoImages.push(element);
      return element;
    },
    createElementNS(_namespace, tagName) { return new Element(tagName); },
    addEventListener(name, fn) { documentListeners[name] = fn; }
  };
  const listeners = {};
  const window = {
    innerWidth: 1200,
    location: { hostname: 'gaemi-gtp.onrender.com', origin: 'https://gaemi-gtp.onrender.com' },
    // Fake browser: acknowledge polling without starting a background timer.
    setInterval() { return 1; },
    addEventListener(name, fn) { (listeners[name] ||= []).push(fn); }
  };
  const calls = [];
  let valueRows = [
    { name: '일라이 릴리', symbol: 'LLY', mark_ticker: 'LLY', identity_status: 'verified', issue_headline: '' },
    { name: '테슬라', symbol: 'TSLA.O', mark_ticker: 'TSLA', identity_status: 'verified', issue_headline: '기존 이슈' }
  ];
  let resolveDeferred = null;
  const fetch = async (url, opts) => {
    calls.push({ url, opts });
    if (url.endsWith('/market/trading-value?market=us')) {
      return { ok: true, json: async () => ({ ok: true, items: valueRows }) };
    }
    if (url.endsWith('/market/issue-headlines')) {
      const request = JSON.parse(opts.body);
      assert.deepEqual(request, { market: 'us', items: [{ name: '일라이 릴리', symbol: 'LLY' }] });
      if (deferred) {
        await new Promise((resolve) => { resolveDeferred = resolve; });
      }
      return { ok: true, json: async () => ({ ok: true, items: [
        { name: '일라이 릴리', symbol: 'LLY', headline: '사업 제휴 이슈' }
      ] }) };
    }
    throw new Error('unexpected request: ' + url);
  };
  vm.runInNewContext(stockMarksSource, { window });
  vm.runInNewContext(sidebarSource, { window, document, fetch, console, localStorage });
  documentListeners.DOMContentLoaded();
  return {
    list, realtimeTab, valueTab, gainTab, lossTab, calls, storage, logoImages,
    replaceValueRows(rows) { valueRows = rows; valueTab.click(); },
    event(detail) { for (const handler of listeners['gaemi:analysis-issues-ready'] || []) handler({ detail }); },
    resolvePost() { assert.ok(resolveDeferred); resolveDeferred(); }
  };
}

test('newly stored Eli Lilly issue updates its sidebar row without fetching rankings again', async () => {
  const app = setup();
  await flush();
  assert.ok(app.calls[0].url.endsWith('/market/trading-value?market=us'));
  const before = app.list.querySelectorAll(':scope > button[data-original-index]');
  assert.equal(before.length, 2);
  assert.equal(before[0].querySelector('[data-stock-issue]').textContent, '');
  const rankingCalls = app.calls.length;

  app.event({ name: '일라이 릴리', market: 'us', symbol: 'LLY' });
  await flush();
  assert.equal(app.calls.length, rankingCalls + 1);
  assert.ok(app.calls.at(-1).url.endsWith('/market/issue-headlines'));
  const after = app.list.querySelectorAll(':scope > button[data-original-index]');
  assert.equal(after[0], before[0], 'existing DOM row must stay intact');
  assert.equal(after[0].querySelector('[data-stock-issue]').textContent, '사업 제휴 이슈');
  assert.equal(after[1].querySelector('[data-stock-issue]').textContent, '기존 이슈');
});

test('unrelated analysis and wrong market do not make requests', async () => {
  const app = setup();
  await flush();
  const n = app.calls.length;
  app.event({ name: '없는 종목', market: 'us', symbol: 'NONE' });
  app.event({ name: '일라이 릴리', market: 'kr', symbol: 'LLY' });
  await flush();
  assert.equal(app.calls.length, n);
});

test('stale lookup must not write to a rebuilt sidebar', async () => {
  const app = setup({ deferred: true });
  await flush();
  app.event({ name: '일라이 릴리', market: 'us', symbol: 'LLY' });
  await flush();
  app.realtimeTab.click();
  await flush();
  app.resolvePost();
  await flush();
  assert.equal(app.list.querySelectorAll(':scope > button[data-original-index]').length, 0);
  assert.match(app.list.textContent, /AI 분석 결과 연결 전/);
});

test('central analysis announces only completed and populated briefs', () => {
  assert.match(analysisSource, /Array\.isArray\(result\.issue_briefs\) && result\.issue_briefs\.length > 0/);
  assert.match(analysisSource, /gaemi:analysis-issues-ready/);
  assert.match(analysisSource, /session\.marketSelection\?\.symbol/);
});

test('market cards show stock logo slot and allow keyboard reorder without changing source ranks', async () => {
  const app = setup();
  await flush();
  const before = app.list.querySelectorAll(':scope > button[data-original-index]');
  assert.equal(before[1].dataset.stockSymbol, 'TSLA.O');
  assert.equal(before[1].children[1].className, 'market-stock-logo');
  assert.equal(before[1].children[0].draggable, true);

  let prevented = false;
  before[1].listeners.keydown[0]({
    altKey: true,
    key: 'ArrowUp',
    preventDefault() { prevented = true; }
  });
  assert.equal(prevented, true);
  const reordered = app.list.querySelectorAll(':scope > button[data-original-index]');
  assert.equal(reordered[0].dataset.stockSymbol, 'TSLA.O');
  assert.equal(reordered[0].querySelector('[data-market-rank]').textContent, '02');
  assert.equal(reordered[1].querySelector('[data-market-rank]').textContent, '01');
  assert.deepEqual(JSON.parse(app.storage.get('gaemiGTP_market_sidebar_order_us_value_v1')),
    ['TSLA.O', 'LLY']);
});

test('fresh ranking ignores stale saved order before and after tab changes', async () => {
  const app = setup({ initialOrder: ['LLY', 'LLY'] });
  await flush();
  assert.equal(app.list.querySelectorAll(':scope > button[data-original-index]')[0].dataset.stockSymbol, 'LLY');
  app.realtimeTab.click();
  await flush();
  assert.equal(app.list.querySelectorAll(':scope > button[data-original-index]').length, 0);
  app.valueTab.click();
  await flush();
  assert.equal(app.list.querySelectorAll(':scope > button[data-original-index]')[0].dataset.stockSymbol, 'LLY');
});

test('local company logos render as SVG even for .O symbols', async () => {
  const app = setup();
  await flush();
  const popular = app.list.querySelectorAll(':scope > button[data-original-index]');
  const teslaMark = popular[1].children[1];
  assert.equal(teslaMark.children[0].tagName, 'svg', 'TSLA.O must resolve to bundled TSLA logo');
  assert.equal(teslaMark.children[0].children[0].tagName, 'path');
  app.replaceValueRows([{ name: '엔비디아', symbol: 'NVDA.O', mark_ticker: 'NVDA', identity_status: 'verified' }]);
  await flush();
  const nvidiaMark = app.list.querySelectorAll(':scope > button[data-original-index]')[0].children[1];
  assert.equal(nvidiaMark.children[0].tagName, 'svg', 'NVDA must have an embedded logo');
});

test('ranked ticker identity automatically changes the mark and never borrows another logo', async () => {
  const app = setup();
  await flush();
  app.replaceValueRows([{ name: '신규 상장사', symbol: 'NEWT.O', mark_ticker: '', identity_status: 'pending' }]);
  await flush();
  const unknown = app.list.querySelectorAll(':scope > button[data-original-index]')[0].children[1];
  assert.equal(unknown.children[0].textContent, 'NEWT');
  assert.equal(unknown.children[0].tagName, 'span');

  app.replaceValueRows([{ name: '엔비디아', symbol: 'NVDA.O', mark_ticker: 'NVDA', identity_status: 'verified' }]);
  await flush();
  const verified = app.list.querySelectorAll(':scope > button[data-original-index]')[0].children[1];
  assert.equal(verified.children[0].tagName, 'svg');

  app.replaceValueRows([{ name: '다른 회사', symbol: 'AAPL.O', mark_ticker: 'NVDA', identity_status: 'verified' }]);
  await flush();
  const mismatched = app.list.querySelectorAll(':scope > button[data-original-index]')[0].children[1];
  assert.equal(mismatched.children[0].textContent, 'AAPL');
  assert.equal(mismatched.children[0].tagName, 'span');
});

test('AnyLogo loads automatically by the exact Neon-verified ticker and replaces existing logo', async () => {
  const app = setup();
  await flush();
  const rows = app.list.querySelectorAll(':scope > button[data-original-index]');
  assert.equal(app.logoImages.length, 2, 'one logo lookup per verified source ticker');
  const tesla = app.logoImages[1];
  assert.equal(tesla.src, 'https://img.anylogo.dev/ticker/TSLA?size=64&variant=icon');
  assert.equal(tesla.referrerPolicy, 'no-referrer');
  const before = rows[1].children[1];
  assert.equal(before.children[0].tagName, 'svg', 'local logo stays visible while loading');
  tesla.naturalWidth = 64;
  tesla.listeners.load[0]();
  assert.equal(before.children[0], tesla, 'verified logo replaces the fallback on load');

  const lily = app.logoImages[0];
  lily.listeners.error[0]();
  assert.equal(rows[0].children[1].children[0].tagName, 'span',
    'failed logo request keeps its ticker mark');
});

test('AnyLogo accepts source-listed pending tickers but rejects mismatched identities', async () => {
  const app = setup();
  await flush();
  const before = app.logoImages.length;
  app.replaceValueRows([
    { name: '버크셔 Class B', symbol: 'BRK.B', mark_ticker: 'BRK.B', identity_status: 'verified' },
    { name: '신규 종목', symbol: 'NEWT.O', mark_ticker: '', logo_lookup_ticker: 'NEWT', identity_status: 'pending' },
    { name: '다른 기업', symbol: 'AAPL.O', mark_ticker: 'NVDA', logo_lookup_ticker: 'AAPL', identity_status: 'verified' },
    { name: '검증 불가', symbol: '../INVALID', mark_ticker: '../INVALID', identity_status: 'verified' }
  ]);
  await flush();
  assert.equal(app.logoImages.length, before + 2, 'verified and source-listed pending tickers both load');
  assert.equal(app.logoImages.at(-2).src,
    'https://img.anylogo.dev/ticker/BRK.B?size=64&variant=icon');
  assert.equal(app.logoImages.at(-1).src,
    'https://img.anylogo.dev/ticker/NEWT?size=64&variant=icon');
  const rows = app.list.querySelectorAll(':scope > button[data-original-index]');
  assert.equal(rows.length, 4);
  assert.equal(rows[1].children[1].children[0].textContent, 'NEWT');
  assert.equal(rows[2].children[1].children[0].textContent, 'AAPL');
  assert.equal(rows[3].children[1].children[0].tagName, 'span');
});

test('pending tickers do not change their identity when an external logo fails', async () => {
  const app = setup();
  await flush();
  const prior = app.logoImages.length;
  app.replaceValueRows([
    { name: '램 리서치', symbol: 'LRCX.O', identity_status: 'pending',
      mark_ticker: '', logo_lookup_ticker: 'LRCX' },
    { name: '블룸 에너지', symbol: 'BE', identity_status: 'pending',
      mark_ticker: '', logo_lookup_ticker: 'BE' },
    { name: '어플라이드 머티어리얼즈', symbol: 'AMAT.O', identity_status: 'pending',
      mark_ticker: '', logo_lookup_ticker: 'AMAT' }
  ]);
  await flush();
  assert.deepEqual(Array.from(app.logoImages.slice(prior), (img) => img.src), [
    'https://img.anylogo.dev/ticker/LRCX?size=64&variant=icon',
    'https://img.anylogo.dev/ticker/BE?size=64&variant=icon',
    'https://img.anylogo.dev/ticker/AMAT?size=64&variant=icon'
  ]);
  const rows = app.list.querySelectorAll(':scope > button[data-original-index]');
  assert.deepEqual(Array.from(rows, (r) => r.dataset.stockSymbol), ['LRCX.O', 'BE', 'AMAT.O']);
  app.logoImages.at(-1).listeners.error[0]();
  assert.equal(rows[2].children[1].children[0].textContent, 'AMAT');
});

test('new side menus do not query a fake partial TOP20 ranking', async () => {
  const app = setup();
  await flush();
  const existingCalls = app.calls.length;
  app.gainTab.click();
  app.lossTab.click();
  app.realtimeTab.click();
  await flush();
  assert.equal(app.calls.length, existingCalls);
  assert.equal(app.list.querySelectorAll(':scope > button[data-original-index]').length, 0);
});

test('market list keeps readable original font sizes', () => {
  assert.match(sidebarCss, /\.market-stock-name\s*\{\s*font-size:\s*13px/);
  assert.match(sidebarCss, /\.market-stock-price\s*\{[^}]*font-size:\s*13px/);
  assert.match(sidebarCss, /\.market-stock-third \[data-stock-issue\][\s\S]*font-size:\s*13px/);
});
