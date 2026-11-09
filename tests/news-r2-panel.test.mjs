import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFileSync } from 'node:fs';

const source = readFileSync(new URL('../frontend/js/analysis-api.js', import.meta.url), 'utf8');

async function run({ marketSelection = null, r2Base = '', newsResponse = null, r2Response = null }) {
  const requests = [];
  const window = { ENV: r2Base ? { NEWS_STOCKS_R2_BASE_URL: r2Base } : {} };
  const original = { ok: true, sections: [], paired_news_items: [{ title: '기존 뉴스', url: 'https://example.org/old' }] };
  const fetch = async (url) => {
    requests.push(String(url));
    if (requests.length === 1) return { ok: true, json: async () => newsResponse ?? original };
    return r2Response ?? { ok: false, status: 503 };
  };
  vm.runInNewContext(source, { window, fetch, BACKEND_URL: 'https://example.test', URLSearchParams });
  const result = await window.GaemiGTPAnalysisAPI.fetchAnalysisFromBackend(
    'NVIDIA', undefined, marketSelection
  );
  return { result, requests };
}

const us = { market: 'us', menu: 'value', symbol: 'NVDA' };
const kr = { market: 'kr', menu: 'value', symbol: '005930' };

test('legacy path remains unchanged when R2 is not configured', async () => {
  const { result, requests } = await run({ marketSelection: us });
  assert.equal(requests.length, 1);
  assert.equal(result.paired_news_items[0].title, '기존 뉴스');
  assert.equal(result.panel_news_items, undefined);
});

test('US opted-in R2 news uses existing panel_news_items contract', async () => {
  const { result, requests } = await run({
    marketSelection: us,
    r2Base: '/r2',
    r2Response: { ok: true, json: async () => ({
      ok: true, symbol: 'NVDA',
      items: [{ title: 'R2 기사', url: 'https://example.org/new', published_at: '2026-11-09T10:00:00Z' }],
    }) },
  });
  assert.equal(requests[1], '/r2/news/stocks/us/NVDA');
  assert.equal(result.panel_news_items[0].title, 'R2 기사');
  assert.equal(result.paired_news_items[0].title, '기존 뉴스');
});

test('R2 failures and empty payload preserve working legacy news', async () => {
  for (const response of [
    { ok: false, status: 404 },
    { ok: true, json: async () => ({ ok: true, symbol: 'NVDA', items: [] }) },
    { ok: true, json: async () => ({ ok: true, symbol: 'TSLA', items: [{ title: 'wrong symbol', url: 'https://example.org' }] }) },
  ]) {
    const { result } = await run({ marketSelection: us, r2Base: '', r2Response: response });
    assert.equal(result.panel_news_items, undefined);
    assert.equal(result.paired_news_items[0].title, '기존 뉴스');
  }
});

test('KR panel never issues an R2 request even if opt-in is set', async () => {
  const { result, requests } = await run({ marketSelection: kr, r2Base: '/r2' });
  assert.equal(requests.length, 1);
  assert.equal(result.panel_news_items, undefined);
});

test('untrusted symbols never produce R2 paths', async () => {
  const { requests } = await run({
    marketSelection: { market: 'us', menu: 'value', symbol: '../evil' },
    r2Base: '/r2',
  });
  assert.equal(requests.length, 1);
});
