'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const test = require('node:test');

const sidebarSource = fs.readFileSync('frontend/shell/left-market-sidebar/market-sidebar.js', 'utf8');
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

function setup({ deferred = false } = {}) {
  let postStatus = 'ready';
  let clock = 1000000;
  const list = new Element('div');
  const title = new Element();
  const metric = new Element();
  const subtitle = new Element();
  const kr = new Element('button'); kr.textContent = '국내';
  const us = new Element('button'); us.textContent = '해외';
  const sidebar = new Element();
  sidebar.querySelector = (selector) => ({
    '#marketRankingList': list,
    '#rightListTitle': title,
    '#rightListMetric': metric,
    '.market-sidebar-subtitle': subtitle
  })[selector] || null;
  sidebar.querySelectorAll = (selector) =>
    selector === '[data-legacy-region]' ? [kr, us] : [];
  const documentListeners = {};
  const visibleClasses = new Set();
  const document = {
    body: { classList: {
      contains(key) { return visibleClasses.has(key); },
      remove(...keys) { keys.forEach(key => visibleClasses.delete(key)); },
      toggle(key, force) {
        const active = force === undefined ? !visibleClasses.has(key) : !!force;
        if (active) visibleClasses.add(key); else visibleClasses.delete(key);
        return active;
      }
    } },
    getElementById(id) { return id === 'leftMarketSidebar' ? sidebar : null; },
    createElement(tagName) { return new Element(tagName); },
    addEventListener(name, fn) { documentListeners[name] = fn; }
  };
  const listeners = {};
  const window = {
    innerWidth: 1200,
    location: { hostname: 'gaemi-gtp.onrender.com', origin: 'https://gaemi-gtp.onrender.com' },
    addEventListener(name, fn) { (listeners[name] ||= []).push(fn); }
  };
  const calls = [];
  let resolveDeferred = null;
  const fetch = async (url, opts) => {
    calls.push({ url, opts });
    if (url.endsWith('/market/popular?market=kr')) {
      return { ok: true, json: async () => ({ ok: true, items: [
        { name: '삼성전자', symbol: '005930', issue_headline: '' }
      ] }) };
    }
    if (url.endsWith('/market/popular?market=us')) {
      return { ok: true, json: async () => ({ ok: true, items: [
        { name: '일라이 릴리', symbol: 'LLY', issue_headline: '' },
        { name: '테슬라', symbol: 'TSLA.O', issue_headline: '기존 이슈' }
      ] }) };
    }
    if (url.endsWith('/market/issue-headlines')) {
      const request = JSON.parse(opts.body);
      assert.equal(request.market, 'us');
      assert.ok(request.items.length >= 1);
      if (deferred && request.items.length === 1) {
        await new Promise((resolve) => { resolveDeferred = resolve; });
      }
      return { ok: true, json: async () => ({
        ok: postStatus !== 'error',
        items: request.items.map((item) => ({
          ...item, status: postStatus,
          headline: postStatus === 'ready' ? (item.name === '일라이 릴리' ? '사업 제휴 이슈' : '기존 이슈') : ''
        }))
      }) };
    }
    throw new Error('unexpected request: ' + url);
  };
  vm.runInNewContext(sidebarSource, { window, document, fetch, console, Date: { now: () => clock } });
  documentListeners.DOMContentLoaded();
  return {
    list, us, kr, calls,
    event(detail) { for (const handler of listeners['gaemi:analysis-issues-ready'] || []) handler({ detail }); },
    toggle() { window.GaemiGTPMarketSidebar.toggle(); },
    advance(ms) { clock += ms; },
    setPostStatus(status) { postStatus = status; },
    resolvePost() { assert.ok(resolveDeferred); resolveDeferred(); }
  };
}

test('newly stored Eli Lilly issue updates its sidebar row without fetching rankings again', async () => {
  const app = setup();
  await flush();
  app.us.click();
  await flush();
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
  app.us.click();
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
  app.us.click();
  await flush();
  app.event({ name: '일라이 릴리', market: 'us', symbol: 'LLY' });
  await flush();
  app.kr.click();
  await flush();
  app.resolvePost();
  await flush();
  assert.equal(app.list.querySelectorAll(':scope > button[data-original-index]')[0].dataset.stockName, '삼성전자');
});

test('completed central analysis permits sidebar invalidation even with no issue briefs', () => {
  assert.ok(!analysisSource.includes('if (Array.isArray(result.issue_briefs) && result.issue_briefs.length > 0)'));
  assert.ok(analysisSource.includes('gaemi:analysis-issues-ready'));
  assert.ok(analysisSource.includes('session.marketSelection?.symbol'));
});

test('confirmed no-issue clears the old title, Neon error preserves it', async () => {
  const app = setup();
  await flush();
  app.us.click();
  await flush();
  app.event({ name: '일라이 릴리', market: 'us', symbol: 'LLY' });
  await flush();
  const issue = app.list.querySelectorAll(':scope > button[data-original-index]')[0].querySelector('[data-stock-issue]');
  assert.equal(issue.textContent, '사업 제휴 이슈');
  app.setPostStatus('error');
  app.event({ name: '일라이 릴리', market: 'us', symbol: 'LLY' });
  await flush();
  assert.equal(issue.textContent, '사업 제휴 이슈');
  app.setPostStatus('unavailable');
  app.event({ name: '일라이 릴리', market: 'us', symbol: 'LLY' });
  await flush();
  assert.equal(issue.textContent, '');
});

test('sidebar reopen is throttled and rechecks every visible stock in one call', async () => {
  const app = setup();
  await flush();
  app.us.click();
  await flush();
  const oldCount = app.calls.length;
  app.toggle();
  await flush();
  assert.equal(app.calls.length, oldCount);
  app.toggle();
  app.advance(60001);
  app.toggle();
  await flush();
  assert.equal(app.calls.length, oldCount + 1);
  assert.ok(app.calls.at(-1).url.endsWith('/market/issue-headlines'));
  const items = JSON.parse(app.calls.at(-1).opts.body).items;
  assert.equal(items.length, 2);
  app.toggle();
  app.toggle();
  await flush();
  assert.equal(app.calls.length, oldCount + 1);
});

test('fast repeated tab switches reuse bounded ranking cache', async () => {
  const app = setup();
  await flush();
  app.us.click();
  await flush();
  const count = app.calls.length;
  app.kr.click();
  await flush();
  app.us.click();
  await flush();
  assert.equal(app.calls.length, count);
  app.advance(15001);
  app.us.click();
  await flush();
  assert.equal(app.calls.length, count + 1);
});
