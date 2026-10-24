/* Central Widget Dock — presentation shell for data-backed analysis widgets only. */
(function () {
  'use strict';

  const STATE_KEY = 'gaemiGTP_central_widget_dock_v1';
  let activeIds = [];

  function catalog() { return window.GaemiGTPWidgetCatalog || {}; }
  function escapeHtml(value) {
    return String(value || '')
      .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;').replaceAll("'", '&#039;');
  }
  function root() { return document.getElementById('centralWidgetDock'); }
  function body() { return document.getElementById('centralWidgetDockBody'); }

  function readState() {
    try {
      const saved = localStorage.getItem(STATE_KEY);
      if (saved === null) return ['qqq'];
      const value = JSON.parse(saved);
      if (!Array.isArray(value)) return ['qqq'];
      // 이전 버전의 코스피 위젯 ID를 새 명확한 ID로 한 번만 이관한다.
      return value
        .map(id => (id === 'why-up' || id === 'kospi') ? 'qqq' : id)
        .filter((id, index, list) => catalog()[id] && list.indexOf(id) === index);
    } catch (_) { return []; }
  }
  function saveState() {
    try { localStorage.setItem(STATE_KEY, JSON.stringify(activeIds)); } catch (_) {}
  }

  // Browser-only chart cache: max 120 authenticated relay snapshots, no API or DB calls.
  const qqqPoints = [];
  let qqqHistory = [];
  let qqqHistoryDate = '';
  let qqqHistoryClose = null;
  let qqqHistoryChange = null;
  let qqqHistoryRequest = null;
  let qqqLastReceivedMs = 0;
  let qqqSessionKey = '';
  let qqqCurrent = null;
  const MAX_QQQ_POINTS = 120;

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

  function drawQqqChart(card) {
    const line = card.querySelector('[data-kospi-sparkline]');
    const fill = card.querySelector('[data-kospi-sparkline-fill]');
    if (!line || !fill) return;
    // History remains visible through weekends/restarts; live FE prices extend it.
    const series = qqqHistory.concat(qqqPoints);
    if (series.length < 2) {
      line.setAttribute('points', '');
      fill.setAttribute('points', '');
      return;
    }
    const lows = series.map(point => point.price);
    const lowest = Math.min(...lows);
    const highest = Math.max(...lows);
    const span = highest - lowest;
    const points = series.map((point, index) => {
      const x = 1 + (index / (series.length - 1)) * 70;
      const y = span === 0 ? 14 : 25 - ((point.price - lowest) / span) * 22;
      return x.toFixed(1) + ',' + y.toFixed(1);
    }).join(' ');
    line.setAttribute('points', points);
    fill.setAttribute('points', '1,27 ' + points + ' 71,27');
  }

  function updateQqqCard() {
    const card = body()?.querySelector('[data-central-widget-id="qqq"]');
    if (!card) return;
    const priceNode = card.querySelector('[data-kospi-price]');
    const pctNode = card.querySelector('[data-kospi-change]');
    const reasonNode = card.querySelector('.central-widget-card__kospi-reason span');
    const chartNode = card.querySelector('.central-widget-card__sparkline');
    const quote = qqqCurrent;
    const quoteValid = quote && Number.isFinite(quote.price) && quote.price > 0;
    const fresh = quoteValid && !quote.stale && Date.now() - quote.received_at_ms <= 25000;
    const hasHistory = Number.isFinite(qqqHistoryClose) && qqqHistoryClose > 0
      && qqqHistory.length >= 2;
    const price = fresh ? quote.price : hasHistory ? qqqHistoryClose : null;
    const percent = fresh && Number.isFinite(quote.change_pct)
      ? quote.change_pct : hasHistory ? qqqHistoryChange : null;
    card.classList.toggle('central-widget-card--qqq-muted', !fresh && !hasHistory);
    if (priceNode) priceNode.textContent = price !== null
      ? price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
      : '—';
    if (pctNode) {
      pctNode.textContent = percent === null ? '—%' : (percent > 0 ? '+' : '') + percent.toFixed(2) + '%';
      pctNode.classList.toggle('central-widget-card__kospi-change--up', percent !== null && percent > 0);
      pctNode.classList.toggle('central-widget-card__kospi-change--down', percent !== null && percent < 0);
      chartNode?.classList.toggle('central-widget-card__sparkline--up', percent !== null && percent > 0);
      chartNode?.classList.toggle('central-widget-card__sparkline--down', percent !== null && percent < 0);
    }
    if (reasonNode) {
      if (fresh) reasonNode.textContent = easternTradingWindow(quote.received_at_ms).period + ' · 실시간';
      else if (hasHistory) reasonNode.textContent = qqqHistoryDate.slice(5).replace('-', '/') + ' 종가';
      else reasonNode.textContent = '차트 조회 대기';
    }
    drawQqqChart(card);
  }

  function loadQqqHistory() {
    if (qqqHistoryRequest) return qqqHistoryRequest;
    const url = window.location.hostname.endsWith('github.io')
      ? 'https://gaemi-gtp.onrender.com/api/market/qqq-history'
      : '/api/market/qqq-history';
    // One lightweight historical GET when the widget is mounted; no 3s polling.
    qqqHistoryRequest = fetch(url, { cache: 'default' }).then(async response => {
      if (!response.ok) throw new Error('qqq_history_unavailable');
      const data = await response.json();
      if (data?.ok !== true || data.symbol !== 'QQQ' || data.source !== 'yahoo-daily'
        || !Array.isArray(data.points)) throw new Error('qqq_history_invalid');
      let prev = '';
      const rows = [];
      for (const point of data.points.slice(-60)) {
        const date = String(point?.date || '');
        const price = point?.close;
        if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || date <= prev
          || typeof price !== 'number' || !Number.isFinite(price) || price <= 0) {
          throw new Error('qqq_history_invalid');
        }
        rows.push({ date, price });
        prev = date;
      }
      if (rows.length < 2 || rows[rows.length - 1].date !== data.last_trading_date) {
        throw new Error('qqq_history_invalid');
      }
      qqqHistory = rows;
      qqqHistoryDate = rows[rows.length - 1].date;
      qqqHistoryClose = rows[rows.length - 1].price;
      qqqHistoryChange = ((qqqHistoryClose / rows[rows.length - 2].price) - 1) * 100;
      updateQqqCard();
    }).catch(() => {
      // Never invent values, never erase independently received live FE data.
      updateQqqCard();
    });
    return qqqHistoryRequest;
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
      updateQqqCard();
      return;
    }
    qqqCurrent = quote;
    const fresh = quote.stale === false && Date.now() - quote.received_at_ms <= 25000;
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
    updateQqqCard();
  }

  function render() {
    const dock = root();
    const bodyEl = body();
    if (!dock || !bodyEl) return;
    bodyEl.innerHTML = activeIds.map(id => {
      const meta = catalog()[id];
      if (id === 'qqq') {
        return `
        <article class="central-widget-card central-widget-card--kospi central-widget-card--qqq-muted" data-central-widget-id="${escapeHtml(id)}">
          <button type="button" class="central-widget-card__close central-widget-card__close--overlay" data-central-widget-remove="${escapeHtml(id)}" aria-label="QQQ 위젯 삭제" title="위젯 삭제">
            <i data-lucide="x" class="w-3 h-3"></i>
          </button>
          <div class="central-widget-card__kospi-title">QQQ</div>
          <div class="central-widget-card__kospi-body" aria-label="QQQ 키움 실시간 체결가 차트">
            <svg class="central-widget-card__sparkline" viewBox="0 0 72 28" preserveAspectRatio="none" aria-hidden="true">
              <defs>
                <linearGradient id="kospiSparklineGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="currentColor" stop-opacity="0.28"></stop>
                  <stop offset="100%" stop-color="currentColor" stop-opacity="0"></stop>
                </linearGradient>
              </defs>
              <polygon data-kospi-sparkline-fill points=""></polygon>
              <polyline data-kospi-sparkline points=""></polyline>
            </svg>
            <div class="central-widget-card__kospi-copy">
              <div class="central-widget-card__kospi-row central-widget-card__kospi-market"><strong data-kospi-price>—</strong><span data-kospi-change class="central-widget-card__kospi-change">—%</span></div>
              <div class="central-widget-card__kospi-row central-widget-card__kospi-reason"><span>데이터 미연결</span></div>
            </div>
          </div>
        </article>`;
      }
      if (id === 'night-futures') {
        const title = '코스피200 야간선물';
        const detail = '야간선물 원천 데이터 연결 후 시세·등락률·흐름을 표시합니다.';
        return `<article class="central-widget-card central-widget-card--kospi" data-central-widget-id="${escapeHtml(id)}">
          <button type="button" class="central-widget-card__close central-widget-card__close--overlay" data-central-widget-remove="${escapeHtml(id)}" aria-label="${escapeHtml(title)} 위젯 삭제" title="위젯 삭제"><i data-lucide="x" class="w-3 h-3"></i></button>
          <div class="central-widget-card__kospi-title">${escapeHtml(title)}</div>
          <div class="central-widget-card__market-empty">${escapeHtml(detail)}</div>
        </article>`;
      }
      return `<article class="central-widget-card" data-central-widget-id="${escapeHtml(id)}">
        <div class="central-widget-card__top">
          <div class="central-widget-card__name">${escapeHtml(meta.title)}</div>
          <button type="button" class="central-widget-card__close" data-central-widget-remove="${escapeHtml(id)}" aria-label="${escapeHtml(meta.title)} 위젯 삭제" title="위젯 삭제"><i data-lucide="x" class="w-3 h-3"></i></button>
        </div>
        <div class="central-widget-card__desc" data-central-widget-mount="${escapeHtml(id)}">${escapeHtml(meta.description)} · 데이터 준비 중</div>
      </article>`;
    }).join('');
    dock.dataset.count = String(activeIds.length);
    document.querySelectorAll('[data-central-widget-mount]').forEach(node => {
      window.GaemiGTPAnalysisWidgets?.mount?.(node.dataset.centralWidgetMount, node);
    });
    if (window.lucide) window.lucide.createIcons();
    if (activeIds.includes('qqq')) updateQqqCard();
  }
  function add(id) {
    if (!catalog()[id] || activeIds.includes(id)) return false;
    activeIds.push(id); saveState(); render();
    if (id === 'qqq') void loadQqqHistory();
    return true;
  }
  function remove(id) {
    const next = activeIds.filter(item => item !== id);
    const changed = next.length !== activeIds.length;
    activeIds = next;
    if (changed) { saveState(); render(); window.GaemiGTPPluginSidebar?.render?.(); }
    return changed;
  }
  function initialize() {
    const dock = root();
    if (!dock || dock.dataset.bound === 'true') return;
    dock.dataset.bound = 'true';
    activeIds = readState(); render();
    if (activeIds.includes('qqq')) void loadQqqHistory();
    window.addEventListener('gaemi:qqq-quote', onQqqQuote);
    dock.addEventListener('click', event => {
      const button = event.target.closest('[data-central-widget-remove]');
      if (button) remove(button.dataset.centralWidgetRemove);
    });
  }
  document.addEventListener('DOMContentLoaded', initialize);
  window.GaemiGTPWidgetDock = { initialize, add, remove, getActiveIds: () => [...activeIds], isActive: id => activeIds.includes(id) };
}());
