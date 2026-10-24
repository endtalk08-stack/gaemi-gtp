const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const window = {};
const flowFile = 'frontend/shell/center-chat/analysis-flow.js';
const source = fs.readFileSync(flowFile, 'utf8');
vm.runInNewContext(source, { window });
const choose = window.GaemiGTPCenterAnalysisFlow.whyChoiceFromChange;

test('MU sidebar +2.46% is RED even if 20-day indicator is -1.06%', () => {
  const selection = { market: 'us', symbol: 'MU', name: '마이크론 테크놀로지', change_pct: 2.46 };
  const misleadingAnalysis = '20일선 -1.06% / 지표 -9.10%';
  assert.ok(misleadingAnalysis.includes('-1.06%'));
  assert.equal(choose(selection.change_pct).tag, '#왜_빨간불일까?');
  assert.equal(choose(selection.change_pct).label, '왜 빨간불일까?');
});

test('negative values are blue, including small negative moves', () => {
  assert.equal(choose(-1.06).tag, '#왜_파란불일까?');
  assert.equal(choose(-0.01).tag, '#왜_파란불일까?');
});

test('positive values are red, including small positive moves', () => {
  assert.equal(choose(0.01).tag, '#왜_빨간불일까?');
  assert.equal(choose('2.46').tag, '#왜_빨간불일까?');
});

test('exactly zero displays neutral; unavailable quote does not guess direction', () => {
  assert.equal(choose(0).tag, '#왜_보합일까?');
  assert.equal(choose(-0).tag, '#왜_보합일까?');
  for (const missing of [undefined, null, '', 'unavailable', NaN, Infinity, false]) {
    assert.equal(choose(missing).tag, '#왜_움직였을까?');
  }
});

test('flow reads the clicked sidebar market selection and never analysis prose', () => {
  const sidebar = fs.readFileSync('frontend/shell/left-market-sidebar/market-sidebar.js', 'utf8');
  const app = fs.readFileSync('frontend/js/app.js', 'utf8');
  assert.match(sidebar, /window\.openStockInChat\?\.\(item\.name,/);
  assert.match(sidebar, /change_pct:\s*button\.dataset\.currentChangePct/);
  assert.match(app, /marketSelection: marketSelection\?\.name === stock \? \{ \.\.\.marketSelection \} : null/);
  assert.match(source, /whyChoiceFromChange\(ctx\.getSession\(\)\?\.marketSelection\?\.change_pct\)/);
  assert.doesNotMatch(source, /const changeMatch = String\(whySection/);
  assert.match(source, /await typeText\(element, text, \{ chunkSize: 1 \}\)/);
});
