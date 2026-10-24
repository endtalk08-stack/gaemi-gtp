// Isolated DOM regression: the animated caret must follow the last inline
// characters, not appear on a separate line after the outer response row.
// No browser, provider/API, DB or authentication calls.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

class Element {
  constructor(tag) {
    this.tagName = tag;
    this.children = [];
    this._text = '';
    this.classes = new Set();
    this.classList = {
      add: (name) => this.classes.add(name),
      remove: (name) => this.classes.delete(name),
      contains: (name) => this.classes.has(name),
    };
    this.dataset = { chatMessageId: '1' };
    this.isConnected = true;
  }
  set textContent(text) {
    this._text = String(text);
    this.children = [];
  }
  get textContent() {
    return this._text + this.children.map((child) => child.textContent).join('');
  }
  // Simplified visible-text semantics for the block/inline markup of replies.
  // Real browsers provide Element.innerText, unlike this lightweight fake DOM.
  get innerText() {
    return this._text + this.children.map((child) => {
      const text = child.innerText;
      return ['p', 'div', 'li'].includes(child.tagName) ? text + '\\n' : text;
    }).join('');
  }
  appendChild(child) {
    this.children.push(child);
    child.parent = this;
    return child;
  }
  querySelector(selector) {
    const search = (root) => {
      for (const child of root.children) {
        if (selector === '.typing-cursor' && child.classList.contains('typing-cursor')) return child;
        const found = search(child);
        if (found) return found;
      }
      return null;
    };
    return search(this);
  }
  scrollIntoView() {}
}
async function scenario(answer, interrupt = false) {
  const row = new Element('div');
  const document = {
    head: new Element('head'),
    getElementById: () => null,
    createElement: (tag) => new Element(tag),
  };
  const actions = [];
  const window = { GaemiGTPFirstReplyActions: { appendFirstReplyActions: (anchor, text) => {
    actions.push(text);
    return null;
  } } };
  const observations = [];
  let session = { id: 1, stock: '' };
  const sandbox = {
    window, document,
    setTimeout: (done, delay) => {
      if (delay === 40) {
        const caret = row.querySelector('.typing-cursor');
        assert.ok(caret, 'caret must be present while typing');
        assert.notEqual(caret, row, 'cursor must not be attached to outer row');
        assert.ok(['span', 'strong'].includes(caret.tagName), 'caret must follow inline text');
        assert.ok(caret.textContent.length > 0, 'caret must follow written characters');
        observations.push({ tag: caret.tagName, text: caret.textContent });
        if (interrupt && observations.length === 3) session = { id: 2 };
      }
      done();
      return 0;
    },
    clearTimeout: () => {},
  };
  vm.runInNewContext(
    fs.readFileSync('frontend/shell/center-chat/ai-chat.js', 'utf8'), sandbox
  );
  const ctx = {
    getSession: () => session,
    appendChatMessage: () => row,
  };
  const ok = await window.GaemiGTPCenterAIChat.create(ctx).appendChatReply(answer, 1);
  assert.equal(row.querySelector('.typing-cursor'), null, 'caret must disappear after typing');
  assert.ok(!row.classList.contains('typing-cursor'), 'outer row must never own caret');
  return { ok, row, observations, actions };
}
(async () => {
  const plain = await scenario('한글이 길게 이어지는 문장입니다. 다음 줄도 있어요.');
  assert.equal(plain.ok, true);
  assert.ok(plain.observations.length > 3);
  assert.equal(plain.row.textContent, '한글이 길게 이어지는 문장입니다. 다음 줄도 있어요.');

  const rich = await scenario('첫 문단\n\n**굵은 제목**\n\n- 첫 항목\n- 두 번째 **강조** 항목\n\n마지막 문단');
  assert.equal(rich.ok, true);
  assert.ok(rich.observations.some((item) => item.tag === 'strong'));
  assert.ok(rich.observations.some((item) => item.tag === 'span'));
  assert.match(rich.row.textContent, /마지막 문단/);
  assert.equal(rich.actions.length, 1, 'exactly one completed-reply action set');
  assert.ok(rich.actions[0].includes('굵은 제목'), 'action text preserves visible words');
  assert.ok(rich.actions[0].includes('두 번째 강조 항목'), 'action text preserves list item');
  assert.ok(!/\\*\\*|^\\s*[-*+]\\s/m.test(rich.actions[0]), 'copy/read do not receive hidden Markdown markers');

  const interrupted = await scenario('계속 타이핑되는 긴 문장입니다.', true);
  assert.equal(interrupted.ok, false);
  console.log('INLINE_TYPING_CARET_REGRESSION_OK');
})().catch((error) => { console.error(error); process.exitCode = 1; });
