/* Offline Nasdaq plugin: chart draws only sourced values, tags only saved session. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

class FakeNode {
  constructor(tag) {
    this.tagName = tag;
    this.children = [];
    this.attributes = {};
    this.className = '';
    this.textContent = '';
    this.isConnected = true;
    this.classList = { add: () => {} };
  }
  append(...nodes) { for (const node of nodes) this.children.push(node); }
  appendChild(node) { this.children.push(node); return node; }
  replaceChildren(...nodes) { this.children = nodes; }
  setAttribute(name, value) { this.attributes[name] = value; }
}
function findAll(root, tag) {
  return (root.tagName === tag ? [root] : []).concat(
    root.children.flatMap(child => findAll(child, tag))
  );
}
async function scenario(annotation, shouldFail=false) {
  let calls = 0;
  const points = Array.from({length: 20}, (_,i) => ({
    date: '2026-10-' + String(i+1).padStart(2, '0'), close: 24000+i*10
  }));
  const window = { location: { hostname: 'gaemi-gtp.onrender.com', origin: 'https://gaemi-gtp.onrender.com' }};
  const fetch = async url => {
    calls += 1;
    assert.equal(url, 'https://gaemi-gtp.onrender.com/api/market/nasdaq-chart');
    return {ok: !shouldFail, json: async()=>({
      ok: true, symbol: '.IXIC', points, annotation
    })};
  };
  const doc = { createElement: tag=>new FakeNode(tag),
    createElementNS: (_ns,tag)=>new FakeNode(tag) };
  vm.runInNewContext(
    fs.readFileSync('frontend/widgets/nasdaq/nasdaq-chart.js','utf8'),
    {window,document:doc,fetch,Date,Number,Intl,Math,Object,Error},
  );
  const host = new FakeNode('div');
  window.GaemiGTPNasdaqWidget.mount(host);
  await new Promise(setImmediate);
  assert.equal(calls, 1);
  if (shouldFail) {
    assert.match(host.children[0].textContent, /불러올 수 없어/);
    return;
  }
  const paths = findAll(host, 'path');
  assert.equal(paths.length, annotation ? 3 : 2);
  assert.equal(findAll(host, 'svg').length, 1);
  if (annotation) {
    assert.equal(findAll(host, 'circle').length, 1);
    const tags = findAll(host, 'span').map(node=>node.textContent).filter(x=>x.startsWith('#'));
    assert.deepEqual(tags, annotation.tags);
    assert.ok(findAll(host, 'title')[0].textContent.includes(annotation.session_date_et));
  } else {
    assert.equal(findAll(host, 'circle').length, 0);
    assert.ok(findAll(host, 'p').some(n=>n.textContent.includes('저장되면')));
  }
}

async function main() {
  const catalog = fs.readFileSync('frontend/widgets/catalog/catalog.js','utf8');
  const dock = fs.readFileSync('frontend/shell/center-chat/widget-dock/widget-dock.js','utf8');
  const html = fs.readFileSync('frontend/index.html','utf8');
  assert.match(catalog, /'nasdaq': \{ title: '나스닥'/);
  assert.match(dock, /data-nasdaq-chart-mount/);
  assert.match(dock, /GaemiGTPNasdaqWidget\?\.mount/);
  assert.ok(html.indexOf('nasdaq-chart.js') < html.indexOf('widget-dock.js'));
  await scenario({
    session_date_et:'2026-10-20',
    tags:['#나스닥보합','#다우상승','#실적호조']
  });
  await scenario(null);
  await scenario(null, true);
  console.log('NASDAQ_WIDGET_WITH_NEON_TAGS_PASS');
}
main().catch(error=>{ console.error(error); process.exitCode=1; });
