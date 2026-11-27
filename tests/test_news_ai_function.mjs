// Pages Function /news/ai/us/top20 serves only well-formed articles, never their sources.
import test from 'node:test';
import assert from 'node:assert/strict';
import { onRequestGet } from '../functions/news/ai/us/top20.js';

const env = data => ({ DATA_R2: { get: async key => {
  assert.equal(key, 'news/ai/us/TOP20.json');
  return data === null ? null : { json: async () => data };
} } });

test('keeps valid articles, drops broken ones and never exposes sources', async () => {
  const response = await onRequestGet({ env: env({ ok: true, exchange_day: '2026-11-27', generated_at: 'x',
    complete: false, items: [
    { status: 'ok', type: 'reason', symbol: 'MU', name: '마이크론', change_pct: 6.2, industry: '반도체',
      headline_keyword: 'A 키워드', keywords: ['A 키워드', 'B 키워드', 'C 키워드'], lines: ['1', '2', '3'],
      sources: [{ title: 'ok', url: 'https://a.example/' }] },
    { status: 'ok', type: 'news', symbol: 'AAPL', headline_keyword: 'A', headline: '',
      keywords: ['A', 'B', 'C'], lines: ['1', '2', '3'] },
    { status: 'ok', symbol: 'BAD', keywords: ['only one'], lines: ['1'] },
    { status: 'failed', symbol: 'X' },
    { status: 'no_news', symbol: 'SNDK', name: '샌디스크', change_pct: 10.2 },
  ] }) });
  const body = await response.json();
  assert.equal(body.complete, false);
  assert.deepEqual(body.items.map(i => i.symbol), ['MU', 'SNDK']);
  assert.equal(body.items[0].type, 'reason');
  assert.equal(body.items[0].headline, '');
  assert.equal(body.items[0].industry, '반도체');
  assert.equal('sources' in body.items[0], false);
});

test('before the first run it returns an empty list, not an error', async () => {
  const body = await (await onRequestGet({ env: env(null) })).json();
  assert.deepEqual(body, { ok: true, exchange_day: null, generated_at: null, items: [] });
});

test('company intros: only well-formed sentences, source label never exposed', async () => {
  const { onRequestGet: profiles } = await import('../functions/news/ai/us/profiles.js');
  const env = data => ({ DATA_R2: { get: async key => {
    assert.equal(key, 'news/ai/us/PROFILES.json');
    return data === null ? null : { json: async () => data };
  } } });
  const body = await (await profiles({ env: env({ ok: true, items: {
    NVDA: { intro: '엔비디아는 AI 서버용 GPU를 만드는 회사예요.', source: 'manual' },
    'bad sym': { intro: '잘못된 티커예요.' },
    TSLA: { intro: '짧' },
  } }) })).json();
  assert.deepEqual(body, { ok: true, items: { NVDA: '엔비디아는 AI 서버용 GPU를 만드는 회사예요.' } });
  assert.deepEqual(await (await profiles({ env: env(null) })).json(), { ok: true, items: {} });
});

test('macro headlines: keeps translated https items only and fixes the category', async () => {
  const { onRequestGet: macro } = await import('../functions/news/macro/us.js');
  const env = data => ({ DATA_R2: { get: async key => {
    assert.equal(key, 'news/macro/us/feed.json');
    return data === null ? null : { json: async () => data };
  } } });
  const body = await (await macro({ env: env({ ok: true, generated_at: 'g', items: [
    { id: '0123456789abcdef', title: '연준, FOMC 성명 발표', title_en: 'FOMC statement', source: '연준',
      category: '연준·금리', url: 'https://www.federalreserve.gov/x', published_at: '2026-11-27T19:00:00Z' },
    { id: '1123456789abcdef', title: '', url: 'https://a.example', published_at: '2026-11-27T19:00:00Z' },
    { id: '2123456789abcdef', title: '링크 없음', url: 'javascript:alert(1)', published_at: '2026-11-27T19:00:00Z' },
    { id: '3123456789abcdef', title: '분류 이상', url: 'https://b.example', published_at: '2026-11-27T19:00:00Z',
      category: '<b>' },
  ] }) })).json();
  assert.deepEqual(body.items.map(i => [i.id, i.category]),
    [['macro:0123456789abcdef', '연준·금리'], ['macro:3123456789abcdef', '정책·규제']]);
  assert.deepEqual(await (await macro({ env: env(null) })).json(), { ok: true, generated_at: null, items: [] });
});
