// Pages Function /news/ai/us/top20 serves only well-formed analysis rows.
import test from 'node:test';
import assert from 'node:assert/strict';
import { onRequestGet } from '../functions/news/ai/us/top20.js';

const env = data => ({ DATA_R2: { get: async key => {
  assert.equal(key, 'news/ai/us/TOP20.json');
  return data === null ? null : { json: async () => data };
} } });

test('keeps valid rows and drops broken ones', async () => {
  const response = await onRequestGet({ env: env({ ok: true, exchange_day: '2026-11-27', generated_at: 'x', items: [
    { status: 'ok', symbol: 'MU', name: '마이크론', change_pct: 6.2, headline_keyword: 'A 키워드',
      keywords: ['A 키워드', 'B 키워드', 'C 키워드'], lines: ['1', '2', '3'],
      sources: [{ title: 't', url: 'javascript:alert(1)' }, { title: 'ok', url: 'https://a.example/' }] },
    { status: 'ok', symbol: 'BAD', keywords: ['only one'], lines: ['1'] },
    { status: 'failed', symbol: 'X' },
    { status: 'no_news', symbol: 'SNDK', name: '샌디스크', change_pct: 10.2 },
  ] }) });
  const body = await response.json();
  assert.deepEqual(body.items.map(i => i.symbol), ['MU', 'SNDK']);
  assert.deepEqual(body.items[0].sources.map(s => s.url), ['https://a.example/']);
});

test('before the first run it returns an empty list, not an error', async () => {
  const body = await (await onRequestGet({ env: env(null) })).json();
  assert.deepEqual(body, { ok: true, exchange_day: null, generated_at: null, items: [] });
});
