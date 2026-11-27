// The news widget "분석" tab shows 개미지티피 articles on the US TOP20 in the
// same list and detail views as every other news item.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('jsdom');

const read = file => fs.readFileSync(path.join(__dirname, '..', file), 'utf8');
const snapshot = { ok: true, exchange_day: '2026-11-27', generated_at: '2026-11-27T15:30:05Z', items: [
  { status: 'ok', type: 'reason', symbol: 'MU', name: '마이크론 테크놀로지', change_pct: 6.26,
    generated_at: '2026-11-27T15:30:05Z', industry: '반도체',
    headline: '마이크론, AI 메모리 장기 공급계약 확대', headline_keyword: '장기 공급계약 확대',
    keywords: ['중국 HBM 경쟁', '장기 공급계약 확대', 'AI 메모리 수요'],
    lines: ['원인 문장이에요.', '흐름 문장이에요.', '기업 소개 문장이에요.'] },
  { status: 'no_news', symbol: 'SNDK', name: '샌디스크', change_pct: 10.2 },
  { status: 'ok', type: 'news', symbol: 'AAPL', name: '애플', change_pct: 0.8,
    generated_at: '2026-11-27T15:35:05Z',
    headline_keyword: 'AI 광고 심의', headline: '애플, 아이폰16 AI 기능 광고 심의 착수',
    keywords: ['AI 광고 심의', '애플 인텔리전스', '공정위 조사'],
    lines: ['심의한다는 소식이 있어요.', '배경이에요.', '애플은 기술 기업이에요.'] },
  { status: 'ok', type: 'reason', symbol: 'TSLA', name: '테슬라', change_pct: -1.18,
    headline_keyword: '로보택시 일정 지연',   // earlier run without a headline
    keywords: ['로보택시 일정 지연', '유럽 판매 둔화', '자율주행 규제'],
    lines: ['하락 원인이에요.', '흐름이에요.', '회사 소개예요.'] },
] };
const intros = { ok: true, items: { MU: '마이크론은 메모리 반도체를 만드는 회사예요.',
  NVDA: '엔비디아는 AI 서버용 GPU를 만드는 회사예요.' } };

async function widget(t) {
  const dom = new JSDOM('<div data-central-widget-id="news-feed"><section data-gnw-root></section></div>',
    { url: 'https://example.test', runScripts: 'outside-only' });
  const w = dom.window;
  const requested = [];
  w.fetch = async (url) => { requested.push(url);
    return { ok: true, json: async () => (url === '/news/ai/us/profiles' ? intros : snapshot) }; };
  w.eval(read('frontend/widgets/news/us-news-ai.js'));
  w.eval(read('frontend/widgets/news/news-widget.js'));
  w.GaemiGTPNewsWidget.mount();
  t.after(() => w.close());   // stop the widget's refresh timer
  const root = w.document.querySelector('[data-gnw-root]');
  root.querySelector('[data-gnw-cat="분석"]').click();
  await new Promise(resolve => setTimeout(resolve, 20));
  return { w, requested, root };
}

test('분석 tab sits after 전체 and lists only published articles with their full body', async (t) => {
  const { requested, root } = await widget(t);
  const tabs = [...root.querySelectorAll('[data-gnw-cat]')].map(b => b.textContent);
  assert.deepEqual(tabs.slice(0, 2), ['전체', '분석']);
  assert.deepEqual([...new Set(requested)].sort(), ['/news/ai/us/profiles', '/news/ai/us/top20']);
  const rows = [...root.querySelectorAll('.gnw-ai-item')];
  assert.equal(rows.length, 3);                                   // no_news is not an article
  assert.equal(rows[0].querySelector('.gnw-title').textContent, '마이크론, AI 메모리 장기 공급계약 확대');
  // The company intro is not in the list; it sits under 관련 종목 in the detail view.
  assert.equal(rows[0].querySelector('.gnw-summary').textContent, '원인 문장이에요.\n흐름 문장이에요.');
  assert.equal(rows[1].querySelector('.gnw-title').textContent, '애플, 아이폰16 AI 기능 광고 심의 착수');
  assert.equal(rows[2].querySelector('.gnw-title').textContent, '테슬라 로보택시 일정 지연');
  assert.ok(!rows.some(r => /%/.test(r.querySelector('.gnw-title').textContent)));   // no change rate
});

test('opening an article uses the existing news detail view', async (t) => {
  const { root } = await widget(t);
  root.querySelector('[data-gnw-open="ai:MU"]').click();
  assert.equal(root.querySelector('.gnw-detail-title').textContent, '마이크론, AI 메모리 장기 공급계약 확대');
  assert.equal(root.querySelector('.gnw-detail-source').textContent, '개미지티피');
  assert.deepEqual([...root.querySelectorAll('.gnw-article-body p')].map(p => p.textContent),
    ['원인 문장이에요.', '흐름 문장이에요.']);
  const sections = [...root.querySelectorAll('.gnw-detail-section h4')].map(h => h.textContent);
  assert.deepEqual(sections, ['관련 이슈', '관련 종목', '관련 산업·테마']);
  assert.deepEqual([...root.querySelectorAll('.gnw-chip')].map(c => c.textContent),
    ['#중국 HBM 경쟁', '#장기 공급계약 확대', '#AI 메모리 수요', '반도체']);
  assert.equal(root.querySelector('.gnw-stock-name').textContent, '$MU');
  assert.equal(root.querySelector('.gnw-stock-intro').textContent, '마이크론은 메모리 반도체를 만드는 회사예요.');
  assert.equal(root.querySelector('.gnw-source-link'), null);        // own article: no source link
  assert.ok(!root.textContent.includes('왜 올랐을까'));
  root.querySelector('[data-gnw-back]').click();
  assert.equal(root.querySelectorAll('.gnw-ai-item').length, 3);
});

test('an empty analysis list is left blank', async (t) => {
  const dom = new JSDOM('<div data-central-widget-id="news-feed"><section data-gnw-root></section></div>',
    { url: 'https://example.test', runScripts: 'outside-only' });
  const w = dom.window;
  t.after(() => w.close());
  w.fetch = async () => ({ ok: true, json: async () => ({ ok: true, items: [
    { status: 'no_news', symbol: 'SNDK', name: '샌디스크' }] }) });
  w.eval(read('frontend/widgets/news/us-news-ai.js'));
  w.eval(read('frontend/widgets/news/news-widget.js'));
  w.GaemiGTPNewsWidget.mount();
  const root = w.document.querySelector('[data-gnw-root]');
  root.querySelector('[data-gnw-cat="분석"]').click();
  await new Promise(resolve => setTimeout(resolve, 20));
  assert.equal(root.querySelector('.gnw-list').textContent.trim(), '');
  assert.ok(!root.textContent.includes('뉴스'), 'no "뉴스 없음" style message');
});

test('전체 shows 개미지티피 articles and no design-file sample news', async (t) => {
  const { root } = await widget(t);
  root.querySelector('[data-gnw-cat="전체"]').click();
  await new Promise(resolve => setTimeout(resolve, 20));
  const titles = [...root.querySelectorAll('.gnw-item .gnw-title')].map(n => n.textContent);
  assert.deepEqual(titles, ['애플, 아이폰16 AI 기능 광고 심의 착수', '마이크론, AI 메모리 장기 공급계약 확대',
                            '테슬라 로보택시 일정 지연']);               // newest first; undated last
  assert.ok(!root.textContent.includes('연준 의장 긴급 기자회견'));
  assert.ok(!read('frontend/widgets/news/news-widget.js').includes('SOURCE_PREVIEW_ITEMS'));
});

test('company intro: saved sentence first, the article own third line otherwise, any news item', async (t) => {
  const { w, root } = await widget(t);
  root.querySelector('[data-gnw-open="ai:AAPL"]').click();          // not in the intro file yet
  assert.equal(root.querySelector('.gnw-stock-intro').textContent, '애플은 기술 기업이에요.');
  w.GaemiGTPNewsWidget.setItems([{ id: 'n1', title: '엔비디아 신제품 발표', category: '종목',
    published_at: '2026-11-27T10:00:00Z', tickers: ['$NVDA', '$ZZZZ'] }]);
  root.querySelector('[data-gnw-open="n1"]').click();
  const intro = [...root.querySelectorAll('.gnw-stock-entry')].map(e => e.querySelector('.gnw-stock-intro')?.textContent || '');
  assert.deepEqual(intro, ['엔비디아는 AI 서버용 GPU를 만드는 회사예요.', '']);   // unknown ticker: blank
});
