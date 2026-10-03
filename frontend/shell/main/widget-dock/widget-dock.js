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
            <svg class="central-widget-card__sparkline" viewBox="0 0 72 28" aria-hidden="true">
              <polyline points="1,23 8,21 15,22 22,17 29,19 36,14 43,16 50,10 57,12 64,7 71,5"></polyline>
            </svg>
            <div class="central-widget-card__kospi-copy">
              <div class="central-widget-card__kospi-row"><strong>7,003.74</strong><span class="central-widget-card__kospi-change central-widget-card__kospi-change--up">+0.46%</span></div>
              <div class="central-widget-card__kospi-row central-widget-card__kospi-reason"><span>기관 매수</span></div>
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
