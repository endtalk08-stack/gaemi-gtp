// A stock name typed in chat must take the same path as a sidebar click.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('jsdom');

const source = fs.readFileSync(
  path.join(__dirname, '..', 'frontend/shell/center-chat/search-controls.js'), 'utf8');
const items = [
  { rank: 1, symbol: 'NVDA', name: '엔비디아', exchange: 'ND', industry: '반도체', price: 150, change_pct: 1.0 },
  { rank: 2, symbol: 'GOOGL', name: '알파벳 A', exchange: 'ND', industry: '미디어', price: 279.06, change_pct: 2.18 },
  { rank: 3, symbol: 'GOOG', name: '알파벳 C', exchange: 'ND', industry: '미디어', price: 270, change_pct: 2.0 },
];

async function typeInChat(query) {
  const dom = new JSDOM('<body><button data-stock-symbol="NVDA" data-current-price="152.8" '
    + 'data-current-change-pct="2.36"></button></body>', { runScripts: 'outside-only' });
  const win = dom.window;
  const calls = [];
  const charts = [];
  win.fetch = async (url) => {
    assert.equal(url, 'https://quotes.gaemigtp.com/market/trading-value?market=us');
    return { ok: true, json: async () => ({ ok: true, items }) };
  };
  win.GaemiGTPApp = { requestStock: (name, selection) => calls.push({ name, selection }) };
  win.GaemiGTPWidgetDock = { setChartSelection: (symbol) => charts.push(symbol) };
  win.eval(source);
  win.GaemiGTPCenterChatSearch.selectStock(query, { enterAnalysis: true });
  await new Promise((resolve) => setTimeout(resolve, 20));
  return { calls, charts };
}

test('typed US names and tickers use the trading-value click selection', async () => {
  for (const [query, symbol, name] of [
    ['엔비디아', 'NVDA', '엔비디아'], ['nvda', 'NVDA', '엔비디아'],
    ['구글', 'GOOGL', '알파벳 A'], ['알파벳 c', 'GOOG', '알파벳 C'],
  ]) {
    const { calls, charts } = await typeInChat(query);
    assert.equal(calls.length, 1, query);
    assert.equal(calls[0].name, name, query);
    assert.equal(calls[0].selection.market, 'us');
    assert.equal(calls[0].selection.menu, 'value');
    assert.equal(calls[0].selection.symbol, symbol);
    assert.equal(calls[0].selection.name, name);
    assert.deepEqual(charts, [symbol]);
  }
});

test('the live sidebar row supplies price and change like a click', async () => {
  const { calls } = await typeInChat('엔비디아');
  assert.equal(calls[0].selection.price, 152.8);
  assert.equal(calls[0].selection.change_pct, 2.36);
  assert.equal(calls[0].selection.rank, 1);
});

test('without the sidebar open the TOP20 list supplies price and change', async () => {
  const { calls } = await typeInChat('구글');
  assert.equal(calls[0].selection.price, 279.06);
  assert.equal(calls[0].selection.change_pct, 2.18);
  assert.equal(calls[0].selection.rank, 2);
});

test('names outside the US snapshot keep the previous path', async () => {
  const { calls } = await typeInChat('삼성전자');
  assert.deepEqual(calls, [{ name: '삼성전자', selection: null }]);
});
