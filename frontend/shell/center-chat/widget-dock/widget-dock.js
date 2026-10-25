/* Central Widget Dock — presentation shell for data-backed analysis widgets only. */
(function () {
  'use strict';

  const STATE_KEY = 'gaemiGTP_central_widget_dock_v1';
  let activeIds = [];
  let chartSymbol = '';
  let chartRequest = 0;

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
      if (saved === null) return ['kospi'];
      const value = JSON.parse(saved);
      if (!Array.isArray(value)) return ['kospi'];
      // 이전 버전의 코스피 위젯 ID를 새 명확한 ID로 한 번만 이관한다.
      return value
        .map(id => id === 'why-up' ? 'kospi' : id)
        .filter((id, index, list) => catalog()[id] && list.indexOf(id) === index);
    } catch (_) { return []; }
  }
  function saveState() {
    try { localStorage.setItem(STATE_KEY, JSON.stringify(activeIds)); } catch (_) {}
  }
  function render() {
    const dock = root();
    const bodyEl = body();
    if (!dock || !bodyEl) return;
    bodyEl.innerHTML = activeIds.map(id => {
      const meta = catalog()[id];
      if (id === 'kospi' || id === 'night-futures') {
        const title = id === 'kospi' ? '코스피' : '코스피200 야간선물';
        const detail = id === 'kospi'
          ? '키움 원천 데이터 연결 후 시세·등락률·장중 흐름을 표시합니다.'
          : '야간선물 원천 데이터 연결 후 시세·등락률·흐름을 표시합니다.';
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
    if (activeIds.includes('chart')) loadChart();
    if (window.lucide) window.lucide.createIcons();
  }

  function setChartSelection(symbol) {
    if (!/^[A-Z0-9.\\-]{1,20}$/.test(String(symbol || ''))) return;
    chartSymbol = symbol;
    if (!activeIds.includes('chart')) add('chart');
    else loadChart();
  }

  async function loadChart() {
    const target = document.querySelector('[data-us-daily-chart]');
    if (!target || !chartSymbol) return;
    const current = ++chartRequest;
    target.textContent = '키움 일봉을 불러오는 중...';
    try {
      const response = await fetch(BACKEND_URL + '/market/us-daily-chart?symbol=' +
        encodeURIComponent(chartSymbol));
      const data = await response.json();
      if (current !== chartRequest || !target.isConnected) return;
      if (!response.ok || !data.ok || !Array.isArray(data.rows) || !data.rows.length) {
        target.textContent = '일봉 데이터가 아직 준비되지 않았어.';
        return;
      }
      target.replaceChildren();
      const label = document.createElement('div');
      label.className = 'us-daily-chart__label';
      label.textContent = data.name + ' (' + data.symbol + ') · 키움 일봉 · ' + data.rows.length + '개';
      const canvas = document.createElement('canvas');
      canvas.height = 272;
      canvas.setAttribute('aria-label', data.name + ' 일봉 캔들과 거래량');
      target.append(label, canvas);
      drawCandles(canvas, data.rows);
    } catch (_) {
      if (current === chartRequest && target.isConnected)
        target.textContent = '일봉 데이터를 조회할 수 없어.';
    }
  }

  function drawCandles(canvas, input) {
    const rows = input.slice(-65).filter(row =>
      ['open', 'high', 'low', 'close'].every(key => Number.isFinite(Number(row[key])) && Number(row[key]) > 0));
    if (!rows.length) return;
    const width = Math.max(320, canvas.getBoundingClientRect().width || 560);
    const height = 272;
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    canvas.style.height = height + 'px';
    const ctx = canvas.getContext('2d');
    ctx.scale(ratio, ratio);
    const left = 8, right = 58, top = 10, priceBottom = 195, volumeTop = 210, volumeBottom = 247;
    const chartWidth = width - left - right;
    const highs = rows.map(row => Number(row.high));
    const lows = rows.map(row => Number(row.low));
    const hi = Math.max(...highs), lo = Math.min(...lows);
    const padding = Math.max((hi - lo) * 0.08, 0.01);
    const min = lo - padding, max = hi + padding;
    const y = value => top + (max - value) / (max - min) * (priceBottom - top);
    ctx.font = '11px sans-serif';
    ctx.strokeStyle = 'rgba(145,155,170,.20)';
    ctx.fillStyle = '#94a3b8';
    for (let tick = 0; tick <= 4; tick++) {
      const value = min + (max - min) * tick / 4;
      const yy = y(value);
      ctx.beginPath(); ctx.moveTo(left, yy); ctx.lineTo(width - right + 4, yy); ctx.stroke();
      ctx.fillText(value.toFixed(2), width - right + 8, yy + 4);
    }
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
      ctx.globalAlpha = 0.65;
      ctx.fillRect(x - candleWidth / 2, volumeBottom - volHeight, candleWidth, volHeight);
      ctx.globalAlpha = 1;
    });
    ctx.fillStyle = '#94a3b8';
    ctx.fillText(rows[0].date.slice(5), left, 266);
    const last = rows[rows.length - 1].date.slice(5);
    ctx.fillText(last, width - right - ctx.measureText(last).width, 266);
  }

  function add(id) {
    if (!catalog()[id] || activeIds.includes(id)) return false;
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
    dock.addEventListener('click', event => {
      const button = event.target.closest('[data-central-widget-remove]');
      if (button) remove(button.dataset.centralWidgetRemove);
    });
  }
  document.addEventListener('DOMContentLoaded', initialize);
  window.GaemiGTPWidgetDock = { initialize, add, remove, getActiveIds: () => [...activeIds], isActive: id => activeIds.includes(id), setChartSelection };
}());
