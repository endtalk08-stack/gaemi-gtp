const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { JSDOM } = require('jsdom');

test('USD/KRW and gold plugins render real source data with explicit freshness labels', async () => {
  const dom = new JSDOM('<main id="mainContent"><section id="centralWidgetDock"><div id="centralWidgetDockBody"></div></section></main><aside id="leftMarketSidebar"></aside><aside id="rightPanel"><div id="rightPanelContent"></div></aside>', {
    url: 'https://example.test', runScripts: 'outside-only'
  });
  const w = dom.window;
  w.setInterval = () => 0;
  w.AbortSignal = AbortSignal;
  const requested = [];
  w.fetch = async (url) => {
    requested.push(String(url));
    if (String(url).includes('frankfurter.dev')) {
      return { ok: true, json: async () => ({ base: 'USD', date: '2026-11-26', rates: { KRW: 1450.25 } }) };
    }
    if (String(url).includes('xaus.com')) {
      return { ok: true, json: async () => ({
        xau: { price: 187500, currency: 'KRW', unit: 'gram' },
        data_state: { status: 'fresh', as_of: '2026-11-27T01:00:00Z' },
        price_as_of: '2026-11-27T01:00:00Z',
        fx_stale: false,
        stale: false
      }) };
    }
    throw new Error('Unexpected URL: ' + url);
  };
  w.eval(readFileSync('frontend/widgets/catalog/catalog.js', 'utf8'));
  w.eval(readFileSync('frontend/widgets/market-quotes/market-quotes-widget.js', 'utf8'));
  w.eval(readFileSync('frontend/shell/center-chat/widget-dock/widget-dock.js', 'utf8'));
  const dock = w.GaemiGTPWidgetDock;
  dock.initialize();
  assert.equal(dock.add('usdkrw'), true);
  assert.equal(dock.add('gold'), true);
  await new Promise(resolve => setTimeout(resolve, 0));

  const fx = w.document.querySelector('[data-market-quote-widget="usdkrw"]');
  const gold = w.document.querySelector('[data-market-quote-widget="gold"]');
  assert.equal(fx.querySelector('[data-market-quote-value]').textContent, '1,450.25');
  assert.equal(gold.querySelector('[data-market-quote-value]').textContent, '187,500');
  assert.match(fx.querySelector('[data-market-quote-meta]').textContent, /일간 기준환율/);
  assert.match(gold.querySelector('[data-market-quote-meta]').textContent, /국제 현물/);
  assert.equal(fx.classList.contains('is-market-quote-stale'), false);
  assert.equal(gold.classList.contains('is-market-quote-stale'), false);
  assert.ok(fx.querySelector('a[href="https://frankfurter.dev/"]'));
  assert.ok(gold.querySelector('a[href="https://xaus.com/api/"]'));
  assert.equal(requested.length, 2);
  assert.ok(requested.every(url => !/api.?key|token/i.test(url)));

  dock.remove('usdkrw');
  dock.remove('gold');
  assert.equal(w.document.querySelector('[data-market-quote-widget]'), null);
  dom.window.close();
});
