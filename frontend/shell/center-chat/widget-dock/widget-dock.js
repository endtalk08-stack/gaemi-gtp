/* Central Widget Dock — presentation shell for data-backed analysis widgets only. */
(function () {
  'use strict';

  const STATE_KEY = 'gaemiGTP_central_widget_dock_v1';
  const PLACEMENT_KEY = 'gaemiGTP_widget_placements_v1';
  const DRAG_THRESHOLD = 8;
  let activeIds = [];
  let dragState = null;
  const cards = new Map();
  const placements = new Map();

  function readPlacements() {
    try {
      const value = JSON.parse(localStorage.getItem(PLACEMENT_KEY) || '{}');
      if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
      return Object.fromEntries(Object.entries(value).filter(([id, where]) =>
        catalog()[id] && ['left', 'center', 'right'].includes(where)));
    } catch (_) { return {}; }
  }
  function savePlacements() {
    try { localStorage.setItem(PLACEMENT_KEY, JSON.stringify(Object.fromEntries(placements))); } catch (_) {}
  }

  function ensurePortableSlot(where, id) {
    if (where === 'left' && id === 'industry') {
      const industrySlot = document.getElementById('marketIndustryWidgetSlot');
      if (industrySlot) return industrySlot;
    }
    const host = where === 'left'
      ? document.getElementById('leftMarketSidebar')
      : document.getElementById('rightPanelContent') || document.getElementById('rightPanel');
    if (!host) return null;
    let slot = host.querySelector('[data-portable-widget-slot="' + where + '"]');
    if (!slot) {
      slot = document.createElement('div');
      slot.dataset.portableWidgetSlot = where;
      slot.style.cssText = 'display:flex;flex-direction:column;gap:8px;padding:8px;min-width:0;flex-shrink:0;max-height:70vh;overflow:auto';
      if (where === 'left') {
        const scroll = host.querySelector('.flex-1.overflow-y-auto') || host;
        const industrySlot = document.getElementById('marketIndustryWidgetSlot');
        if (industrySlot?.parentElement === scroll) industrySlot.after(slot);
        else scroll.appendChild(slot);
      } else {
        // The legacy dashboard tab occupies a full viewport, even when empty.
        // Keep portable widgets above it in the panel's own scrolling region.
        host.prepend(slot);
      }
    }
    if (where === 'right') {
      slot.style.maxHeight = 'none';
      slot.style.overflow = 'visible';
      if (host.firstElementChild !== slot) host.prepend(slot);
    }
    return slot;
  }

  function moveWidget(id, where) {
    if (!activeIds.includes(id) || !['left', 'center', 'right'].includes(where)) return false;
    const card = cards.get(id);
    if (!card) return false;
    const target = where === 'center' ? body() : ensurePortableSlot(where, id);
    if (!target) return false;

    if (where === 'left') {
      document.body.classList.remove('left-home-open', 'left-context-open');
      if (window.innerWidth < 1024) document.body.classList.remove('right-panel-open', 'right-panel-maximized');
      document.body.classList.add('left-market-open');
    } else if (where === 'right') {
      if (window.innerWidth < 1024) {
        document.body.classList.remove('left-market-open', 'left-home-open', 'left-context-open', 'left-plugin-open');
      }
      document.body.classList.add('right-panel-open');
    } else if (window.innerWidth < 1024) {
      document.body.classList.remove(
        'left-market-open', 'left-home-open', 'left-context-open', 'left-plugin-open',
        'right-panel-open', 'right-panel-maximized'
      );
    }

    target.appendChild(card);
    placements.set(id, where);
    savePlacements();
    saveState();
    if (where === 'left' && id === 'industry') {
      window.GaemiGTPMarketSidebar?.selectIndustryTab?.();
    }
    window.GaemiGTPWorkspaceShellState?.apply?.();
    const dock = root();
    if (dock) dock.dataset.count = String(body().children.length);
    window.dispatchEvent(new CustomEvent('gaemi:widget-placement', { detail: { id, where } }));
    return true;
  }

  function addCardActions(card, id) {
    if (id !== 'industry' || card.querySelector('[data-central-widget-remove="industry"]')) return;
    const close = document.createElement('button');
    close.type = 'button';
    close.textContent = '×';
    close.className = 'central-widget-card__close central-widget-card__close--overlay';
    close.dataset.centralWidgetRemove = 'industry';
    close.setAttribute('aria-label', '업종 위젯 삭제');
    close.addEventListener('click', () => remove(id));
    card.appendChild(close);
  }

  function dropWhereAt(x, y) {
    const point = document.elementFromPoint?.(x, y);
    const zone = point?.closest?.('[data-widget-drop-zone]');
    return zone?.dataset.widgetDropZone || '';
  }

  function highlightDropZone(where) {
    document.querySelectorAll('[data-widget-drop-zone]').forEach(node => {
      node.classList.toggle('is-widget-drop-target', Boolean(where) && node.dataset.widgetDropZone === where);
    });
  }

  function dragSource(event) {
    const origin = event.target?.nodeType === 1 ? event.target : event.target?.parentElement;
    if (!origin?.closest) return null;
    const explicit = origin.closest('[data-widget-drag-handle]');
    if (explicit) return { id: explicit.dataset.widgetDragHandle, handle: explicit };

    const card = origin.closest('[data-central-widget-id]');
    if (!card || origin.closest('button,a,input,textarea,select')) return null;
    const bounds = card.getBoundingClientRect();
    if (event.clientY > bounds.top + Math.min(34, bounds.height)) return null;
    return { id: card.dataset.centralWidgetId, handle: card };
  }

  function clearWidgetDrag() {
    dragState = null;
    document.body.classList.remove('gaemi-widget-dragging');
    highlightDropZone('');
  }

  function onWidgetPointerDown(event) {
    if (event.pointerType === 'mouse' && event.button !== 0) return;
    const source = dragSource(event);
    if (!source || !catalog()[source.id]) return;
    dragState = {
      id: source.id,
      handle: source.handle,
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      dragging: false
    };
  }

  function onWidgetPointerMove(event) {
    if (!dragState || dragState.pointerId !== event.pointerId) return;
    const dx = event.clientX - dragState.startX;
    const dy = event.clientY - dragState.startY;
    if (!dragState.dragging && Math.hypot(dx, dy) < DRAG_THRESHOLD) return;
    dragState.dragging = true;
    document.body.classList.add('gaemi-widget-dragging');
    event.preventDefault();
    highlightDropZone(dropWhereAt(event.clientX, event.clientY));
  }

  function onWidgetPointerUp(event) {
    if (!dragState || dragState.pointerId !== event.pointerId) return;
    const current = dragState;
    if (current.dragging) {
      const where = dropWhereAt(event.clientX, event.clientY);
      if (where && (where !== 'left' || activeIds.includes(current.id))) {
        if (!activeIds.includes(current.id)) add(current.id);
        moveWidget(current.id, where);
        if (where === 'center') window.enterChatWorkspace?.();
      }
      event.preventDefault();
    }
    clearWidgetDrag();
  }

  function initializeWidgetDragging() {
    document.getElementById('leftMarketSidebar')?.setAttribute('data-widget-drop-zone', 'left');
    document.getElementById('mainContent')?.setAttribute('data-widget-drop-zone', 'center');
    document.getElementById('rightPanel')?.setAttribute('data-widget-drop-zone', 'right');
    document.addEventListener('pointerdown', onWidgetPointerDown, true);
    document.addEventListener('pointermove', onWidgetPointerMove, true);
    document.addEventListener('pointerup', onWidgetPointerUp, true);
    document.addEventListener('pointercancel', clearWidgetDrag, true);
  }
  let captionHeadline = '';
  let chartSymbol = '';
  let chartRequest = 0;
  let inlineChart = null;
  let chartRefreshTimer = null;
  let chartController = null;
  const chartDataCache = new Map();
  const CHART_HISTORY_TTL = 300000;
  let chartRetryDelay = 15000;

  function catalog() { return window.GaemiGTPWidgetCatalog || {}; }
  function escapeHtml(value) {
    return String(value || '')
      .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;').replaceAll("'", '&#039;');
  }
  function root() { return document.getElementById('centralWidgetDock'); }
  function body() { return document.getElementById('centralWidgetDockBody'); }

  function readState() {
    let savedIds = null;
    try {
      const saved = localStorage.getItem(STATE_KEY);
      const value = saved === null ? null : JSON.parse(saved);
      if (Array.isArray(value)) savedIds = value;
    } catch (_) {}
    // If the installed-ID record is missing or unreadable, recover from saved
    // placements. A valid empty installed-ID list remains authoritative so a
    // deliberately removed widget cannot be resurrected by an old placement.
    const sourceIds = savedIds === null ? Object.keys(readPlacements()) : savedIds;
    return sourceIds
      .map(id => (id === 'why-up' || id === 'kospi') ? 'qqq' : id)
      .filter((id, index, list) => id !== 'chart' && catalog()[id] && list.indexOf(id) === index);
  }
  function saveState() {
    try { localStorage.setItem(STATE_KEY, JSON.stringify(activeIds)); } catch (_) {}
  }

  // Browser-only chart cache: max 120 authenticated relay snapshots, no API or DB calls.
  const qqqPoints = [];
  let qqqLastReceivedMs = 0;
  let qqqSessionKey = '';
  let qqqCurrent = null;
  const marketEtfs = Object.fromEntries(['SPY', 'DIA'].map(symbol => [symbol, {
    points: [], lastReceivedMs: 0, sessionKey: '', current: null
  }]));
  let marketEtfSnapshotAt = 0;
  const MAX_QQQ_POINTS = 120;
  const QQQ_REASON_REFRESH_MS = 300000;
  let qqqReasons = [];
  let qqqReasonRefreshAt = 0;

  function easternTradingWindow(timestampMs) {
    // These labels describe the US/Eastern clock window, not a verified exchange session.
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/New_York',
      weekday: 'short', year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', hourCycle: 'h23'
    }).formatToParts(new Date(timestampMs));
    const byType = Object.fromEntries(parts.map(part => [part.type, part.value]));
    const minuteOfDay = Number(byType.hour) * 60 + Number(byType.minute);
    const key = [byType.year, byType.month, byType.day].join('-');
    const weekend = byType.weekday === 'Sat' || byType.weekday === 'Sun';
    let period = '장외';
    if (!weekend) {
      if (minuteOfDay >= 4 * 60 && minuteOfDay < 9 * 60 + 30) period = '프리';
      else if (minuteOfDay >= 9 * 60 + 30 && minuteOfDay < 16 * 60) period = '정규';
      else if (minuteOfDay >= 16 * 60 && minuteOfDay < 20 * 60) period = '애프터';
    }
    return { period, key: key + ':' + period };
  }


  function refreshQqqReasons() {
    const reasonUrl = root()?.dataset.qqqReasonUrl;
    if (!reasonUrl || document.hidden || Date.now() < qqqReasonRefreshAt) return;
    qqqReasonRefreshAt = Date.now() + QQQ_REASON_REFRESH_MS;
    fetch(reasonUrl, { signal: AbortSignal.timeout(8000) })
      .then(response => response.ok ? response.json() : null)
      .then(data => { qqqReasons = data?.ok && Array.isArray(data.items) ? data.items : []; })
      .catch(() => { qqqReasons = []; })
      .finally(updateQqqViews);
  }

  function updateQqqReason(card, quote, fresh) {
    const node = card.querySelector('[data-qqq-reason]');
    if (!node) return;
    const session = fresh && Number.isFinite(quote?.change_pct) && quote.change_pct > 0
      ? easternTradingWindow(quote.received_at_ms) : null;
    if (!session || session.period === '장외') {
      node.hidden = true;
      node.textContent = '';
      node.removeAttribute('href');
      node.removeAttribute('title');
      return;
    }
    const reason = qqqReasons.find(item => Number.isFinite(item?.publishedAt)
      && item.publishedAt <= quote.received_at_ms
      && easternTradingWindow(item.publishedAt).key === session.key
      && typeof item.text === 'string' && item.text.trim()
      && typeof item.url === 'string' && item.url.startsWith('https://'));
    node.hidden = !reason;
    if (!reason) {
      node.textContent = '';
      node.removeAttribute('href');
      node.removeAttribute('title');
      refreshQqqReasons();
      return;
    }
    if (node.textContent !== reason.text) node.textContent = reason.text;
    node.href = reason.url;
    node.title = reason.text + ' · ' + reason.source;
    refreshQqqReasons();
  }

  function drawQqqChart(card, chartPoints = qqqPoints) {
    const line = card.querySelector('[data-kospi-sparkline]');
    const fill = card.querySelector('[data-kospi-sparkline-fill]');
    if (!line || !fill) return;
    if (chartPoints.length < 2) {
      line.setAttribute('points', '');
      fill.setAttribute('points', '');
      return;
    }
    const lows = chartPoints.map(point => point.price);
    const lowest = Math.min(...lows);
    const highest = Math.max(...lows);
    const span = highest - lowest;
    const points = chartPoints.map((point, index) => {
      const x = 1 + (index / (chartPoints.length - 1)) * 70;
      const y = span === 0 ? 14 : 25 - ((point.price - lowest) / span) * 22;
      return x.toFixed(1) + ',' + y.toFixed(1);
    }).join(' ');
    line.setAttribute('points', points);
    fill.setAttribute('points', '1,27 ' + points + ' 71,27');
  }

  function isQqqQuoteFresh(quote) {
    const maxAge = quote?.source === 'kiwoom:rest' ? 65000 : 25000;
    return quote?.stale === false
      && Number.isFinite(quote.received_at_ms)
      && quote.received_at_ms <= Date.now() + 5000
      && Date.now() - quote.received_at_ms <= maxAge;
  }

  function updateQqqCard() {
    const card = cards.get('qqq');
    if (!card) return;
    const priceNode = card.querySelector('[data-kospi-price]');
    const changeNode = card.querySelector('[data-kospi-change]');
    const chartNode = card.querySelector('.central-widget-card__sparkline');
    const quote = qqqCurrent;
    const valid = quote && Number.isFinite(quote.price) && quote.price > 0;
    const fresh = valid && isQqqQuoteFresh(quote);
    const change = valid && Number.isFinite(quote.change_pct) ? quote.change_pct : null;
    card.classList.toggle('central-widget-card--qqq-muted', !fresh);
    if (priceNode) priceNode.textContent = valid
      ? quote.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
      : '—';
    changeNode.textContent = change === null ? '—' : (change > 0 ? '+' : '') + change.toFixed(2) + '%';
    changeNode.classList.toggle('central-widget-card__kospi-change--up', fresh && change > 0);
    changeNode.classList.toggle('central-widget-card__kospi-change--down', fresh && change < 0);
    chartNode?.classList.toggle('central-widget-card__sparkline--up', fresh && change !== null && change > 0);
    chartNode?.classList.toggle('central-widget-card__sparkline--down', fresh && change !== null && change < 0);
    drawQqqChart(card);
    updateQqqReason(card, quote, fresh);
  }

  function updateMarketEtfCard(symbol) {
    const card = cards.get(symbol.toLowerCase());
    if (!card) return;
    const state = marketEtfs[symbol];
    const quote = state.current;
    const recentSnapshot = quote?.source === 'kiwoom:rest'
      && quote.stale === false && Number.isFinite(quote.received_at_ms)
      && Date.now() - quote.received_at_ms >= 0
      && Date.now() - quote.received_at_ms < 1800000;
    const fresh = quote && (recentSnapshot || isQqqQuoteFresh(quote));
    const recentTick = quote && Number.isFinite(quote.price) && quote.price > 0
      && Number.isFinite(quote.received_at_ms) && quote.received_at_ms <= Date.now() + 5000
      && Date.now() - quote.received_at_ms <= 180000;
    // Muted while waiting for a new tick, but do not blank a valid recent price.
    const display = fresh || recentTick;
    const change = display && Number.isFinite(quote.change_pct) ? quote.change_pct : null;
    card.classList.toggle('central-widget-card--qqq-muted', !fresh);
    card.querySelector('[data-kospi-price]').textContent = display
      ? quote.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—';
    const changeNode = card.querySelector('[data-kospi-change]');
    changeNode.textContent = change === null ? '—' : (change > 0 ? '+' : '') + change.toFixed(2) + '%';
    changeNode.classList.toggle('central-widget-card__kospi-change--up', change > 0);
    changeNode.classList.toggle('central-widget-card__kospi-change--down', change < 0);
    const chart = card.querySelector('.central-widget-card__sparkline');
    chart.classList.toggle('central-widget-card__sparkline--up', change > 0);
    chart.classList.toggle('central-widget-card__sparkline--down', change < 0);
    drawQqqChart(card, state.points);
  }

  async function refreshMarketEtfSnapshot() {
    if (document.hidden || !Object.keys(marketEtfs).some(symbol => activeIds.includes(symbol.toLowerCase()))
        || Date.now() - marketEtfSnapshotAt < 120000) return;
    marketEtfSnapshotAt = Date.now();
    try {
      const response = await fetch('https://quotes.gaemigtp.com/market/us-etf-quotes', {
        signal: AbortSignal.timeout(20000)
      });
      if (!response.ok) return;
      const data = await response.json();
      if (!data?.ok || !Array.isArray(data.items)) return;
      for (const [symbol, state] of Object.entries(marketEtfs)) {
        const quote = data.items.find(item => item.symbol === symbol);
        if (quote && Number.isFinite(quote.price) && quote.price > 0
            && Number.isFinite(quote.change_pct) && Number.isFinite(quote.received_at_ms)
            && (!state.current || !isQqqQuoteFresh(state.current))) {
          state.current = { ...quote, stale: false, source: 'kiwoom:rest' };
          updateMarketEtfCard(symbol);
        }
      }
    } catch (_) {}
  }

  function onMarketEtfQuotes(event) {
    const items = Array.isArray(event.detail?.items) ? event.detail.items : [];
    for (const [symbol, state] of Object.entries(marketEtfs)) {
      const quote = items.find(item => item.symbol === symbol);
      if (quote && Number.isFinite(quote.price)
          && quote.price > 0 && isQqqQuoteFresh(quote)) state.current = quote;
      if (quote && Number.isFinite(quote.received_at_ms)
          && state.current && quote.received_at_ms > state.lastReceivedMs) {
        const { key } = easternTradingWindow(quote.received_at_ms);
        if (key !== state.sessionKey) {
          state.points.length = 0;
          state.sessionKey = key;
        }
        state.points.push({ receivedAt: quote.received_at_ms, price: quote.price });
        if (state.points.length > MAX_QQQ_POINTS) state.points.shift();
        state.lastReceivedMs = quote.received_at_ms;
      }
      updateMarketEtfCard(symbol);
    }
  }

  function updateMarketQqqReason() {
    const row = document.querySelector('[data-market-qqq]');
    if (!row) return;
    const quote = qqqCurrent;
    const fresh = isQqqQuoteFresh(quote);
    updateQqqReason(row, quote, fresh);
  }

  function updateQqqViews() {
    updateQqqCard();
    updateMarketQqqReason();
  }

  function onQqqQuote(event) {
    const quote = event.detail?.quote;
    if (!quote || quote.symbol !== 'QQQ' || typeof quote.price !== 'number'
      || !Number.isFinite(quote.price) || quote.price <= 0
      || typeof quote.received_at_ms !== 'number'
      || !Number.isFinite(quote.received_at_ms)
      || quote.received_at_ms > Date.now() + 5000
      || Date.now() - quote.received_at_ms > 86400000) {
      qqqCurrent = null;
      updateQqqViews();
      return;
    }
    qqqCurrent = quote;
    const fresh = isQqqQuoteFresh(quote);
    if (fresh && quote.received_at_ms > qqqLastReceivedMs) {
      const { key } = easternTradingWindow(quote.received_at_ms);
      if (key !== qqqSessionKey) {
        qqqPoints.length = 0;
        qqqSessionKey = key;
      }
      qqqPoints.push({ receivedAt: quote.received_at_ms, price: quote.price });
      if (qqqPoints.length > MAX_QQQ_POINTS) qqqPoints.shift();
      qqqLastReceivedMs = quote.received_at_ms;
    }
    updateQqqViews();
  }

  // The one-line alert widget keeps the same fixed height and text size as the search bar.
  function setNewsHeadline(value) {
    captionHeadline = typeof value === 'string' ? value.trim().slice(0, 500) : '';
    const target = cards.get('news-caption')?.querySelector('[data-news-caption-title]');
    if (target) target.textContent = captionHeadline;
  }

  function render() {
    const dock = root();
    const bodyEl = body();
    if (!dock || !bodyEl) return;
    const staging = document.createElement('div');
    staging.innerHTML = activeIds.filter(id => !cards.has(id)).map(id => {
      const meta = catalog()[id];
      if (id === 'industry') {
        return '<article class="central-widget-card central-widget-card--industry" data-central-widget-id="industry" aria-label="업종 위젯"><div data-industry-widget-target="center"></div></article>';
      }
      if (id === 'news-feed') {
        return `<article class="central-widget-card central-widget-card--news-feed" data-central-widget-id="news-feed" aria-label="뉴스 위젯">
          <section class="gnw-root" data-gnw-root aria-label="뉴스 검색과 목록"></section>
        </article>`;
      }
      if (id === 'news-caption') {
        return `<article class="central-widget-card central-widget-card--news-caption" data-central-widget-id="news-caption" aria-label="속보 위젯">
          <button type="button" class="central-widget-card__close central-widget-card__close--overlay" data-central-widget-remove="news-caption" onclick="window.GaemiGTPWidgetDock.remove('news-caption')" aria-label="속보 위젯 삭제" title="위젯 삭제"><i data-lucide="x" class="w-3 h-3"></i></button>
          <div class="central-widget-card__news-caption-title" data-news-caption-title>${escapeHtml(captionHeadline)}</div>
        </article>`;
      }
      if (id === 'qqq' || id === 'spy' || id === 'dia') {
        const isEtf = id !== 'qqq';
        const symbol = id.toUpperCase();
        return `
        <article class="central-widget-card central-widget-card--kospi central-widget-card--qqq-muted" data-central-widget-id="${escapeHtml(id)}">
          <button type="button" class="central-widget-card__close central-widget-card__close--overlay" data-central-widget-remove="${escapeHtml(id)}" onclick="window.GaemiGTPWidgetDock.remove('${escapeHtml(id)}')" aria-label="${symbol} 위젯 삭제" title="위젯 삭제">
            <i data-lucide="x" class="w-3 h-3"></i>
          </button>
          <div class="central-widget-card__kospi-title"><span>${symbol}</span><span class="central-widget-card__kospi-market-name">${id === 'spy' ? 'S&P 500' : id === 'dia' ? '다우' : '나스닥'}</span></div>
          <div class="central-widget-card__kospi-body" aria-label="${symbol} 키움 실시간 체결가 차트">
            <svg class="central-widget-card__sparkline" viewBox="0 0 72 28" preserveAspectRatio="none" aria-hidden="true">
              <defs>
                <linearGradient id="${isEtf ? id : 'kospi'}SparklineGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="currentColor" stop-opacity="0.28"></stop>
                  <stop offset="100%" stop-color="currentColor" stop-opacity="0"></stop>
                </linearGradient>
              </defs>
              <polygon data-kospi-sparkline-fill points=""></polygon>
              <polyline data-kospi-sparkline points=""></polyline>
            </svg>
            <div class="central-widget-card__kospi-copy">
              <div class="central-widget-card__kospi-row central-widget-card__kospi-market"><strong data-kospi-price>—</strong><span class="central-widget-card__kospi-change" data-kospi-change>—</span></div>
            </div>
          </div>
          ${isEtf ? '' : '<a class="central-widget-card__kospi-reason" data-qqq-reason target="_blank" rel="noopener noreferrer" hidden></a>'}
        </article>`;
      }
      if (id === 'night-futures') {
        const title = '코스피200 야간선물';
        const detail = '야간선물 원천 데이터 연결 후 시세·등락률·흐름을 표시합니다.';
        return `<article class="central-widget-card central-widget-card--kospi" data-central-widget-id="${escapeHtml(id)}">
          <button type="button" class="central-widget-card__close central-widget-card__close--overlay" data-central-widget-remove="${escapeHtml(id)}" onclick="window.GaemiGTPWidgetDock.remove('${escapeHtml(id)}')" aria-label="${escapeHtml(title)} 위젯 삭제" title="위젯 삭제"><i data-lucide="x" class="w-3 h-3"></i></button>
          <div class="central-widget-card__kospi-title">${escapeHtml(title)}</div>
          <div class="central-widget-card__market-empty">${escapeHtml(detail)}</div>
        </article>`;
      }
      return `<article class="central-widget-card" data-central-widget-id="${escapeHtml(id)}">
        <div class="central-widget-card__top">
          <div class="central-widget-card__name">${escapeHtml(meta.title)}</div>
          <button type="button" class="central-widget-card__close" data-central-widget-remove="${escapeHtml(id)}" onclick="window.GaemiGTPWidgetDock.remove('${escapeHtml(id)}')" aria-label="${escapeHtml(meta.title)} 위젯 삭제" title="위젯 삭제"><i data-lucide="x" class="w-3 h-3"></i></button>
        </div>
        <div class="central-widget-card__desc" data-central-widget-mount="${escapeHtml(id)}">${escapeHtml(meta.description)} · 데이터 준비 중</div>
      </article>`;
    }).join('');
    for (const [id, card] of cards) {
      if (!activeIds.includes(id)) { card.remove(); cards.delete(id); placements.delete(id); }
    }
    for (const card of Array.from(staging.children)) {
      const id = card.dataset.centralWidgetId;
      cards.set(id, card);
      addCardActions(card, id);
      bodyEl.appendChild(card);
      moveWidget(id, placements.get(id) || 'center');
    }
    dock.dataset.count = String(bodyEl.children.length);
    document.querySelectorAll('[data-central-widget-mount]').forEach(node => {
      window.GaemiGTPAnalysisWidgets?.mount?.(node.dataset.centralWidgetMount, node);
    });
    if (staging.querySelector('[data-gnw-root]') || cards.get('news-feed')?.dataset.newsMounted !== 'true') {
      window.GaemiGTPNewsWidget?.mount?.();
      if (cards.has('news-feed')) cards.get('news-feed').dataset.newsMounted = 'true';
    }
    window.GaemiGTPIndustryWidget?.mount?.();
    window.dispatchEvent(new CustomEvent('gaemi:widget-change'));
    if (window.lucide) window.lucide.createIcons();
    if (activeIds.includes('qqq')) updateQqqCard();
    for (const symbol of Object.keys(marketEtfs)) {
      if (activeIds.includes(symbol.toLowerCase())) updateMarketEtfCard(symbol);
    }

  }
  function setChartSelection(symbol) {
    chartSymbol = /^[A-Z0-9.\\-]{1,20}$/.test(String(symbol || '')) ? String(symbol) : '';
  }

  function renderInlineChart(target, symbol, initialChangePct = null) {
    clearTimeout(chartRefreshTimer);
    chartController?.abort();
    setChartSelection(symbol);
    if (!chartSymbol || !target) return;
    const selected = chartSymbol;
    inlineChart = { target, symbol: selected, updateLive: null };
    chartRetryDelay = 15000;
    return loadChart(target, selected, initialChangePct);
  }

  function isInlineChartActive() {
    return Boolean(inlineChart?.target?.isConnected);
  }

  function onUsLiveQuotes(event) {
    const active = inlineChart;
    if (!active?.target?.isConnected || typeof active.updateLive !== 'function') return;
    const items = event.detail?.items;
    const quote = Array.isArray(items)
      ? items.find(row => row && row.symbol === active.symbol) : null;
    active.updateLive(quote || null);
  }

  async function loadChart(target, symbol, initialChangePct) {
    if (!target || !symbol || document.hidden) return;
    clearTimeout(chartRefreshTimer);
    chartController?.abort();
    const controller = new AbortController();
    chartController = controller;
    const requestTimeout = setTimeout(() => controller.abort(), 15000);
    const current = ++chartRequest;
    let historyReady = false;
    const previous = target.querySelector('canvas');
    const status = document.createElement('div');
    status.className = 'us-daily-chart__live';
    status.setAttribute('role', 'status');
    status.style.textAlign = 'right';
    const showPercentage = (change) => {
      if (!Number.isFinite(change)) return;
      status.textContent = (change > 0 ? '+' : '') + change.toFixed(2) + '%';
      status.style.color = change > 0 ? '#ff8da1' : change < 0 ? '#38bdf8' : '#a5abb5';
    };
    showPercentage(initialChangePct);
    const updateLive = (quote) => {
      const now = Date.now();
      const fresh = quote && quote.symbol === symbol && quote.stale === false
        && Number.isFinite(quote.price) && quote.price > 0
        && Number.isFinite(quote.received_at_ms)
        && quote.received_at_ms <= now + 5000
        && now - quote.received_at_ms <= 25000;
      if (fresh) showPercentage(quote.change_pct);
    };
    if (inlineChart?.target === target && inlineChart.symbol === symbol) {
      inlineChart.updateLive = updateLive;
    }
    const loading = document.createElement('div');
    loading.textContent = '';
    if (!previous) target.replaceChildren(loading);
    try {
      const cached = chartDataCache.get(symbol);
      let data;
      let responseOk = true;
      if (cached && Date.now() - cached.at < CHART_HISTORY_TTL) {
        data = cached.data;
      } else {
        // Pages reads chart history from R2; stock analysis is handled by DigitalOcean.
        const chartOrigin = window.location.hostname === 'gaemigtp-main.pages.dev'
          ? window.location.origin : BACKEND_URL;
        const response = await fetch(chartOrigin + '/market/us-daily-chart?symbol=' +
          encodeURIComponent(symbol), { cache: 'default', signal: controller.signal });
        data = await response.json();
        responseOk = response.ok;
        if (responseOk && data.ok && Array.isArray(data.rows) && data.rows.length) {
          if (chartDataCache.size >= 20) chartDataCache.delete(chartDataCache.keys().next().value);
          chartDataCache.set(symbol, { at: Date.now(), data });
        }
      }
      if (current !== chartRequest || !target.isConnected) return;
      if (!responseOk || !data.ok || !Array.isArray(data.rows) || !data.rows.length) {
        if (!previous) loading.textContent = '일봉 데이터를 준비 중이야. 자동으로 다시 확인할게.';
        return;
      }
      historyReady = true;
      chartRetryDelay = 15000;
      loading.remove();
      const plot = document.createElement('div');
      plot.className = 'us-daily-chart__plot';
      const canvas = document.createElement('canvas');
      canvas.height = 272;
      canvas.tabIndex = 0;
      canvas.setAttribute('aria-label', data.name + ' 일봉. 마우스나 터치로 개별 봉 정보 확인');
      const tooltip = document.createElement('div');
      tooltip.className = 'us-daily-chart__tooltip';
      tooltip.hidden = true;
      tooltip.setAttribute('role', 'status');
      plot.append(canvas);
      target.replaceChildren(status, plot, tooltip);
      drawCandles(canvas, data.rows, tooltip);
    } catch (_) {
      if (current === chartRequest && target.isConnected && !previous)
        loading.textContent = '일봉 연결을 다시 확인 중이야.';
    } finally {
      clearTimeout(requestTimeout);
      if (current === chartRequest && inlineChart?.target === target && target.isConnected) {
        const nextRead = historyReady ? CHART_HISTORY_TTL : chartRetryDelay;
        if (!historyReady) chartRetryDelay = Math.min(60000, chartRetryDelay * 2);
        chartRefreshTimer = setTimeout(() => {
          if (inlineChart?.target !== target || !target.isConnected) return;
          if (document.hidden) return;
          return loadChart(target, symbol, initialChangePct);
        }, nextRead);
      }
    }
  }


  function drawCandles(canvas, input, tooltip) {
    const valid = input.filter(row =>
      ['open', 'high', 'low', 'close'].every(key => Number.isFinite(Number(row[key])) && Number(row[key]) > 0));
    const rows = valid.slice(-65);
    if (!rows.length) return;
    const width = Math.max(320, canvas.getBoundingClientRect().width || 560);
    const height = 272;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    canvas.style.height = height + 'px';
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.scale(ratio, ratio);
    const left = 8, right = 8, top = 10, priceBottom = 205, volumeTop = 222, volumeBottom = 262;
    const chartWidth = width - left - right;
    const highs = rows.map(row => Number(row.high));
    const lows = rows.map(row => Number(row.low));
    const hi = Math.max(...highs), lo = Math.min(...lows);
    const padding = Math.max((hi - lo) *0.08, 0.01);
    const min = lo - padding, max = hi + padding;
    const y = value => top + (max - value) / (max - min) * (priceBottom - top);
    const step = chartWidth / rows.length, candleWidth = Math.max(2, Math.min(10, step * 0.65));
    const volMax = Math.max(1, ...rows.map(row => Number(row.volume) || 0));
    rows.forEach((row, index) => {
      const x = left + step * (index + 0.5);
      const open = Number(row.open), close = Number(row.close);
      ctx.strokeStyle = ctx.fillStyle = close >= open ? '#e44f64' : '#3987e4';
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(x, y(Number(row.high))); ctx.lineTo(x, y(Number(row.low))); ctx.stroke();
      const a = y(open), b = y(close);
      ctx.fillRect(x - candleWidth / 2, Math.min(a,b), candleWidth, Math.max(1.5, Math.abs(a-b)));
      const volHeight = (Number(row.volume) || 0) / volMax * (volumeBottom - volumeTop);
      ctx.fillStyle = '#50545c';
      ctx.fillRect(x - candleWidth / 2, volumeBottom - volHeight, candleWidth, volHeight);
    });

    const price = value => '$' + Number(value).toLocaleString('en-US', {
      minimumFractionDigits: 2, maximumFractionDigits: 2
    });
    function showCandle(index) {
      if (index < 0 || index >= rows.length || !canvas.isConnected) return;
      const row = rows[index];
      const fields = [
        ['시가', price(row.open)], ['고가', price(row.high)],
        ['저가', price(row.low)], ['종가', price(row.close)],
        ['거래량', row.volume == null ? '—' : Number(row.volume).toLocaleString('ko-KR') + '주']
      ];
      tooltip.replaceChildren();
      const dateEl = document.createElement('div');
      dateEl.className = 'us-daily-chart__tooltip-date';
      dateEl.textContent = row.date;
      const grid = document.createElement('div');
      grid.className = 'us-daily-chart__tooltip-grid';
      fields.forEach(([name, value]) => {
        const item = document.createElement('div');
        const key = document.createElement('span');
        key.textContent = name;
        const val = document.createElement('strong');
        val.textContent = value;
        item.append(key, val);
        grid.appendChild(item);
      });
      tooltip.append(dateEl, grid);
      tooltip.hidden = false;
      const hostWidth = canvas.parentElement?.clientWidth || width;
      const centerX = left + step * (index + 0.5);
      const desiredLeft = centerX - tooltip.offsetWidth / 2;
      tooltip.style.left = Math.round(Math.min(Math.max(0, desiredLeft), Math.max(0, hostWidth - tooltip.offsetWidth))) + 'px';
    }
    function candleIndex(event) {
      const bounds = canvas.getBoundingClientRect();
      const x = (event.clientX - bounds.left) * (width / bounds.width);
      if (x < left || x > width - right) return -1;
      return Math.min(rows.length - 1, Math.max(0, Math.floor((x - left) / step)));
    }
    canvas.addEventListener('pointermove', event => {
      if (event.pointerType === 'mouse' || event.pointerType === 'pen') {
        const index = candleIndex(event);
        if (index >= 0) showCandle(index);
        else tooltip.hidden = true;
      }
    });
    canvas.addEventListener('pointerleave', event => {
      if (event.pointerType !== 'touch') tooltip.hidden = true;
    });
    // Touch devices: tap a candle to pin its details until the next tap.
    canvas.addEventListener('pointerdown', event => {
      if (event.pointerType !== 'mouse') {
        const index = candleIndex(event);
        if (index >= 0) showCandle(index);
      }
    });
    canvas.addEventListener('keydown', event => {
      if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
      event.preventDefault();
      const active = Number(canvas.dataset.selectedIndex);
      const index = Number.isFinite(active)
        ? Math.min(rows.length - 1, Math.max(0, active + (event.key === 'ArrowRight' ? 1 : -1)))
        : rows.length - 1;
      canvas.dataset.selectedIndex = String(index);
      showCandle(index);
    });
    canvas.addEventListener('blur', () => { tooltip.hidden = true; });
    return { width, left, right, top, priceBottom, min, max };
  }

  function add(id) {
    if (id === 'chart' || !catalog()[id] || activeIds.includes(id)) return false;
    activeIds.push(id);
    if (!placements.has(id)) placements.set(id, 'center');
    savePlacements();
    saveState();
    if (id === 'qqq') window.dispatchEvent(new CustomEvent('gaemi:qqq-placement'));
    if (id === 'spy' || id === 'dia') {
      window.dispatchEvent(new CustomEvent('gaemi:market-widget-placement'));
      void refreshMarketEtfSnapshot();
    }
    render();
    window.GaemiGTPPluginSidebar?.render?.();
    return true;
  }
  function remove(id) {
    const next = activeIds.filter(item => item !== id);
    const changed = next.length !== activeIds.length;
    activeIds = next;
    if (changed) {
      placements.delete(id);
      savePlacements();
      saveState();
      render();
      if (id === 'qqq') window.dispatchEvent(new CustomEvent('gaemi:qqq-placement'));
      if (id === 'spy' || id === 'dia') window.dispatchEvent(new CustomEvent('gaemi:market-widget-placement'));
      window.GaemiGTPPluginSidebar?.render?.();
    }
    return changed;
  }
  function initialize() {
    const dock = root();
    if (!dock || dock.dataset.bound === 'true') return;
    dock.dataset.bound = 'true';
    initializeWidgetDragging();
    window.addEventListener('pagehide', () => {
      savePlacements();
      saveState();
    });
    Object.entries(readPlacements()).forEach(([id, where]) => placements.set(id, where));
    activeIds = readState(); render();
    // The plugin sidebar can initialize before the dock restores its saved widgets.
    // Re-sync its add/remove labels after the dock state is ready.
    window.GaemiGTPPluginSidebar?.render?.();
    document.addEventListener('visibilitychange', () => {
      const active = inlineChart;
      if (!document.hidden && active?.target?.isConnected)
        loadChart(active.target, active.symbol, null);
    });
    window.addEventListener('gaemi:qqq-quote', onQqqQuote);
    window.addEventListener('gaemi:market-etf-quotes', onMarketEtfQuotes);
    document.addEventListener('visibilitychange', refreshMarketEtfSnapshot);
    setInterval(refreshMarketEtfSnapshot, 120000);
    void refreshMarketEtfSnapshot();
    window.addEventListener('gaemi:us-live-quotes', onUsLiveQuotes);
    // Each card X button calls the same remove() action directly.
  }
  document.addEventListener('DOMContentLoaded', initialize);
  window.GaemiGTPWidgetDock = {
    initialize, add, remove, move: moveWidget,
    getActiveIds: () => [...activeIds],
    getPlacement: id => placements.get(id) || 'center',
    setNewsHeadline, isActive: id => activeIds.includes(id),
    setChartSelection, renderInlineChart, isInlineChartActive, updateMarketQqqReason
  };
}());

