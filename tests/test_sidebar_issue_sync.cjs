'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const test = require('node:test');

const sidebarSource = fs.readFileSync('frontend/shell/left-market-sidebar/market-sidebar.js', 'utf8');
const indexHtml = fs.readFileSync('frontend/index.html', 'utf8');
const analysisSource = fs.readFileSync('frontend/shell/center-chat/analysis-flow.js', 'utf8');

class Element {
  constructor(textContent = '') {
    this.textContent = textContent;
    this.dataset = {};
    this.listeners = {};
    this.children = [];
    this.disabled = false;
    this.attributes = {};
    this.classList = { toggle() {}, contains() { return false; }, remove() {} };
  }
  addEventListener(event, handler) { (this.listeners[event] ||= []).push(handler); }
  click() { (this.listeners.click || []).forEach(fn => fn()); }
  setAttribute(key, value) { this.attributes[key] = value; }
  replaceChildren(...nodes) { this.children = [...nodes]; }
  appendChild(node) { this.children.push(node); }
}

function setup() {
  const kr = new Element('국내');
  const us = new Element('해외');
  const coin = new Element('코인'); coin.disabled = true;
  const cap = new Element('시가총액'); cap.dataset.infoTabAction = 'cap';
  const popular = new Element('인기 순위'); popular.dataset.infoTabAction = 'popular';
  const value = new Element('거래대금'); value.dataset.infoTabAction = 'value';
  const list = new Element();
  const title = new Element();
  const subtitle = new Element();
  const sidebar = new Element();
  sidebar.querySelector = selector => ({
    '#marketRankingList': list,
    '#rightListTitle': title,
    '.market-sidebar-subtitle': subtitle
  })[selector] || null;
  sidebar.querySelectorAll = selector => ({
    '[data-legacy-region]': [kr, us, coin],
    '[data-info-tab-action]': [cap, popular, value]
  })[selector] || [];
  const documentListeners = {};
  const document = {
    body: { classList: { contains() { return false; }, remove() {}, toggle() {} } },
    getElementById(id) { return id === 'leftMarketSidebar' ? sidebar : null; },
    createElement() { return new Element(); },
    addEventListener(name, handler) { documentListeners[name] = handler; }
  };
  let fetchCalls = 0;
  const window = {
    innerWidth: 1200,
    addEventListener() {}
  };
  vm.runInNewContext(sidebarSource, {
    document, window, console,
    fetch() { fetchCalls++; throw new Error('legacy market fetch must not run'); }
  });
  documentListeners.DOMContentLoaded();
  return { kr, us, coin, cap, popular, value, list, title, subtitle, sidebar,
    get fetchCalls() { return fetchCalls; } };
}

test('old market tabs, KR/US controls, and stock-row layout are restored', () => {
  const html = indexHtml.split('id="leftMarketSidebar"')[1].split('<!-- 왼쪽 실적 캘린더')[0];
  for (const section of ['전체', '국내', '해외', '코인', '시가총액', '인기 순위', '거래대금', '산업', '테마']) {
    assert.ok(html.includes('>' + section + '</button>'), section + ' missing');
  }
  assert.deepEqual([...html.matchAll(/data-info-tab-action="([^"]+)"/g)].map(x => x[1]),
    ['cap', 'popular', 'value', 'industry', 'theme']);
  assert.match(html, /rightListMetric/);
  assert.match(html, /data-legacy-region="true" class="[^"]*bg-\[#eef2f7\][^"]*">해외<\/button>/);
  assert.match(html, /marketRankingList/);
  assert.doesNotMatch(html, /onclick="openStockInChat|257,500원/);
});

test('existing KR and US popular/trading-value requests remain wired', () => {
  assert.match(sidebarSource, /\/market\/trading-value/);
  assert.match(sidebarSource, /\/market\/popular/);
  assert.match(sidebarSource, /refreshAnalyzedIssue/);
  assert.match(sidebarSource, /openStockInChat/);
  assert.match(sidebarSource, /applyChangeSort/);
});

test('US cap uses existing stock name and AI headline API in original row classes', () => {
  assert.match(sidebarSource, /\/api\/market\/us-cap-headlines/);
  assert.match(sidebarSource, /stock\.headlines/);
  assert.match(sidebarSource, /grid-cols-\[24px_minmax\(0,1fr\)_auto\]/);
  assert.match(sidebarSource, /showCapRanking/);
  assert.doesNotMatch(sidebarSource, /fixedStockIssuePanel|GaemiGTPWatchlist/);
});

test('central issue event stays in analysis flow for future US row integration', () => {
  assert.match(analysisSource, /gaemi:analysis-issues-ready/);
});


test('right panel keeps the complete last-30-days list without the duplicate SEC dropdown', () => {
  const panel = fs.readFileSync('frontend/shell/right-panel/right-panel-tabs.js', 'utf8');
  const engine = fs.readFileSync('backend/services/engine.py', 'utf8');
  const app = fs.readFileSync('app.py', 'utf8');
  assert.match(engine, /fetch_us_official_filings\(ticker_symbol, days=30, max_results=30, complete_window=True\)/);
  assert.match(engine, /fetch_kr_official_disclosures\(clean_code, days=30, max_results=0\)/);
  assert.match(engine, /if not complete_window and len\(results\) >= max_results:/);
  assert.match(engine, /if not complete_window:\s+results = \[/);
  assert.match(engine, /for page_no in range\(2, total_pages \+ 1\)/);
  assert.match(panel, /panelWorkspaceView === 'disclosures'/);
  assert.doesNotMatch(panel, /\.slice\(0, 30\)/);
  assert.doesNotMatch(panel, /GaemiGTPUSSecRightPanel|공시 상세보기 ▾/);
  assert.doesNotMatch(app, /\/disclosures\/sec\/detail|\/disclosures\/sec\/today/);
  assert.doesNotMatch(indexHtml, /us-sec-detail\.js|sec-chat\.js/);
  for (const artifact of [
    'frontend/shell/right-panel/us-sec-detail.js',
    'backend/services/us_sec_disclosures.py',
    'tests/test_us_sec_display.py',
    '.github/workflows/us-sec-chat-display-check.yml'
  ]) {
    assert.equal(fs.existsSync(artifact), false, 'redundant file still exists: ' + artifact);
  }
});
