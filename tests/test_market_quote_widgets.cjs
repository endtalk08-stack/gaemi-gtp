const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { JSDOM } = require('jsdom');

test('USD/KRW and gold widgets render live ticks, daily changes and intraday charts', async () => {
  const dom = new JSDOM('<main id="mainContent"><section id="centralWidgetDock"><div id="centralWidgetDockBody"></div></section></main><aside id="leftMarketSidebar"></aside><aside id="rightPanel"><div id="rightPanelContent"></div></aside>', {
    url: 'https://example.test', runScripts: 'outside-only'
  });
  const w = dom.window;
  w.setInterval = () => 1;
  Object.defineProperty(w.document, 'hidden', { value: false, configurable: true });
  w.AbortSignal = AbortSignal;
  const requested = [];
  const now = Date.now();
  const bars = (base) => ({
    bars: [
      { openTime: new Date(now - 120000).toISOString(), close: base - 1, isOpen: false },
      { openTime: new Date(now - 60000).toISOString(), close: base, isOpen: true }
    ]
  });
  w.fetch = async (url) => {
    const value = String(url);
    requested.push(value);
    if (value === 'https://biquote.io/api/USDKRW') {
      return { ok: true, json: async () => ({
        symbol: 'USDKRW', mid: 1450.5, dayDiffPercent: -0.2,
        marketState: 'open', stale: false, quoteAgeSeconds: 2, timestamp: now
      }) };
    }
    if (value === 'https://biquote.io/api/XAUUSD') {
      return { ok: true, json: async () => ({
        symbol: 'XAUUSD', mid: 4200, dayDiffPercent: 1.1,
        marketState: 'open', stale: false, quoteAgeSeconds: 2, timestamp: now
      }) };
    }
    if (value.includes('/USDKRW/ohlc?')) return { ok: true, json: async () => bars(1450.5) };
    if (value.includes('/XAUUSD/ohlc?')) return { ok: true, json: async () => bars(4200) };
    throw new Error('Unexpected URL: ' + value);
  };
  w.eval(readFileSync('frontend/widgets/catalog/catalog.js', 'utf8'));
  w.eval(readFileSync('frontend/widgets/market-quotes/market-quotes-widget.js', 'utf8'));
  w.eval(readFileSync('frontend/shell/center-chat/widget-dock/widget-dock.js', 'utf8'));
  const dock = w.GaemiGTPWidgetDock;
  dock.initialize();
  assert.equal(dock.add('usdkrw'), true);
  assert.equal(dock.add('gold'), true);
  await new Promise(resolve => setTimeout(resolve, 25));

  const fx = w.document.querySelector('[data-market-quote-widget="usdkrw"]');
  const gold = w.document.querySelector('[data-market-quote-widget="gold"]');
  assert.equal(fx.querySelector('[data-market-quote-value]').textContent, '1,450.50');
  assert.equal(gold.querySelector('[data-market-quote-value]').textContent,
    (4200 * 1450.5 / 31.1034768).toLocaleString('ko-KR', { maximumFractionDigits: 0 }));
  assert.equal(fx.querySelector('[data-market-quote-change]').textContent, '-0.20%');
  assert.equal(gold.querySelector('[data-market-quote-change]').textContent, '+0.90%');
  assert.match(fx.querySelector('[data-market-quote-meta]').textContent, /실시간/);
  assert.match(gold.querySelector('[data-market-quote-meta]').textContent, /국제 금 현물/);
  assert.equal(fx.classList.contains('central-widget-card--qqq-muted'), false);
  assert.equal(gold.classList.contains('central-widget-card--qqq-muted'), false);
  assert.ok(fx.querySelector('.central-widget-card__sparkline'));
  assert.ok(gold.querySelector('.central-widget-card__sparkline'));
  assert.ok(requested.includes('https://biquote.io/api/USDKRW'));
  assert.ok(requested.includes('https://biquote.io/api/XAUUSD'));
  assert.ok(requested.some(url => url.includes('/USDKRW/ohlc?interval=1m')));
  assert.ok(requested.some(url => url.includes('/XAUUSD/ohlc?interval=1m')));
  assert.ok(requested.every(url => !/api.?key|token/i.test(url)));

  dock.remove('usdkrw');
  dock.remove('gold');
  assert.equal(w.document.querySelector('[data-market-quote-widget]'), null);
  dom.window.close();
});
