const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

class E {
  constructor(tag = 'div') {
    this.tag = tag;
    this.children = [];
    this.className = '';
    this._text = '';
    this.href = '';
  }
  set textContent(text) { this._text = String(text); this.children = []; }
  get textContent() { return this._text + this.children.map(c => c.textContent).join(''); }
  appendChild(child) { this.children.push(child); return child; }
  replaceChildren(...children) { this._text = ''; this.children = [...children]; }
}
const window = {};
const document = {
  createElement: tag => new E(tag),
  createTextNode: text => { const x = new E('#text'); x.textContent = text; return x; }
};
vm.runInNewContext(fs.readFileSync('frontend/js/company-intro-preview.js','utf8'), {
  window, document,
  // Avoid real timeouts; assert progressive updates deterministically.
  setTimeout: fn => { Promise.resolve().then(fn); return 1; }
});

test('MU preview is explanatory prose, not trading price or stock metadata', () => {
  const payload = {
    symbol: 'MU', name: '마이크론 테크놀로지',
    paragraphs: ['마이크론은 메모리 반도체 회사예요.', '쉽게 말해 데이터를 저장하는 칩을 만듭니다.'],
    highlights: [{title:'AI 서버용 HBM',description:'빠른 데이터 처리를 돕습니다.'}],
    related: [{name:'엔비디아',symbol:'NVDA'},{name:'AMD',symbol:'AMD'}],
    source_url:'https://www.micron.com/about/company/corporate-profile'
  };
  const container = new E();
  assert.equal(window.GaemiGTPCompanyIntroPreview.render(container,payload),true);
  assert.match(container.textContent,/쉽게 말해/);
  assert.match(container.textContent,/AI 서버용 HBM/);
  assert.match(container.textContent,/엔비디아 \(NVDA\)/);
  assert.doesNotMatch(container.textContent,/거래소:|현재가|등락률/);
  assert.match(window.GaemiGTPCompanyIntroPreview.readableText(payload),/AMD \(AMD\)/);
  assert.equal(container.children.some(e=>e.tag==='h3' || e.tag==='a'), false,
    'duplicate company name and visible source link must be absent');
});

test('typewriter animates the actual narrative and preserves bold highlights', async () => {
  const payload = {
    symbol: 'MU',
    paragraphs: ['마이크론은 메모리 반도체 전문 기업입니다.', '쉽게 말해 데이터를 저장하는 기업입니다.'],
    highlights: [{title:'AI 서버용 HBM', description:'AI 서버의 데이터 처리 속도를 돕습니다.'}],
    related: [{symbol:'AMD',name:'AMD'}]
  };
  const row = new E();
  const ongoing = window.GaemiGTPCompanyIntroPreview.renderTyped(row, payload);
  assert.notEqual(row.textContent, window.GaemiGTPCompanyIntroPreview.readableText(payload),
    'must begin displaying before the full narration is typed');
  assert.equal(await ongoing, true);
  assert.match(row.textContent, /메모리 반도체 전문/);
  assert.match(row.textContent, /AMD \(AMD\)/);
  assert.ok(row.children.some(e => e.children.some(c => c.tag === 'strong' && c.textContent === 'AI 서버용 HBM: ')));
  assert.equal(row.children.some(e=>e.tag==='h3' || e.tag==='a'),false);
});

test('typewriter stops when user switches to another stock', async () => {
  const row = new E();
  const payload = {symbol:'MU', paragraphs:['긴 마이크론 회사 설명입니다.'.repeat(10)], highlights:[], related:[]};
  let checks = 0;
  const done = await window.GaemiGTPCompanyIntroPreview.renderTyped(row,payload,()=> ++checks < 3);
  assert.equal(done,false);
  assert.ok(row.textContent.length < payload.paragraphs[0].length);
});

test('unknown company does not render guessed content', () => {
  assert.equal(window.GaemiGTPCompanyIntroPreview.render(new E(), {symbol:'TSLA'}),false);
});

test('integration bypasses the old price answer only for MU trial', () => {
  const flow=fs.readFileSync('frontend/shell/center-chat/analysis-flow.js','utf8');
  const index=fs.readFileSync('frontend/index.html','utf8');
  assert.match(flow,/isMicronPreview/);
  assert.match(flow,/api\/company-intro-preview\?symbol=MU/);
  assert.match(flow,/if \(isMicronPreview && window\.GaemiGTPCompanyIntroPreview\)/);
  assert.match(flow,/renderer\.renderTyped\(row, intro/);
  assert.match(flow,/minimumLoading.*Promise/);
  assert.match(flow,/progress\.textContent = '조회중입니다\.\.\.'/);
  assert.match(flow,/fetchAnalysisFromBackend\(/,'all other tickers keep old route');
  assert.match(index,/js\/company-intro-preview\.js\?v=/);
});
