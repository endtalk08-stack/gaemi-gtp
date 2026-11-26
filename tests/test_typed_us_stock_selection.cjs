const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const tabs = [
  { dataset: { centerMode: 'news' }, attrs: {}, setAttribute(k, v) { this.attrs[k] = v; }, removeAttribute(k) { delete this.attrs[k]; } },
  { dataset: { centerMode: 'chat' }, attrs: {}, setAttribute(k, v) { this.attrs[k] = v; }, removeAttribute(k) { delete this.attrs[k]; } }
];
const classes = new Set();
const elements = {
  mainHeroView: { classList: { add() {}, remove() {} } },
  mainContent: { classList: { add() {}, remove() {} } },
  gaemiCenterNewsFeed: { setAttribute() {} }
};
const document = {
  body: { classList: { add: (v) => classes.add(v), remove: (v) => classes.delete(v) } },
  getElementById: (id) => elements[id] || null,
  querySelectorAll: (selector) => selector === '[data-center-mode]' ? tabs : []
};
let request;
const window = {
  innerWidth: 1440,
  GaemiGTPWorkspaceState: { save() {} },
  GaemiGTPWorkspaceShellState: { apply() {} },
  GaemiGTPApp: { requestStock: (...args) => { request = args; } }
};
const source = fs.readFileSync(path.join(__dirname, '../frontend/shell/center-chat/search-controls.js'), 'utf8');
vm.runInNewContext(source, { window, document, console });

window.GaemiGTPCenterChatSearch.submitChatInput('엔비디아');
assert.equal(request[0], '엔비디아');
assert.deepEqual(JSON.parse(JSON.stringify(request[1])), {
  market: 'us', menu: 'value', name: '엔비디아', symbol: 'NVDA',
  currency: 'USD', source: 'kiwoom'
});
assert.equal(classes.has('analysis-mode'), true);
assert.equal(tabs[0].attrs['aria-current'], undefined);
assert.equal(tabs[1].attrs['aria-current'], 'page');

window.GaemiGTPCenterChatSearch.submitChatInput('NVDA');
assert.equal(request[0], '엔비디아');
assert.equal(request[1].symbol, 'NVDA');
console.log('typed US stock selection and Chat mode: ok');
