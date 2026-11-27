'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const searchWindow = {};
vm.runInNewContext(
  fs.readFileSync('frontend/shell/center-chat/search-controls.js', 'utf8'),
  { window: searchWindow, document: {} }
);
const resolveStockInputOnly = searchWindow.GaemiGTPCenterChatSearch.resolveStockInputOnly;

for (const [input, expected] of [
  ['엔비디아', '엔비디아'],
  ['NVDA', '엔비디아'],
  ['MU', '마이크론 테크놀로지'],
  ['마이크론 테크놀로지', '마이크론 테크놀로지'],
  ['버크셔 해서웨이', '버크셔 해서웨이'],
  ['005930', '삼성전자'],
]) {
  assert.equal(resolveStockInputOnly(input), expected, input);
}
assert.equal(resolveStockInputOnly('엔비디아 왜 올랐어?'), '');
assert.equal(searchWindow.GaemiGTPCenterChatSearch.isQuestionInput('엔비디아 왜 올랐어?'), true);
assert.equal(searchWindow.GaemiGTPCenterChatSearch.isQuestionInput('LITE'), false);

const requested = [];
const chatWindow = {
  GaemiGTPAppState: { getCurrentAppMode: () => 'gaemi' },
  GaemiGTPCenterChatSearch: searchWindow.GaemiGTPCenterChatSearch,
  GaemiGTPApp: { requestStock: (stock) => requested.push(stock) },
};
vm.runInNewContext(
  fs.readFileSync('frontend/shell/center-chat/ai-chat.js', 'utf8'),
  { window: chatWindow, document: {} }
);
const chat = chatWindow.GaemiGTPCenterAIChat.create({
  getPendingQuestionSessionId: () => null,
  getSession: () => null,
});
assert.equal(chat.submitQuestion('엔비디아'), true);
assert.equal(chat.submitQuestion('LITE'), true);
assert.deepEqual(requested, ['엔비디아', 'LITE']);
console.log('PASS: exact company/ticker chat input starts stock analysis');
