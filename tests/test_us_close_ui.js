// Offline DOM contract for US-close: title -> index table -> explanation -> hashtags.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '..', 'frontend', 'shell',
  'center-chat', 'us-close-reply.js'), 'utf8');

function makeNode(name) {
  const classes = new Set();
  return {
    tagName: name,
    children: [],
    className: '',
    textContent: '',
    isConnected: true,
    attributes: {},
    classList: { add: (...items) => items.forEach(item => classes.add(item)),
      contains: item => classes.has(item) },
    appendChild(node) { this.children.push(node); return node; },
    append(...nodes) { nodes.forEach(node => this.appendChild(node)); },
    replaceChildren(...nodes) { this.children = nodes; },
    setAttribute(name, value) { this.attributes[name] = value; },
    scrollIntoView() {}
  };
}

const win = {};
vm.runInNewContext(source, {
  window: win, document: { createElement: makeNode },
  Intl
}, { filename: 'us-close-reply.js' });

const valid = {
  session_date_et: '2026-10-19',
  market_indices: [
    { name: '다우존스', close: 51966.03, change_pct: -0.07 },
    { name: '나스닥 종합', close: 26430.89, change_pct: 1.11 },
    { name: 'S&P 500', close: 7690.73, change_pct: 0.41 }
  ],
  issues: [{ headline: '기술주 주도 혼조 마감',
    summary: '나스닥은 올랐지만 다우는 내렸어.',
    tags: ['#AI주', '#나스닥', '#금리'] }]
};

async function main() {
  const api = win.GaemiGTPUSCloseReply;
  const normalized = api.normalize(valid);
  assert.ok(normalized);
  assert.ok(api.normalize(normalized), 'second normalization must preserve the validated format');
  assert.equal(api.plainText(normalized), api.plainText(valid),
    'plainText must accept pre-normalized data from the real UI handler');
  const answer = api.plainText(valid);
  for (const token of ['기술주 주도 혼조 마감', '다우존스 51,966.03 (-0.07%)',
    '나스닥 종합 26,430.89 (+1.11%)', 'S&P 500 7,690.73 (+0.41%)',
    '나스닥은 올랐지만 다우는 내렸어.', '#AI주 #나스닥 #금리']) {
    assert.ok(answer.includes(token), token);
  }
  assert.ok(answer.indexOf('기술주 주도 혼조 마감') <
    answer.indexOf('다우존스') &&
    answer.indexOf('S&P 500') < answer.indexOf('나스닥은 올랐지만'));

  const root = makeNode('div');
  let typed = 0;
  assert.equal(await api.render(root, valid, {
    isActive: () => true,
    typeText: async (element, value) => {
      element.textContent = value;
      typed += 1;
      return true;
    }
  }), true);
  assert.equal(typed, 3);
  assert.equal(root.children.length, 1);
  const order = root.children[0].children;
  assert.deepEqual(order.map(node => node.tagName), ['p', 'div', 'p', 'p']);
  assert.equal(order[0].textContent, valid.issues[0].headline);
  assert.equal(order[2].textContent, valid.issues[0].summary);
  assert.equal(order[3].textContent, '#AI주 #나스닥 #금리');
  const table = order[1].children[0];
  assert.equal(table.tagName, 'table');
  assert.equal(table.children[1].children.length, 3);
  assert.equal(table.children[1].children[0].children[0].textContent, '다우존스');

  // New model-2 output keeps the same storage shape but receives model-3-style
  // paragraph / heading / list spacing, and exactly three code-generated tags.
  const free = {
    ...valid,
    response_format: 'free_text_v1',
    issues: [{
      headline: '미국장 마감',
      summary: '미국장은 **대체로 상승**했어.\n\n**업종별 흐름**\n- **기술주** 약세\n- __산업주__ 강세\n\n다우가 올랐어. `VIX`도 확인해.',
      tags: ['#나스닥상승', '#다우보합', '#실적호조']
    }]
  };
  const normalizedFree = api.normalize(free);
  assert.ok(normalizedFree);
  assert.equal(api.normalize(normalizedFree).responseFormat, 'free_text_v1');
  assert.ok(api.plainText(free).includes('#나스닥상승 #다우보합 #실적호조'));
  const structured = makeNode('div');
  assert.equal(await api.render(structured, free, {
    isActive: () => true,
    typeText: async (element, value) => { element.textContent = value; return true; }
  }), true);
  const sections = structured.children[0].children;
  assert.equal(sections[2].tagName, 'div');
  assert.deepEqual(sections[2].children.map(n => n.tagName), ['p', 'div', 'ul', 'p']);
  assert.equal(sections[2].children[2].children.length, 2);
  assert.equal(sections[2].children[0].textContent, '미국장은 대체로 상승했어.');
  assert.equal(sections[2].children[2].children[0].textContent, '기술주 약세');
  assert.equal(sections[2].children[2].children[1].textContent, '산업주 강세');
  assert.equal(sections[2].children[3].textContent, '다우가 올랐어. VIX도 확인해.');
  assert.equal(sections[3].textContent, '#나스닥상승 #다우보합 #실적호조');
  assert.ok(!api.plainText(free).includes('**'), 'inline Markdown delimiters must not leak');
  assert.ok(api.plainText(free).includes('#나스닥상승 #다우보합 #실적호조'), 'chart hashtags must remain');

  // Fail closed: no random AI text, missing indices or stale numeric values.
  assert.equal(api.normalize({ ...valid, market_indices: valid.market_indices.slice(0, 2) }), null);
  assert.equal(api.normalize({ ...valid, market_indices: [
    ...valid.market_indices.slice(0, 2),
    { name: 'S&P 500', close: 0, change_pct: 0.4 }
  ] }), null);
  const stopped = makeNode('div');
  assert.equal(await api.render(stopped, valid, {
    isActive: () => false,
    typeText: async () => { throw new Error('typing after interruption'); }
  }), false);

  const chatJS = fs.readFileSync(path.join(__dirname, '..', 'frontend', 'shell',
    'center-chat', 'ai-chat.js'), 'utf8');
  const flowJS = fs.readFileSync(path.join(__dirname, '..', 'frontend', 'shell',
    'center-chat', 'analysis-flow.js'), 'utf8');
  const markup = fs.readFileSync(path.join(__dirname, '..', 'frontend', 'index.html'), 'utf8');
  assert.ok(chatJS.includes('GaemiGTPUSCloseReply.render('));
  assert.ok(chatJS.includes('5000 - (Date.now() - thinkingStartedAt)'));
  assert.ok(flowJS.includes('wait(5000)'));
  assert.ok(flowJS.includes('GaemiGTPUSCloseReply.render('));
  assert.ok(markup.includes('us-close-reply.js'));
  assert.ok(markup.indexOf('us-close-reply.js') < markup.indexOf('/ai-chat.js'));
  console.log('US_CLOSE_UI_ARRANGEMENT_AND_REUSED_TYPING_PASS');
}

main().catch(error => { console.error(error); process.exitCode = 1; });
