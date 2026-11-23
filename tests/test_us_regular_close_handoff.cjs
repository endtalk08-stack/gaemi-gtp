const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(__dirname + '/../frontend/shell/us-regular-close-hold.js', 'utf8');
const storage = new Map();
let now = Date.parse('2026-11-23T20:58:00Z'); // Mon 15:58 ET, 05:58 KST
function load() {
  const window = {};
  const Clock = class extends Date { static now() { return now; } };
  const context = { window, Date: Clock, Intl, JSON, Number, Object, String,
    localStorage: {
      getItem: key => storage.get(key) || null,
      setItem: (key, value) => storage.set(key, value),
    }
  };
  vm.runInNewContext(source, context);
  return window.GaemiGTPRegularCloseHold;
}
let hold = load();
const quote = (symbol, price, change_pct, received_at_ms = now, stale = false) => ({
  symbol, price, change_pct, received_at_ms, stale, source: 'kiwoom:websocket'
});
for (const [symbol, price, pct] of [
  ['QQQ', 650.2, 3.2], ['SPY', 725.2, 2.4], ['DIA', 497.9, 1.6],
  ['NVDA', 165.06, 30.93], ['XLK', 300.01, 9.87]
]) assert.equal(hold.remember(quote(symbol, price, pct)), true);
assert.equal(hold.held('QQQ'), null, 'no close freeze during normal session');
// after-close missing rates and new-session near-zero values may not overwrite
now = Date.parse('2026-11-23T21:04:00Z');
assert.equal(hold.held('QQQ').change_pct, 3.2);
assert.equal(hold.held('NVDA').change_pct, 30.93);
assert.equal(hold.rate('XLK', null), 9.87);
const resolved = hold.resolve('SPY', quote('SPY', 728.5, 0.05));
assert.equal(resolved.price, 725.2);
assert.equal(resolved.change_pct, 2.4);
assert.equal(resolved.market_session, 'last_regular_tick');
assert.equal(hold.remember(quote('QQQ', 651.2, 0.03)), false);
now = Date.parse('2026-11-23T21:29:59Z');
assert.equal(hold.held('DIA').price, 497.9);
// survive a browser refresh in the same profile; no DB or external calls
hold = load();
assert.equal(hold.held('QQQ').price, 650.2);
assert.equal(hold.held('XLK').change_pct, 9.87);
now = Date.parse('2026-11-23T21:30:00Z');
assert.equal(hold.held('QQQ'), null, 'new-session quotes may resume at 16:30 ET');
assert.equal(hold.rate('QQQ', 0.03), 0.03);
// a later session must never inherit the previous date
now = Date.parse('2026-11-24T21:10:00Z');
assert.equal(hold.held('QQQ'), null);
assert.equal(hold.remember(quote('QQQ', 99.9, 1.2)), false);
now = Date.parse('2026-11-23T20:58:00Z');
assert.equal(hold.remember(quote('QQQ', 100, null)), false);
assert.equal(hold.remember(quote('QQQ', 100, 10, now, true)), false);
assert.equal(hold.remember(quote('QQQ', 100, 10, now-2*60*1000)), false);
console.log('PASS: US 16:00-16:30 ET regular-session snapshots retained, reload-safe and day-scoped');
