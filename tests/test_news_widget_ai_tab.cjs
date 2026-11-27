// The news widget "분석" tab shows the daily US TOP20 AI analysis.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('jsdom');

const read = file => fs.readFileSync(path.join(__dirname, '..', file), 'utf8');
const snapshot = { ok: true, exchange_day: '2026-11-27', generated_at: '2026-11-27T15:30:05Z', items: [
  { status: 'ok', symbol: 'MU', name: '마이크론 테크놀로지', change_pct: 6.26, generated_at: '2026-11-27T15:30:05Z',
    headline_keyword: '장기 공급계약 확대', keywords: ['중국 HBM 경쟁', '장기 공급계약 확대', 'AI 메모리 수요'],
    lines: ['원인 문장이에요.', '흐름 문장이에요.', '기업 소개 문장이에요.'],
    sources: [{ title: '근거 기사', source: 'jemin.com', published_at: '2026-11-26T22:00:00Z', url: 'https://www.jemin.com/' }] },
  { status: 'no_news', symbol: 'SNDK', name: '샌디스크', change_pct: 10.2 },
  { status: 'ok', symbol: 'TSLA', name: '테슬라', change_pct: -1.18,
    headline_keyword: '로보택시 일정 지연', keywords: ['로보택시 일정 지연', '유럽 판매 둔화', '자율주행 규제'],
    lines: ['하락 원인이에요.', '흐름이에요.', '회사 소개예요.'], sources: [] },
] };

async function widget() {
  const dom = new JSDOM('<div data-central-widget-id="news-feed"><section data-gnw-root></section></div>',
    { url: 'https://example.test', runScripts: 'outside-only' });
  const w = dom.window;
  const requested = [];
  w.fetch = async (url) => { requested.push(url); return { ok: true, json: async () => snapshot }; };
  w.eval(read('frontend/widgets/news/us-news-ai.js'));
  w.eval(read('frontend/widgets/news/news-widget.js'));
  w.GaemiGTPNewsWidget.mount();
  return { w, requested, root: w.document.querySelector('[data-gnw-root]') };
}
const settle = () => new Promise(resolve => setTimeout(resolve, 20));

test('분석 tab lists each stock as keyword + Kiwoom move, with the first line', async () => {
  const { w, requested, root } = await widget();
  const tabs = [...root.querySelectorAll('[data-gnw-cat]')].map(b => b.textContent);
  assert.deepEqual(tabs.slice(0, 2), ['전체', '분석']);
  root.querySelector('[data-gnw-cat="분석"]').click();
  await settle();
  assert.deepEqual(requested, ['/news/ai/us/top20']);
  const rows = [...root.querySelectorAll('.gnw-ai-item')].map(r => r.textContent.replace(/\s+/g, ' ').trim());
  assert.equal(rows.length, 3);
  assert.match(rows[0], /마이크론 테크놀로지 장기 공급계약 확대로 6\.26% 상승 원인 문장이에요\./);
  assert.match(rows[1], /샌디스크 10\.20% 상승 관련 뉴스가 확인되지 않았어요\./);
  assert.match(rows[2], /테슬라 로보택시 일정 지연으로 1\.18% 하락/);
  assert.ok(root.querySelector('[data-gnw-open="ai:TSLA"] .gnw-ai-down'));
});

test('opening a stock shows 3 lines, 3 keywords and the source articles', async () => {
  const { root } = await widget();
  root.querySelector('[data-gnw-cat="분석"]').click();
  await settle();
  root.querySelector('[data-gnw-open="ai:MU"]').click();
  assert.equal(root.querySelector('.gnw-ai-eyebrow').textContent, '장기 공급계약 확대로');
  assert.equal(root.querySelector('.gnw-detail-section h4').textContent, '왜 올랐을까');
  assert.deepEqual([...root.querySelectorAll('.gnw-ai-lines li')].map(li => li.textContent),
    ['원인 문장이에요.', '흐름 문장이에요.', '기업 소개 문장이에요.']);
  assert.deepEqual([...root.querySelectorAll('.gnw-chip')].map(c => c.textContent),
    ['#중국 HBM 경쟁', '#장기 공급계약 확대', '#AI 메모리 수요']);
  assert.equal(root.querySelector('.gnw-ai-source').getAttribute('href'), 'https://www.jemin.com/');
  root.querySelector('[data-gnw-back]').click();
  assert.equal(root.querySelectorAll('.gnw-ai-item').length, 3);
});

test('a falling stock asks 왜 떨어졌을까', async () => {
  const { root } = await widget();
  root.querySelector('[data-gnw-cat="분석"]').click();
  await settle();
  root.querySelector('[data-gnw-open="ai:TSLA"]').click();
  assert.equal(root.querySelector('.gnw-detail-section h4').textContent, '왜 떨어졌을까');
});
