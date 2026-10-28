/* Central Widget Dock — presentation shell for data-backed analysis widgets only. */
(function () {
  'use strict';

  const STATE_KEY = 'gaemiGTP_central_widget_dock_v1';
  let activeIds = [];
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
    try {
      const saved = localStorage.getItem(STATE_KEY);
      if (saved === null) return ['qqq'];
      const value = JSON.parse(saved);
      if (!Array.isArray(value)) return ['qqq'];
      // 이전 버전의 코스피 위젯 ID를 새 명확한 ID로 한 번만 이관한다.
      return value
        .map(id => (id === 'why-up' || id === 'kospi') ? 'qqq' : id)
        .filter((id, index, list) => id !== 'chart' && catalog()[id] && list.indexOf(id) === index);
    } catch (_) { return []; }
  }
  function saveState() {
    try { localStorage.setItem(STATE_KEY, JSON.stringify(activeIds)); } catch (_) {}
  }

  // Browser-only chart cache: max 120 authenticated relay snapshots, no API or DB calls.
  const qqqPoints = [];
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
    if (qqqPoints.length < 2) {
      line.setAttribute('points', '');
      fill.setAttribute('points', '');
      return;
    }
    const lows = qqqPoints.map(point => point.price);
    const lowest = Math.min(...lows);
    const highest = Math.max(...lows);
    const span = highest - lowest;
    const points = qqqPoints.map((point, index) => {
      const x = 1 + (index / (qqqPoints.length - 1)) * 70;
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
    const valid = quote && Number.isFinite(quote.price) && quote.price > 0;
    const fresh = valid && !quote.stale && Date.now() - quote.received_at_ms <= 25000;
    card.classList.toggle('central-widget-card--qqq-muted', !fresh);
    if (priceNode) priceNode.textContent = valid
      ? quote.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
      : '—';
    if (pctNode) {
      const percent = valid && Number.isFinite(quote.change_pct) ? quote.change_pct : null;
      pctNode.textContent = percent === null ? '—%' : (percent > 0 ? '+' : '') + percent.toFixed(2) + '%';
      pctNode.classList.toggle('central-widget-card__kospi-change--up', fresh && percent !== null && percent > 0);
      pctNode.classList.toggle('central-widget-card__kospi-change--down', fresh && percent !== null && percent < 0);
      chartNode?.classList.toggle('central-widget-card__sparkline--up', fresh && percent !== null && percent > 0);
      chartNode?.classList.toggle('central-widget-card__sparkline--down', fresh && percent !== null && percent < 0);
    }
    if (reasonNode) {
      if (!valid) reasonNode.textContent = 'QQQ 수신 대기';
      else if (!fresh) reasonNode.textContent = '시세 지연';
      else reasonNode.textContent = easternTradingWindow(quote.received_at_ms).period + ' · 실시간';
    }
    drawQqqChart(card);
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
        const response = await fetch(BACKEND_URL + '/market/us-daily-chart?symbol=' +
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
    activeIds.push(id); saveState(); render(); return true;
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
    document.addEventListener('visibilitychange', () => {
      const active = inlineChart;
      if (!document.hidden && active?.target?.isConnected)
        loadChart(active.target, active.symbol, null);
    });
    window.addEventListener('gaemi:qqq-quote', onQqqQuote);
    window.addEventListener('gaemi:us-live-quotes', onUsLiveQuotes);
    dock.addEventListener('click', event => {
      const button = event.target.closest('[data-central-widget-remove]');
      if (button) remove(button.dataset.centralWidgetRemove);
    });
  }
  document.addEventListener('DOMContentLoaded', initialize);
  window.GaemiGTPWidgetDock = { initialize, add, remove, getActiveIds: () => [...activeIds], isActive: id => activeIds.includes(id), setChartSelection, renderInlineChart, isInlineChartActive };
}());

