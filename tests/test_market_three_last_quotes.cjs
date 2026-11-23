const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const listeners = {};
const cards = {};
let now = Date.parse('2026-11-23T21:00:00Z');
const htmlNode = () => ({
  textContent: '',
  hidden: false,
  classList: { toggle() {}, add() {}, remove() {} },
  setAttribute() {},
  removeAttribute() {},
});
for (const symbol of ['qqq', 'spy', 'dia']) {
  const elements = Object.fromEntries([
    '[data-kospi-price]', '[data-kospi-change]', '.central-widget-card__sparkline',
    '[data-kospi-sparkline]', '[data-kospi-sparkline-fill]', '[data-qqq-reason]',
  ].map(key => [key, htmlNode()]));
  cards[symbol] = { elements, card: {
    classList: { toggle() {} },
    querySelector(selector) { return elements[selector] || null; },
  } };
}
const dock = {dataset: {bound: 'false'}, addEventListener() {}};
const dockBody = {
  innerHTML: '',
  querySelector(selector) {
    const match = selector.match(/data-central-widget-id="(qqq|spy|dia)"/);
    return match ? cards[match[1]].card : null;
  },
};
const document = {
  hidden: false,
  getElementById(id) {
    return id === 'centralWidgetDock' ? dock : id === 'centralWidgetDockBody' ? dockBody : null;
  },
  addEventListener(event, fn) { listeners[event] = fn; },
  querySelector() { return null; },
  querySelectorAll() { return []; },
};
const window = {
  GaemiGTPWidgetCatalog: {qqq: {title: 'QQQ'}, spy: {title: 'SPY'}, dia: {title: 'DIA'}},
  addEventListener(event, fn) { listeners[event] = fn; },
  dispatchEvent() {},
};
class Clock extends Date { static now() { return now; } }
const ctx = {
  window, document, Date: Clock, console, Intl,
  localStorage: {getItem: () => JSON.stringify(['qqq', 'spy', 'dia']), setItem() {}},
  CustomEvent: class {constructor(type, o) {this.type = type; this.detail = o.detail;}},
  setInterval() {}, clearTimeout() {},
  fetch: async () => ({ok: false}),
};
vm.runInNewContext(fs.readFileSync(__dirname + '/../frontend/shell/center-chat/widget-dock/widget-dock.js', 'utf8'), ctx);
listeners.DOMContentLoaded();

const quote = (symbol, price, change_pct, received_at_ms = now, stale = false) => ({
  symbol, price, change_pct, received_at_ms, stale, source: 'kiwoom:websocket',
});
const receiveQQQ = quote => listeners['gaemi:qqq-quote']({detail: {quote}});
const receiveEtfs = items => listeners['gaemi:market-etf-quotes']({detail: {items}});
const display = symbol => ({
  price: cards[symbol].elements['[data-kospi-price]'].textContent,
  change: cards[symbol].elements['[data-kospi-change]'].textContent,
});

receiveQQQ(quote('QQQ', 650.12, 2.77));
receiveEtfs([quote('SPY', 724.19, 1.62), quote('DIA', 496.30, -0.85)]);
assert.deepEqual(display('qqq'), {price: '650.12', change: '+2.77%'});
assert.deepEqual(display('spy'), {price: '724.19', change: '+1.62%'});
assert.deepEqual(display('dia'), {price: '496.30', change: '-0.85%'});

// At close, the server may emit no fresh tick or an incomplete price-only FE packet.
now += 30 * 60 * 1000;
receiveQQQ(null);
receiveEtfs([]);
for (const symbol of ['qqq', 'spy', 'dia']) {
  assert.notEqual(display(symbol).price, '—', symbol + ' must keep last verified price');
  assert.notEqual(display(symbol).change, '—', symbol + ' must keep last verified percent');
}
receiveQQQ(quote('QQQ', 657.99, null));
receiveEtfs([quote('SPY', 729.99, null), quote('DIA', 499.50, null)]);
assert.deepEqual(display('qqq'), {price: '650.12', change: '+2.77%'}, 'QQQ price/rate pair stays together');
assert.deepEqual(display('spy'), {price: '724.19', change: '+1.62%'}, 'SPY price/rate pair stays together');
assert.deepEqual(display('dia'), {price: '496.30', change: '-0.85%'}, 'DIA price/rate pair stays together');

// New verified session quotes replace the last good pair.
now += 10 * 60 * 1000;
receiveQQQ(quote('QQQ', 660.21, -0.25));
receiveEtfs([quote('SPY', 720.10, -1.52), quote('DIA', 501.11, 0.52)]);
assert.deepEqual(display('qqq'), {price: '660.21', change: '-0.25%'});
assert.deepEqual(display('spy'), {price: '720.10', change: '-1.52%'});
assert.deepEqual(display('dia'), {price: '501.11', change: '+0.52%'});

// Do not display old values indefinitely; after 72 hours without verification, expire.
now += 72 * 60 * 60 * 1000 + 1000;
receiveQQQ(null);
receiveEtfs([]);
for (const symbol of ['qqq', 'spy', 'dia']) {
  assert.equal(display(symbol).price, '—', symbol + ' must expire unverified data');
  assert.equal(display(symbol).change, '—', symbol + ' must expire stale percentage');
}
console.log('PASS: only QQQ, SPY, DIA retain complete verified pairs after close, expire after 72h');
