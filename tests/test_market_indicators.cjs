const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { JSDOM } = require('jsdom');

test('five macro indicators are registered and use the existing movable widget card', async () => {
  const dom = new JSDOM(
    '<main id="mainContent"><section id="centralWidgetDock"><div id="centralWidgetDockBody"></div></section></main>' +
    '<aside id="leftMarketSidebar"><div class="flex-1 overflow-y-auto"></div></aside>' +
    '<aside id="rightPanel"><div id="rightPanelContent"></div></aside>',
    { url: 'https://example.test', runScripts: 'outside-only' }
  );
  const w = dom.window;
  w.setInterval = () => 0;
  Object.defineProperty(w.document, 'hidden', { value: false });
  w.AbortSignal = { timeout: () => ({}) };
  const expected = [
    { id: 'us-2y', value: 4.1, change: 1.2, change_unit: 'bp', source: 'FRED', delay: '일간' },
    { id: 'us-10y', value: 4.3, change: -0.8, change_unit: 'bp', source: 'FRED', delay: '일간' },
    { id: 'dxy', value: 100.2, change: 0.3, change_unit: '%', source: 'BiQuote · MT5 CFD', delay: '시세' },
    { id: 'vix', value: 18.4, change: -1.1, change_unit: '%', source: 'CBOE', delay: '지연 시세' },
    { id: 'wti', value: 62.5, change: 0.4, change_unit: '%', source: 'BiQuote · MT5 CFD', delay: '시세' }
  ];
  w.fetch = async () => ({ ok: true, json: async () => ({ ok: true, items: expected.map(item => ({ ...item, ok: true, fresh: true, as_of: '2026-11-28' })) }) });
  w.eval(readFileSync('frontend/widgets/catalog/catalog.js', 'utf8'));
  w.eval(readFileSync('frontend/shell/center-chat/widget-dock/widget-dock.js', 'utf8'));
  const dock = w.GaemiGTPWidgetDock;
  dock.initialize();

  for (const item of expected) {
    assert.ok(w.GaemiGTPWidgetCatalog[item.id]);
    assert.equal(dock.add(item.id), true);
    const card = w.document.querySelector('[data-central-widget-id="' + item.id + '"]');
    assert.ok(card, item.id + ' card exists');
    assert.ok(card.classList.contains('central-widget-card--kospi'));
    assert.ok(card.querySelector('[data-central-widget-remove="' + item.id + '"]'));
    assert.ok(card.querySelector('[data-market-indicator-value]'));
  }

  w.eval(readFileSync('frontend/widgets/market-indicators/market-indicators-widget.js', 'utf8'));
  await w.GaemiGTPMarketIndicators.refresh();

  for (const item of expected) {
    const card = w.document.querySelector('[data-market-indicator-widget="' + item.id + '"]');
    assert.equal(card.querySelector('[data-market-indicator-value]').textContent.includes('—'), false);
    assert.ok(card.querySelector('[data-market-indicator-source]').textContent.includes(item.source));
    assert.equal(card.querySelector('[data-market-indicator-change]').textContent.includes('—'), false);
    assert.equal(dock.move(item.id, 'right'), true);
    assert.equal(card.parentElement, w.document.querySelector('[data-portable-widget-slot="right"]'));
  }
  dom.window.close();
});
