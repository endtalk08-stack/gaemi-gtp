// Offline: the real UI auto-display gate accepts cited AI issues without price_reason.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('frontend/shell/center-chat/analysis-flow.js', 'utf8');
const start = source.indexOf('    function hasCitedAiBriefs(result) {');
const end = source.indexOf('\n    function startTypewriterFlow(', start);
assert.ok(start >= 0 && end > start, 'pure production helper exists');
const script = source.slice(start, end).trim() + '; hasCitedAiBriefs;';
const hasCitedAiBriefs = vm.runInNewContext(script);
const ai = {headline:'매출 성장', summary:'공식 계약을 체결했어',
            source_articles:[{url:'https://news.example/article'}]};
assert.equal(hasCitedAiBriefs({issue_briefs:[ai], price_reason:null}), true);
assert.equal(hasCitedAiBriefs({issue_briefs:[], price_reason:null}), false);
assert.equal(hasCitedAiBriefs({issue_briefs:[{headline:'규칙',summary:'기사 없음'}]}), false);
assert.equal(hasCitedAiBriefs({issue_briefs:[{...ai,source_articles:[]}]}), false);
assert.equal(hasCitedAiBriefs({issue_briefs:[{...ai,source_articles:[{url:'javascript:alert(1)'}]}]}), false);
assert.match(source, /if \(hasCitedAiBriefs\(result\) \|\|[\s\S]*?void appendWhy\(true\);/);
console.log('SOURCED_AI_INLINE_DISPLAY_OK 5 cases');
