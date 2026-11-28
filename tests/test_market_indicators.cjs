const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { JSDOM } = require('jsdom');

test('Dollar Index and WTI use the BiQuote live quote feed and existing movable widget cards', async () => {
  const dom = new JSDOM(
    '<main id="mainContent"><section id="centralWidgetDock"><div id="centralWidgetDockBody"></div></section></main>' +
    '<aside id="leftMarketSidebar"><div class="flex-1 overflow-y-auto"></div></aside>' +
    '<aside id="rightPanel"><div id="rightPanelContent"></div></aside>',
    { url: 'https://example.test', runScripts: 'outside-only' }
  );
  const w = dom.window;
  w.setInterval = () => 0;
  Object.defineProperty(w.document, 'hidden', { value: false });
  w.fetch = async url => {
    if (String(url).includes('/latest?')) return {
      ok: true,
      json: async () => ({
        DXY: { mid: 100.2, dayDiffPercent: 0.3, timestamp: new Date().toISOString(), marketState: 'closed', stale: true, quoteAgeSeconds: 600 },
        USOIL: { mid: 62.5, dayDiffPercent: -0.4, timestamp: new Date().toISOString(), marketState: 'open', stale: false, quoteAgeSeconds: 0 }
      })
    };
    if (String(url).includes('/ohlc?')) return { ok: true, json: async () => ({ bars: [] }) };
    throw new Error('Unexpected request: ' + url);
  };
  w.eval(readFileSync('frontend/widgets/catalog/catalog.js', 'utf8'));
  w.eval(readFileSync('frontend/shell/center-chat/widget-dock/widget-dock.js', 'utf8'));
  const dock = w.GaemiGTPWidgetDock;
  dock.initialize();

  for (const id of ['dollar-index', 'wti']) {
    assert.ok(w.GaemiGTPWidgetCatalog[id]);
    assert.equal(dock.add(id), true);
    const card = w.document.querySelector('[data-central-widget-id="' + id + '"]');
    assert.ok(card);
    assert.ok(card.classList.contains('central-widget-card--kospi'));
    assert.equal(card.querySelector('.central-widget-card__kospi-title span').textContent, id === 'dollar-index' ? 'DXY 달러인덱스' : 'WTI 유가');
    assert.ok(card.querySelector('[data-market-indicator-value]'));
  }
  for (const id of ['us-2y', 'us-10y', 'vix']) assert.equal(w.GaemiGTPWidgetCatalog[id], undefined);

  w.eval(readFileSync('frontend/widgets/market-indicators/market-indicators-widget.js', 'utf8'));
  await w.GaemiGTPMarketIndicators.refresh();
  for (const id of ['dollar-index', 'wti']) {
    const card = w.document.querySelector('[data-market-indicator-widget="' + id + '"]');
    assert.ok(card.querySelector('[data-market-indicator-value]').textContent !== '—');
    assert.equal(card.querySelector('[data-market-indicator-source]').textContent, '');
    assert.notEqual(card.querySelector('[data-market-indicator-change]').textContent, '—');
    assert.equal(dock.move(id, 'right'), true);
  }
  dom.window.close();
});
