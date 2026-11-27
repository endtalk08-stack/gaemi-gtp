import test from 'node:test';
import assert from 'node:assert/strict';
import { onRequestPost } from '../functions/internal/us-daily-chart-snapshot.js';

const token = 'test-token-that-is-at-least-32-characters-long';
const snapshot = {
  symbol: 'NVDA', interval: 'daily', source: 'kiwoom:usa06012', count: 2,
  candles: [
    { date: '2026-11-26', open: 180, high: 185, low: 179, close: 184, volume: 1000 },
    { date: '2026-11-27', open: 184, high: 188, low: 182, close: 187, volume: 1200 }
  ]
};
function request(body, auth = 'Bearer ' + token) {
  return new Request('https://gaemigtp-main.pages.dev/internal/us-daily-chart-snapshot', {
    method: 'POST', headers: { Authorization: auth, 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
}
function env() {
  const writes = [];
  return {
    writes,
    CHART_SYNC_TOKEN: token,
    DATA_R2: { put: async (...args) => writes.push(args) }
  };
}

test('rejects unauthenticated chart snapshot writes', async () => {
  const response = await onRequestPost({ request: request(snapshot, 'Bearer wrong-token'), env: env() });
  assert.equal(response.status, 401);
  assert.equal((await response.json()).error, 'unauthorized');
});

test('rejects malformed and unordered daily candles', async () => {
  const broken = { ...snapshot, candles: [...snapshot.candles].reverse(), count: 2 };
  const response = await onRequestPost({ request: request(broken), env: env() });
  assert.equal(response.status, 400);
  assert.equal((await response.json()).error, 'invalid_candles');
});

test('writes a valid verified daily snapshot to the existing R2 binding', async () => {
  const binding = env();
  const response = await onRequestPost({ request: request(snapshot), env: binding });
  const body = await response.json();
  assert.equal(response.status, 200);
  assert.deepEqual({ ok: body.ok, symbol: body.symbol, interval: body.interval, count: body.count },
    { ok: true, symbol: 'NVDA', interval: 'daily', count: 2 });
  assert.equal(binding.writes.length, 1);
  assert.equal(binding.writes[0][0], 'charts/us/NVDA/daily.json');
  assert.equal(binding.writes[0][2].httpMetadata.contentType, 'application/json; charset=utf-8');
  const saved = JSON.parse(binding.writes[0][1]);
  assert.equal(saved.source, 'kiwoom:usa06012');
  assert.equal(saved.count, 2);
  assert.equal(saved.candles[1].date, '2026-11-27');
});
