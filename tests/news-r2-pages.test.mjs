import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

async function handler(kind) {
  const source = readFileSync(
    new URL('../functions/news/' + kind + '/us/[symbol].js', import.meta.url),
    'utf8'
  );
  const module = await import('data:text/javascript,' + encodeURIComponent(source));
  return module.onRequestGet;
}

for (const kind of ['stocks', 'ai']) {
  test(kind + ' R2 Pages response reads only its own object', async () => {
    const calls = [];
    const get = async key => {
      calls.push(key);
      return { body: JSON.stringify({ ok: true, symbol: 'NVDA' }), httpEtag: '"etag-test"' };
    };
    const route = await handler(kind);
    const response = await route({
      request: new Request('https://example.org/news/' + kind + '/us/NVDA'),
      env: { NEWS_R2: { get } },
      params: { symbol: 'NVDA' },
    });
    assert.equal(response.status, 200);
    assert.deepEqual(calls, ['news/' + kind + '/us/NVDA.json']);
    assert.equal((await response.json()).symbol, 'NVDA');
    assert.equal(response.headers.get('Cache-Control'), 'public, max-age=60, stale-while-revalidate=60');
  });

  test(kind + ' rejects invalid symbols without reading R2', async () => {
    const route = await handler(kind);
    const response = await route({
      request: new Request('https://example.org/'),
      env: { NEWS_R2: { get: () => { throw Error('should not fetch'); } } },
      params: { symbol: '../latest.json' },
    });
    assert.equal(response.status, 400);
  });

  test(kind + ' returns 503 if NEWS_R2 binding is absent', async () => {
    const route = await handler(kind);
    const response = await route({
      request: new Request('https://example.org/'),
      env: {}, params: { symbol: 'NVDA' },
    });
    assert.equal(response.status, 503);
  });

  test(kind + ' returns 404 for absent object and 304 for matching ETag', async () => {
    const route = await handler(kind);
    const url = 'https://example.org/news/' + kind + '/us/NVDA';
    let response = await route({
      request: new Request(url),
      env: { NEWS_R2: { get: async () => null } },
      params: { symbol: 'NVDA' },
    });
    assert.equal(response.status, 404);
    response = await route({
      request: new Request(url, { headers: { 'If-None-Match': '"etag"' } }),
      env: { NEWS_R2: { get: async () => ({ body: '{}', httpEtag: '"etag"' }) } },
      params: { symbol: 'NVDA' },
    });
    assert.equal(response.status, 304);
  });
}
