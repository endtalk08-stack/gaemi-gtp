const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { JSDOM } = require('jsdom');

test('widgets retain identity, live quotes and caption after panel moves', () => {
  const dom = new JSDOM('<div id="leftMarketSidebar"></div><div id="rightPanel"></div><section id="centralWidgetDock"><div id="centralWidgetDockBody"></div></section>', { url: 'https://example.test', runScripts: 'outside-only' });
  const w = dom.window;
  w.setInterval = () => 0;
  w.fetch = async () => ({ ok: false });
  w.eval(readFileSync('frontend/widgets/catalog/catalog.js', 'utf8'));
  w.eval(readFileSync('frontend/shell/center-chat/widget-dock/widget-dock.js', 'utf8'));
  const dock = w.GaemiGTPWidgetDock;
  dock.initialize();
  dock.add('qqq');
  const card = w.document.querySelector('[data-central-widget-id="qqq"]');
  for (const place of ['right', 'left', 'center']) {
    assert.equal(dock.move('qqq', place), true);
    assert.equal(card.parentElement, place === 'center' ? w.document.getElementById('centralWidgetDockBody') : w.document.querySelector(`[data-portable-widget-slot="${place}"]`));
  }
  dock.move('qqq', 'right');
  dock.add('spy');
  assert.equal(w.document.querySelector('[data-central-widget-id="qqq"]'), card);
  w.dispatchEvent(new w.CustomEvent('gaemi:qqq-quote', { detail: { quote: { symbol: 'QQQ', price: 600, change_pct: 2, received_at_ms: Date.now(), stale: false } } }));
  assert.equal(card.querySelector('[data-kospi-price]').textContent, '600.00');
  dock.add('news-caption');
  dock.move('news-caption', 'left');
  dock.setNewsHeadline('테스트 속보');
  assert.equal(w.document.querySelector('[data-news-caption-title]').textContent, '테스트 속보');
  Object.defineProperty(w, 'innerWidth', { value: 390 });
  w.document.body.classList.add('left-plugin-open');
  dock.move('spy', 'left');
  assert.equal(w.document.body.classList.contains('right-panel-open'), false);
  assert.equal(w.document.body.classList.contains('left-plugin-open'), false);
  dock.remove('qqq');
  assert.equal(card.isConnected, false);
  assert.equal(dock.move('qqq', 'right'), false);
  dom.window.close();
});
