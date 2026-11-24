const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { JSDOM } = require('jsdom');

function dispatchPointer(window, target, type, x, y) {
  const event = new window.Event(type, { bubbles: true, cancelable: true });
  Object.defineProperties(event, {
    pointerId: { value: 1 },
    pointerType: { value: 'mouse' },
    button: { value: 0 },
    clientX: { value: x },
    clientY: { value: y }
  });
  target.dispatchEvent(event);
}

test('widgets keep identity and live content while moving without move buttons', () => {
  const dom = new JSDOM('<aside id="leftMarketSidebar"><div class="flex-1 overflow-y-auto"></div></aside><main id="mainContent"><section id="centralWidgetDock"><div id="centralWidgetDockBody"></div></section></main><aside id="rightPanel"><div id="rightPanelContent"></div></aside>', { url: 'https://example.test', runScripts: 'outside-only' });
  const w = dom.window;
  w.setInterval = () => 0;
  w.fetch = async () => ({ ok: false });
  w.eval(readFileSync('frontend/widgets/catalog/catalog.js', 'utf8'));
  w.eval(readFileSync('frontend/shell/center-chat/widget-dock/widget-dock.js', 'utf8'));
  const dock = w.GaemiGTPWidgetDock;
  dock.initialize();
  dock.add('qqq');
  const card = w.document.querySelector('[data-central-widget-id="qqq"]');
  assert.ok(card);
  assert.equal(card.querySelector('[aria-label="위젯 위치"]'), null);
  for (const place of ['right', 'left', 'center']) {
    assert.equal(dock.move('qqq', place), true);
    const slot = place === 'center'
      ? w.document.getElementById('centralWidgetDockBody')
      : w.document.querySelector('[data-portable-widget-slot="' + place + '"]');
    assert.equal(card.parentElement, slot);
  }
  dock.move('qqq', 'right');
  dock.add('spy');
  assert.equal(w.document.querySelector('[data-central-widget-id="qqq"]'), card);
  w.dispatchEvent(new w.CustomEvent('gaemi:qqq-quote', { detail: { quote: { symbol: 'QQQ', price: 600, change_pct: 2, received_at_ms: Date.now(), stale: false } } }));
  assert.equal(card.querySelector('[data-kospi-price]').textContent, '600.00');
  dock.add('news-caption');
  dock.move('news-caption', 'left');
  dock.setNewsHeadline('테스트 속보');
  assert.equal(w.document.querySelector('[data-news-caption-title]').textContent, '테스트 속보');
  Object.defineProperty(w, 'innerWidth', { value: 390 });
  w.document.body.classList.add('left-plugin-open');
  dock.move('spy', 'left');
  assert.equal(w.document.body.classList.contains('right-panel-open'), false);
  assert.equal(w.document.body.classList.contains('left-plugin-open'), false);
  dock.remove('qqq');
  assert.equal(card.isConnected, false);
  assert.equal(dock.move('qqq', 'right'), false);
  dom.window.close();
});

test('the existing semiconductor tile drags the same industry map into a panel', () => {
  const dom = new JSDOM('<aside id="leftMarketSidebar"><div class="flex-1 overflow-y-auto"><button data-info-tab-action="industry">업종</button><div id="marketIndustryWidgetSlot" data-widget-drop-zone="left"><div id="marketIndustryMap"><div class="industry-map-sector" data-widget-drag-handle="industry">반도체</div></div></div><div id="rankingSection"><div id="marketRankingList"></div></div></div></aside><main id="mainContent"><section id="centralWidgetDock"><div id="centralWidgetDockBody"></div></section></main><aside id="rightPanel"><div id="rightPanelContent"></div></aside>', { url: 'https://example.test', runScripts: 'outside-only' });
  const w = dom.window;
  w.setInterval = () => 0;
  w.fetch = async () => ({ ok: false });
  const menu = w.document.querySelector('[data-info-tab-action="industry"]');
  const homeSlot = w.document.getElementById('marketIndustryWidgetSlot');
  const map = w.document.getElementById('marketIndustryMap');
  const handle = map.querySelector('[data-widget-drag-handle="industry"]');
  w.eval(readFileSync('frontend/widgets/catalog/catalog.js', 'utf8'));
  w.eval(readFileSync('frontend/widgets/industry/industry-widget.js', 'utf8'));
  w.eval(readFileSync('frontend/shell/center-chat/widget-dock/widget-dock.js', 'utf8'));
  const dock = w.GaemiGTPWidgetDock;
  dock.initialize();

  w.document.elementFromPoint = (x) => x > 50
    ? w.document.getElementById('mainContent')
    : w.document.getElementById('leftMarketSidebar');
  dispatchPointer(w, handle, 'pointerdown', 10, 10);
  dispatchPointer(w, w.document, 'pointermove', 100, 10);
  dispatchPointer(w, w.document, 'pointerup', 100, 10);

  assert.equal(dock.isActive('industry'), true);
  const widget = w.document.querySelector('[data-central-widget-id="industry"]');
  const target = widget.querySelector('[data-industry-widget-target]');
  assert.ok(widget);
  assert.equal(widget.parentElement, w.document.getElementById('centralWidgetDockBody'));
  assert.equal(target.firstElementChild, map);
  assert.equal(map.querySelector('[data-widget-drag-handle="industry"]'), handle);
  assert.equal(widget.querySelector('[aria-label="위젯 위치"]'), null);
  assert.equal(menu.isConnected, true);

  dock.move('industry', 'right');
  assert.equal(widget.parentElement, w.document.querySelector('[data-portable-widget-slot="right"]'));
  assert.equal(target.firstElementChild, map);
  dock.move('industry', 'left');
  assert.equal(widget.parentElement, homeSlot);
  assert.equal(homeSlot.contains(map), true);
  dock.remove('industry');
  assert.equal(map.parentElement, homeSlot);
  assert.equal(menu.isConnected, true);
  dom.window.close();
});


test('right panel displays all moved widgets before its full-height dashboard and restores saved positions', () => {
  const html = readFileSync('frontend/index.html', 'utf8');
  const dom = new JSDOM(html, { url: 'https://example.test', runScripts: 'outside-only' });
  const w = dom.window;
  w.setInterval = () => 0;
  w.fetch = async () => ({ ok: false });
  const right = w.document.getElementById('rightPanelContent');
  const dashboard = right.firstElementChild;
  const map = w.document.getElementById('marketIndustryMap');
  const ids = ['qqq', 'spy', 'dia', 'night-futures', 'news-caption', 'news-feed', 'industry'];
  w.localStorage.setItem('gaemiGTP_central_widget_dock_v1', JSON.stringify(ids));
  w.localStorage.setItem('gaemiGTP_widget_placements_v1', JSON.stringify(Object.fromEntries(ids.map(id => [id, 'right']))));
  w.eval(readFileSync('frontend/widgets/catalog/catalog.js', 'utf8'));
  w.eval(readFileSync('frontend/widgets/industry/industry-widget.js', 'utf8'));
  w.eval(readFileSync('frontend/shell/center-chat/widget-dock/widget-dock.js', 'utf8'));
  const dock = w.GaemiGTPWidgetDock;
  dock.initialize();
  for (const id of ids) {
    if (!dock.isActive(id)) dock.add(id);
    assert.equal(dock.getPlacement(id), 'right');
  }
  const slot = right.querySelector('[data-portable-widget-slot="right"]');
  assert.equal(right.firstElementChild, slot);
  assert.equal(slot.nextElementSibling, dashboard);
  assert.equal(slot.style.maxHeight, 'none');
  assert.equal(slot.style.overflow, 'visible');
  assert.deepEqual(Array.from(slot.children, card => card.dataset.centralWidgetId), ids);
  assert.ok(slot.contains(map));
  for (const id of ids) {
    const card = slot.querySelector('[data-central-widget-id="' + id + '"]');
    assert.equal(dock.move(id, 'center'), true);
    assert.equal(dock.move(id, 'right'), true);
    assert.equal(card.parentElement, slot);
    assert.equal(right.firstElementChild, slot);
  }
  assert.equal(dashboard.isConnected, true);
  for (const id of ids) dock.move(id, 'center');
  assert.equal(slot.children.length, 0);
  assert.equal(dashboard.isConnected, true);
  dom.window.close();
});


test('news widget in the right panel uses the panel scroll instead of its old viewport height cap', () => {
  const css = readFileSync('frontend/widgets/news/news-widget.css', 'utf8');
  const rule = css.match(/#rightPanelContent > \[data-portable-widget-slot="right"\] \.central-widget-card--news-feed \.gnw-root\s*\{([^}]*)\}/);
  assert.ok(rule, 'right-panel-specific news widget rule exists');
  assert.match(rule[1], /max-height:\s*none/);
  assert.match(rule[1], /overflow:\s*visible/);
  assert.match(rule[1], /scrollbar-gutter:\s*auto/);
  assert.match(css, /\.gnw-root\s*\{[^}]*max-height:\s*calc\(100vh - 150px\)/s, 'center/left widget layout keeps its original height rule');
});


test('right panel keeps vertical scrolling enabled when portable widgets are present', () => {
  const css = readFileSync('frontend/pages/panel-workspace/panel-workspace.css', 'utf8');
  const override = css.match(/#rightPanelContent:has\(#rightPanelTabView-(?:panel-workspace|dashboard):not\(\[hidden\]\)\):has\(> \[data-portable-widget-slot="right"\]:not\(:empty\)\),[\s\S]*?\{([^}]*)\}/);
  assert.ok(override, 'portable-widget override has enough specificity to beat the legacy dashboard overflow rule');
  assert.match(override[1], /overflow-y:\s*auto\s*!important/);
  assert.match(override[1], /overflow-x:\s*hidden\s*!important/);

  const dashboardCss = readFileSync('frontend/pages/dashboard/dashboard.css', 'utf8');
  assert.match(dashboardCss, /panel-workspace\/panel-workspace\.css\?v=20261125-portable-right-scroll/);
  const html = readFileSync('frontend/index.html', 'utf8');
  assert.match(html, /dashboard\.css\?v=20261125-portable-right-scroll/);
});
