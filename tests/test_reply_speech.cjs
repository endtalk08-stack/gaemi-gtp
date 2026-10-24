// Deterministic Web Speech regression tests; no paid API or browser dependency.
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');

function setup() {
  const spoken = [];
  const timers = new Map();
  let timerId = 0;
  let now = 0;
  class Utterance {
    constructor(text) { this.text = text; this.lang = ''; this.rate = 0; }
  }
  const synth = {
    speaking: false,
    paused: false,
    cancelCount: 0,
    resumeCount: 0,
    speak(utterance) {
      spoken.push(utterance);
      this.speaking = true;
      utterance.onstart?.({});
    },
    cancel() { this.cancelCount++; this.speaking = false; },
    resume() { this.resumeCount++; this.paused = false; }
  };
  const win = {
    speechSynthesis: synth,
    addEventListener() {}
  };
  const ctx = {
    window: win,
    document: { visibilityState: 'visible' },
    SpeechSynthesisUtterance: Utterance,
    Date: { now: () => now },
    setTimeout(fn, delay) { timers.set(++timerId, { fn, delay, interval: false }); return timerId; },
    clearTimeout(id) { timers.delete(id); },
    setInterval(fn, delay) { timers.set(++timerId, { fn, delay, interval: true }); return timerId; },
    clearInterval(id) { timers.delete(id); }
  };
  vm.runInNewContext(fs.readFileSync('frontend/js/reply-speech.js', 'utf8'), ctx);
  const button = () => ({
    title: '소리 내어 읽기', attributes: {},
    setAttribute(name, value) { this.attributes[name] = value; }
  });
  function tickTimeouts() {
    for (const [id, item] of [...timers.entries()]) {
      if (!item.interval && timers.has(id)) {
        timers.delete(id);
        item.fn();
      }
    }
  }
  function tickIntervals() {
    for (const [id, item] of [...timers.entries()]) {
      if (item.interval && timers.has(id)) item.fn();
    }
  }
  function endLatest() {
    const last = spoken.at(-1);
    synth.speaking = false;
    last.onend?.({});
    tickTimeouts();
  }
  return { reader: win.GaemiGTPReplySpeech, synth, spoken, button,
    endLatest, tickIntervals, tickTimeouts, advance: ms => { now += ms; }, document: ctx.document };
}

test('long Korean article reads ALL text as short consecutive utterances', () => {
  const f = setup();
  const input = ('엔비디아는 실적 발표 이후 시장 관심을 받았습니다. 투자자들은 성장률과 가이던스를 확인합니다. ').repeat(35).trim();
  const expected = input.replace(/\s+/g, ' ').trim();
  const btn = f.button();
  f.reader.toggle(input, btn);
  for (let i = 0; i < 1000 && btn.attributes['aria-pressed'] === 'true'; i++) f.endLatest();
  assert.ok(f.spoken.length > 10, 'must split a long response');
  assert.ok(f.spoken.every(u => u.text.length > 0 && u.text.length <= 90));
  assert.equal(f.spoken.map(u => u.text).join(' '), expected, 'no unread remainder or lost words');
  assert.equal(btn.attributes['aria-pressed'], 'false');
  assert.equal(btn.title, '소리 내어 읽기');
});

test('repeated click stops; late callbacks cannot restart old chunks', () => {
  const f = setup(), btn = f.button();
  f.reader.toggle('첫 번째 긴 뉴스 내용입니다. '.repeat(40), btn);
  const old = f.spoken.at(-1);
  f.reader.toggle('ignored', btn);
  const count = f.spoken.length;
  old.onend?.({});
  old.onerror?.({ error: 'interrupted' });
  f.tickTimeouts();
  assert.equal(f.spoken.length, count);
  assert.equal(btn.attributes['aria-pressed'], 'false');
});

test('switching replies cancels old reader and speaks new one', () => {
  const f = setup(), a = f.button(), b = f.button();
  f.reader.toggle('첫번째 답변입니다. '.repeat(40), a);
  const old = f.spoken.at(-1);
  f.reader.toggle('두번째 답변입니다.', b);
  old.onend?.({});
  assert.equal(f.spoken.at(-1).text, '두번째 답변입니다.');
  assert.equal(a.attributes['aria-pressed'], 'false');
  f.endLatest();
  assert.equal(b.attributes['aria-pressed'], 'false');
});

test('recoverable voice interruption retries the SAME chunk once', () => {
  const f = setup(), btn = f.button();
  f.reader.toggle('이 문장은 실패 후 다시 읽어야 합니다. ', btn);
  const first = f.spoken.at(-1);
  first.onerror?.({ error: 'interrupted' });
  f.tickTimeouts();
  assert.equal(f.spoken.at(-1).text, first.text);
  assert.equal(f.spoken.length, 2);
  f.endLatest();
  assert.equal(btn.attributes['aria-pressed'], 'false');
});

test('repeated fatal error does not silently skip unread text', () => {
  const f = setup(), btn = f.button();
  f.reader.toggle('읽기 실패 테스트 문장입니다.', btn);
  f.spoken.at(-1).onerror?.({ error: 'network' });
  f.tickTimeouts();
  f.spoken.at(-1).onerror?.({ error: 'network' });
  assert.equal(f.spoken.length, 2, 'retry is bounded');
  assert.match(btn.title, /읽기 중단/);
  assert.equal(btn.attributes['aria-pressed'], 'false');
});

test('missing onend/onerror is retried after browser reports no speech', () => {
  const f = setup(), btn = f.button();
  f.reader.toggle('음성이 끊어진 경우도 복구해야 합니다.', btn);
  const first = f.spoken.at(-1);
  f.synth.speaking = false;
  f.advance(10000);
  f.tickIntervals();
  f.tickTimeouts();
  assert.equal(f.spoken.length, 2);
  assert.equal(f.spoken.at(-1).text, first.text);
  f.endLatest();
  assert.equal(btn.attributes['aria-pressed'], 'false');
});

test('recover paused browser speech only while tab is visible', () => {
  const f = setup(), btn = f.button();
  f.reader.toggle('일시정지된 브라우저 엔진을 복구합니다.', btn);
  f.synth.paused = true;
  f.document.visibilityState = 'hidden';
  f.tickIntervals();
  assert.equal(f.synth.resumeCount, 0);
  f.document.visibilityState = 'visible';
  f.tickIntervals();
  assert.equal(f.synth.resumeCount, 1);
  f.endLatest();
});

test('app imports reader and routes existing button to it', () => {
  const html = fs.readFileSync('frontend/index.html', 'utf8');
  const actions = fs.readFileSync('frontend/js/first-reply-actions.js', 'utf8');
  assert.match(html, /<script src="js\/reply-speech\.js\?v=/);
  assert.match(actions, /GaemiGTPReplySpeech\.toggle\(replyText, button\)/);
  assert.doesNotMatch(fs.readFileSync('frontend/js/reply-speech.js', 'utf8'), /fish\.audio|https:\/\/|API_KEY/);
});
