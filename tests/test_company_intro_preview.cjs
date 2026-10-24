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
vm.runInNewContext(fs.readFileSync('frontend/js/company-intro-preview.js','utf8'), {window,document});

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
  assert.ok(container.children.some(e=>e.tag==='a' && e.href.startsWith('https://www.micron.com')));
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
  assert.match(flow,/fetchAnalysisFromBackend\(/,'all other tickers keep old route');
  assert.match(index,/js\/company-intro-preview\.js\?v=/);
});
