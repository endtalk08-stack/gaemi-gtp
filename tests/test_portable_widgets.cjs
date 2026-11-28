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
  assert.equal(w.document.body.classList.contains('left-plugin-open'), true);
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
  assert.match(css, /\.gnw-root\s*\{[^}]*max-height:\s*calc\(100vh - 150px\)/s, 'center widget layout keeps its original height rule');
  const leftSlot = css.match(/#leftMarketSidebar > \.flex-1\.overflow-y-auto > \[data-portable-widget-slot="left"\]\s*\{([^}]*)\}/);
  assert.ok(leftSlot, 'left sidebar slot lets the outer sidebar own scrolling');
  assert.match(leftSlot[1], /max-height:\s*none\s*!important/);
  assert.match(leftSlot[1], /overflow:\s*visible\s*!important/);
  const leftRoot = css.match(/#leftMarketSidebar > \.flex-1\.overflow-y-auto > \[data-portable-widget-slot="left"\] \.central-widget-card--news-feed \.gnw-root\s*\{([^}]*)\}/);
  assert.ok(leftRoot, 'left sidebar news content uses natural height');
  assert.match(leftRoot[1], /max-height:\s*none/);
  assert.match(leftRoot[1], /overflow:\s*visible/);
  assert.match(leftRoot[1], /scrollbar-gutter:\s*auto/);
});


test('right panel constrains only vertical scrolling and keeps the moved news widget at full panel width', () => {
  const panelCss = readFileSync('frontend/pages/panel-workspace/panel-workspace.css', 'utf8');
  const override = panelCss.match(/#rightPanelContent:has\(#rightPanelTabView-dashboard\):has\(> \[data-portable-widget-slot="right"\] > \[data-central-widget-id\]\)\s*\{([^}]*)\}/);
  assert.ok(override, 'right panel scroll override matches a real moved widget regardless of tab visibility');
  assert.match(override[1], /display:\s*flex/);
  assert.match(override[1], /flex-direction:\s*column/);
  assert.match(override[1], /min-height:\s*0/);
  assert.match(override[1], /overflow-y:\s*auto\s*!important/);
  assert.match(override[1], /overflow-x:\s*hidden\s*!important/);
  assert.match(override[1], /scrollbar-gutter:\s*stable/);

  const slot = panelCss.match(/#rightPanelContent > \[data-portable-widget-slot="right"\]\s*\{([^}]*)\}/);
  assert.ok(slot, 'right widget slot uses natural content height');
  assert.match(slot[1], /flex:\s*0 0 auto/);
  assert.match(slot[1], /width:\s*100%/);
  assert.match(slot[1], /max-width:\s*100%/);
  assert.match(slot[1], /max-height:\s*none/);
  assert.match(slot[1], /overflow:\s*visible/);

  const newsCss = readFileSync('frontend/widgets/news/news-widget.css', 'utf8');
  const root = newsCss.match(/#rightPanelContent > \[data-portable-widget-slot="right"\] \.central-widget-card--news-feed \.gnw-root\s*\{([^}]*)\}/);
  assert.ok(root, 'news content uses its natural height inside the panel slot');
  assert.match(root[1], /width:\s*100%/);
  assert.match(root[1], /max-height:\s*none/);
  assert.match(root[1], /overflow:\s*visible/);
  assert.match(newsCss, /\.gnw-root\s*\{[^}]*max-height:\s*calc\(100vh - 150px\)/s, 'center/left news widget keeps its original viewport behavior');

  const shellCss = readFileSync('frontend/shell/right-panel/right-panel.css', 'utf8');
  assert.match(shellCss, /flex:\s*0 0 var\(--right-panel-width\)/);
  assert.match(shellCss, /width:\s*var\(--right-panel-width\)/, 'right panel outer width remains unchanged');

  const dashboardCss = readFileSync('frontend/pages/dashboard/dashboard.css', 'utf8');
  assert.match(dashboardCss, /panel-workspace\/panel-workspace\.css\?v=20261125-right-news-height-scroll-v2/);
  const html = readFileSync('frontend/index.html', 'utf8');
  assert.match(html, /dashboard\.css\?v=20261125-right-news-height-scroll-v2/);
  assert.match(html, /news-widget\.css\?v=20261128-company-intro-v1/);
});


test('left sidebar keeps all market tabs and restores moved widgets after refresh', () => {
  const html = readFileSync('frontend/index.html', 'utf8');
  const boot = (window) => {
    window.setInterval = () => 0;
    window.fetch = async () => ({ ok: false });
    window.eval(readFileSync('frontend/widgets/catalog/catalog.js', 'utf8'));
    window.eval(readFileSync('frontend/widgets/industry/industry-widget.js', 'utf8'));
    window.eval(readFileSync('frontend/shell/center-chat/widget-dock/widget-dock.js', 'utf8'));
    const dock = window.GaemiGTPWidgetDock;
    dock.initialize();
    return dock;
  };

  const firstDom = new JSDOM(html, { url: 'https://example.test', runScripts: 'outside-only' });
  const first = firstDom.window;
  const firstDock = boot(first);
  assert.equal(firstDock.add('news-feed'), true);
  assert.equal(firstDock.move('news-feed', 'left'), true);
  const savedPlacements = first.localStorage.getItem('gaemiGTP_widget_placements_v1');
  assert.equal(JSON.parse(savedPlacements)['news-feed'], 'left');
  assert.deepEqual(JSON.parse(first.localStorage.getItem('gaemiGTP_central_widget_dock_v1')), ['news-feed']);
  firstDom.window.close();

  // Simulate a partial/legacy save where the active-ID key is missing but the
  // moved widget's placement record survived.
  const secondDom = new JSDOM(html, { url: 'https://example.test', runScripts: 'outside-only' });
  const second = secondDom.window;
  second.localStorage.setItem('gaemiGTP_widget_placements_v1', savedPlacements);
  const secondDock = boot(second);

  assert.deepEqual(Array.from(secondDock.getActiveIds()), ['news-feed']);
  assert.equal(secondDock.getPlacement('news-feed'), 'left');
  const widget = second.document.querySelector('[data-central-widget-id="news-feed"]');
  assert.ok(widget);
  assert.equal(widget.parentElement, second.document.querySelector('[data-portable-widget-slot="left"]'));
  assert.equal(second.document.querySelectorAll('[data-central-widget-id="news-feed"]').length, 1);

  const tabs = Array.from(second.document.querySelectorAll('#rightInfoTabs [data-info-tab-action]'))
    .map(button => button.dataset.infoTabAction);
  assert.deepEqual(tabs, ['realtime', 'industry', 'value']);
  assert.ok(second.document.querySelector('#leftMarketSidebar #marketRankingList'));
  assert.ok(second.document.querySelector('#leftMarketSidebar #marketIndustryWidgetSlot'));

  const marketSidebar = readFileSync('frontend/shell/left-market-sidebar/market-sidebar.js', 'utf8');
  assert.equal(marketSidebar.includes('시장 시세'), false);
  assert.match(marketSidebar, /const showListHeading = tab === 'value'/);
  assert.match(html, /market-sidebar\.js\?v=20261128-kis-night-futures-v1/);
  assert.match(html, /widget-dock\.js\?v=20261128-schedule-widget-v1/);
  secondDom.window.close();
});


test('KIS night futures widget displays the live quote and connection state from the shared relay event', () => {
  const dom = new JSDOM(
    '<main id="mainContent"><section id="centralWidgetDock"><div id="centralWidgetDockBody"></div></section></main>',
    { url: 'https://example.test', runScripts: 'outside-only' }
  );
  const w = dom.window;
  w.setInterval = () => 0;
  w.fetch = async () => ({ ok: false });
  w.eval(readFileSync('frontend/widgets/catalog/catalog.js', 'utf8'));
  w.eval(readFileSync('frontend/shell/center-chat/widget-dock/widget-dock.js', 'utf8'));
  const dock = w.GaemiGTPWidgetDock;
  dock.initialize();
  assert.equal(dock.add('night-futures'), true);
  const card = w.document.querySelector('[data-central-widget-id="night-futures"]');
  assert.ok(card);
  assert.equal(card.querySelector('[data-night-futures-price]').textContent, '—');
  assert.equal(card.querySelector('[data-night-futures-status]').textContent, '연결 대기');

  w.dispatchEvent(new w.CustomEvent('gaemi:night-futures-quote', {
    detail: {
      price: 352.75, change_pct: 0.42, received_at_ms: Date.now(),
      connected: true, status: 'live', source: 'kis:websocket'
    }
  }));
  assert.equal(card.querySelector('[data-night-futures-price]').textContent, '352.75');
  assert.equal(card.querySelector('[data-night-futures-change]').textContent, '+0.42%');
  assert.equal(card.querySelector('[data-night-futures-status]').textContent, '실시간');

  w.dispatchEvent(new w.CustomEvent('gaemi:night-futures-quote', {
    detail: { connected: false, status: 'disconnected' }
  }));
  assert.equal(card.querySelector('[data-night-futures-status]').textContent, '연결 끊김');

  w.dispatchEvent(new w.CustomEvent('gaemi:night-futures-quote', {
    detail: { connected: false, status: 'credentials_missing' }
  }));
  assert.equal(card.querySelector('[data-night-futures-status]').textContent, 'API 키 미설정');
  dom.window.close();
});

test('KIS night futures widget keeps the closing price outside trading hours (never a dash)', () => {
  const dom = new JSDOM(
    '<main id="mainContent"><section id="centralWidgetDock"><div id="centralWidgetDockBody"></div></section></main>',
    { url: 'https://example.test', runScripts: 'outside-only' }
  );
  const w = dom.window;
  w.setInterval = () => 0;
  w.fetch = async () => ({ ok: false });
  w.eval(readFileSync('frontend/widgets/catalog/catalog.js', 'utf8'));
  w.eval(readFileSync('frontend/shell/center-chat/widget-dock/widget-dock.js', 'utf8'));
  const dock = w.GaemiGTPWidgetDock;
  dock.initialize();
  dock.add('night-futures');
  const card = w.document.querySelector('[data-central-widget-id="night-futures"]');
  w.dispatchEvent(new w.CustomEvent('gaemi:night-futures-quote', {
    detail: { price: 760.05, change_pct: 0.38, received_at_ms: Date.now() - 600000,
      connected: true, status: 'closed', source: 'kis:rest-night' }
  }));
  assert.equal(card.querySelector('[data-night-futures-price]').textContent, '760.05');
  assert.equal(card.querySelector('[data-night-futures-change]').textContent, '+0.38%');
  assert.equal(card.querySelector('[data-night-futures-status]').textContent, '마감');
  assert.ok(card.querySelector('[data-night-futures-change]').classList.contains('central-widget-card__kospi-change--up'));
  // A dropped connection afterwards keeps the price on screen.
  w.dispatchEvent(new w.CustomEvent('gaemi:night-futures-quote', { detail: { connected: false, status: 'disconnected' } }));
  assert.equal(card.querySelector('[data-night-futures-price]').textContent, '760.05');
  dom.window.close();
});

test('주요일정 widget renders the same weekly table as the sidebar', () => {
  const dom = new JSDOM(
    '<main id="mainContent"><section id="centralWidgetDock"><div id="centralWidgetDockBody"></div></section></main>',
    { url: 'https://example.test', runScripts: 'outside-only' }
  );
  const w = dom.window;
  w.setInterval = () => 0;
  w.fetch = async () => ({ ok: false });
  w.eval(readFileSync('frontend/widgets/catalog/catalog.js', 'utf8'));
  w.eval(readFileSync('frontend/widgets/schedule/schedule.js', 'utf8'));
  w.eval(readFileSync('frontend/shell/center-chat/widget-dock/widget-dock.js', 'utf8'));
  const dock = w.GaemiGTPWidgetDock;
  dock.initialize();
  assert.equal(dock.add('schedule'), true);
  const card = w.document.querySelector('[data-central-widget-id="schedule"]');
  assert.equal(card.querySelector('.gsc-placeholder').textContent, '주요일정이 여기에 표시됩니다');
  w.GaemiGTPSchedule.setItems([
    { time: '2026-11-25T15:00:00Z', title: '신규주택 매매건수 발표', country: 'US', actual: '70.1만 건', forecast: '65만 건', previous: '67.6만 건' },
    { time: '2026-12-01T15:00:00Z', title: 'ISM 제조업 구매관리자지수 발표', country: 'US' },
  ]);
  assert.deepEqual([...card.querySelectorAll('.gsc-week__title')].map(n => n.textContent), ['11월 4주차', '12월 1주차']);
  assert.equal(card.querySelector('.gsc-num--actual').textContent, '70.1만 건');
  assert.ok(card.querySelector('.gsc-num--actual').classList.contains('gsc-num--up'));
  assert.equal(card.querySelector('.gsc-pending').textContent, '오전 12시 발표 예정');
  assert.equal(card.querySelector('.gsc-date').textContent, '26일 (목)');
  dom.window.close();
});
