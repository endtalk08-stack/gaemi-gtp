/* Central Widget Dock — display and remove shell only.
   Widget creation/addition is routed through the left Plugin sidebar.
   Actual widget data/rendering will be connected after architecture is finalized.
*/
(function () {
  'use strict';

  const STATE_KEY = 'gaemiGTP_central_widget_dock_v1';
  let activeIds = [];

  function catalog() {
    return window.GaemiGTPWidgetCatalog || {};
  }

  function readState() {
    try {
      const raw = localStorage.getItem(STATE_KEY);
      const value = raw ? JSON.parse(raw) : null;
      return Array.isArray(value) ? value.filter(id => catalog()[id]) : [];
    } catch (_) {
      return [];
    }
  }

  function saveState() {
    try { localStorage.setItem(STATE_KEY, JSON.stringify(activeIds)); } catch (_) {}
  }

  const KOSPI_URL = 'https://query1.finance.yahoo.com/v8/finance/chart/%5EKS11?range=1d&interval=5m';

  function root() { return document.getElementById('centralWidgetDock'); }
  function body() { return document.getElementById('centralWidgetDockBody'); }

  function render() {
    const dock = root();
    const bodyEl = body();
    if (!dock || !bodyEl) return;

    bodyEl.innerHTML = activeIds.map(id => {
      const meta = catalog()[id];
      if (id === 'why-up') {
        return `
        <article class="central-widget-card central-widget-card--kospi" data-central-widget-id="${escapeHtml(id)}">
          <button type="button" class="central-widget-card__close central-widget-card__close--overlay" data-central-widget-remove="${escapeHtml(id)}" aria-label="코스피 위젯 삭제" title="위젯 삭제">
            <i data-lucide="x" class="w-3 h-3"></i>
          </button>
          <div class="central-widget-card__kospi-title">코스피</div>
          <div class="central-widget-card__kospi-body" aria-label="코스피 샘플 데이터">
            <svg class="central-widget-card__sparkline" viewBox="0 0 72 28" preserveAspectRatio="none" aria-hidden="true">
              <defs>
                <linearGradient id="kospiSparklineGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="currentColor" stop-opacity="0.28"></stop>
                  <stop offset="100%" stop-color="currentColor" stop-opacity="0"></stop>
                </linearGradient>
              </defs>
              <polygon data-kospi-sparkline-fill points="1,27 1,23 8,21 15,22 22,17 29,19 36,14 43,16 50,10 57,12 64,7 71,5 71,27"></polygon>
              <polyline data-kospi-sparkline points="1,23 8,21 15,22 22,17 29,19 36,14 43,16 50,10 57,12 64,7 71,5"></polyline>
            </svg>
            <div class="central-widget-card__kospi-copy">
              <div class="central-widget-card__kospi-row central-widget-card__kospi-market"><strong data-kospi-price>7,003.74</strong><span data-kospi-change class="central-widget-card__kospi-change central-widget-card__kospi-change--up">+0.46%</span></div>
              <div class="central-widget-card__kospi-row central-widget-card__kospi-reason"><span>기관 매수 전환</span></div>
            </div>
          </div>
        </article>`;
      }
      return `
        <article class="central-widget-card" data-central-widget-id="${escapeHtml(id)}">
          <div class="central-widget-card__top">
            <div class="central-widget-card__name">${escapeHtml(meta.title)}</div>
            <button type="button" class="central-widget-card__close" data-central-widget-remove="${escapeHtml(id)}" aria-label="${escapeHtml(meta.title)} 위젯 삭제" title="위젯 삭제">
              <i data-lucide="x" class="w-3 h-3"></i>
            </button>
          </div>
          <div class="central-widget-card__desc" data-central-widget-mount="${escapeHtml(id)}">${escapeHtml(meta.description)} · 데이터 미연결</div>
        </article>`;
    }).join('');

    dock.dataset.count = String(activeIds.length);
    if (window.lucide) window.lucide.createIcons();
    if (activeIds.includes('why-up')) loadKospiSample();
  }


  async function loadKospiSample() {
    const card = document.querySelector('.central-widget-card--kospi');
    if (!card) return;
    try {
      const response = await fetch(KOSPI_URL, { cache: 'no-store' });
      if (!response.ok) return;
      const payload = await response.json();
      const result = payload?.chart?.result?.[0];
      const meta = result?.meta;
      const price = Number(meta?.regularMarketPrice);
      const previousClose = Number(meta?.chartPreviousClose ?? meta?.previousClose);
      if (!Number.isFinite(price) || !Number.isFinite(previousClose) || previousClose === 0) return;
      const changePercent = ((price - previousClose) / previousClose) * 100;
      const closes = (result?.indicators?.quote?.[0]?.close || []).map(Number).filter(Number.isFinite);
      const sparkline = card.querySelector('[data-kospi-sparkline]');
      if (sparkline && closes.length > 1) {
        const min = Math.min(...closes);
        const max = Math.max(...closes);
        const range = max - min || 1;
        const points = closes.map((value, index) => {
          const x = 1 + (index / (closes.length - 1)) * 70;
          const y = 25 - ((value - min) / range) * 22;
          return x.toFixed(1) + ',' + y.toFixed(1);
        }).join(' ');
        sparkline.setAttribute('points', points);
        const fill = card.querySelector('[data-kospi-sparkline-fill]');
        if (fill) fill.setAttribute('points', '1,27 ' + points + ' 71,27');
      }
      const priceEl = card.querySelector('[data-kospi-price]');
      const changeEl = card.querySelector('[data-kospi-change]');
      if (priceEl) priceEl.textContent = price.toLocaleString('ko-KR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      if (changeEl) {
        changeEl.textContent = (changePercent > 0 ? '+' : '') + changePercent.toFixed(2) + '%';
        changeEl.classList.toggle('central-widget-card__kospi-change--up', changePercent > 0);
        changeEl.classList.toggle('central-widget-card__kospi-change--down', changePercent < 0);
        const chart = card.querySelector('.central-widget-card__sparkline');
        chart?.classList.toggle('central-widget-card__sparkline--up', changePercent > 0);
        chart?.classList.toggle('central-widget-card__sparkline--down', changePercent < 0);
      }
    } catch (_) {
      // 샘플 연결 실패 시 기존 표시값을 유지한다.
    }
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function add(id) {
    if (!catalog()[id] || activeIds.includes(id)) return false;
    activeIds.push(id);
    saveState();
    render();
    return true;
  }

  function remove(id) {
    const next = activeIds.filter(item => item !== id);
    const changed = next.length !== activeIds.length;
    activeIds = next;
    if (changed) {
      saveState();
      render();
      window.GaemiGTPPluginSidebar?.render?.();
    }
    return changed;
  }

  function initialize() {
    const dock = root();
    if (!dock || dock.dataset.bound === 'true') return;
    dock.dataset.bound = 'true';
    activeIds = readState();
    render();

    dock.addEventListener('click', (event) => {
      const removeBtn = event.target.closest('[data-central-widget-remove]');
      if (removeBtn) remove(removeBtn.dataset.centralWidgetRemove);
    });
  }

  // 분리된 위젯 도크도 페이지 로드 시 기존처럼 자동 초기화한다.
  document.addEventListener('DOMContentLoaded', initialize);

  window.GaemiGTPWidgetDock = {
    initialize,
    add,
    remove,
    getActiveIds: () => [...activeIds],
    isActive: (id) => activeIds.includes(id),
  };
}());
