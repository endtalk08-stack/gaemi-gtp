const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

// Exercise the actual browser analysis-data store without changing the UI.
function makeDataStore() {
  const window = { dispatchEvent() {} };
  class CustomEvent { constructor(name) { this.type = name; } }
  vm.runInNewContext(
    fs.readFileSync('frontend/widgets/analysis-data/analysis-data.js', 'utf8'),
    { window, CustomEvent },
    { filename: 'analysis-data.js' }
  );
  return window.GaemiGTPAnalysisData;
}

test('KR center is today-only while the right panel retains the last 24 hours', () => {
  const store = makeDataStore();
  store.set('삼성전자', {
    sections: [],
    disclosures: [{ receipt_no: 'today', source: 'DART' }],
    panel_disclosures: [
      { receipt_no: 'today', source: 'DART' },
      { receipt_no: 'yesterday-but-within24h', source: 'DART' }
    ],
    us_filings: [], panel_us_filings: []
  });
  const result = store.get();
  assert.equal(result.disclosures.length, 1);
  assert.equal(result.panelDisclosures.length, 2);
  assert.equal(result.panelDisclosures[1].receipt_no, 'yesterday-but-within24h');
});

test('US center and panel have separate data without cross-market leakage', () => {
  const store = makeDataStore();
  store.set('애플', {
    sections: [],
    disclosures: [],
    panel_disclosures: [],
    us_filings: [],
    panel_us_filings: [{ accession: 'us-1', source: 'SEC' }]
  });
  const result = store.get();
  assert.equal(result.usFilings.length, 0);
  assert.equal(result.panelUsFilings.length, 1);
  assert.equal(result.panelDisclosures.length, 0);
});

test('empty panel and center remain empty; no manufactured disclosure', () => {
  const store = makeDataStore();
  store.set('삼성전자', { sections: [], disclosures: [], us_filings: [] });
  const result = store.get();
  assert.equal(result.disclosures.length, 0);
  assert.equal(result.panelDisclosures.length, 0);
  assert.equal(result.usFilings.length, 0);
  assert.equal(result.panelUsFilings.length, 0);
});
