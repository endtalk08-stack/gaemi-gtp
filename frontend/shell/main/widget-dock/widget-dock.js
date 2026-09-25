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
      return `
        <article class="central-widget-card" data-central-widget-id="${escapeHtml(id)}">
          <div class="central-widget-card__top">
            <div class="central-widget-card__name">${escapeHtml(meta.title)}</div>
            <button type="button" class="central-widget-card__close" data-central-widget-remove="${escapeHtml(id)}" aria-label="${escapeHtml(meta.title)} 위젯 삭제" title="위젯 삭제">
              <i data-lucide="x" class="w-3 h-3"></i>
            </button>
          </div>
          <div class="central-widget-card__desc" data-central-widget-mount="${escapeHtml(id)}">${escapeHtml(meta.description)} · 분석 전에는 안내가 표시됩니다.</div>
        </article>`;
    }).join('');

    dock.dataset.count = String(activeIds.length);
    if (window.GaemiGTPAnalysisWidgets?.mount) {
      activeIds.forEach(id => {
        const mount = bodyEl.querySelector(`[data-central-widget-mount="${id}"]`);
        window.GaemiGTPAnalysisWidgets.mount(id, mount);
      });
    }
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
    window.addEventListener('gaemi-analysis-data-change', render);
  }

  window.GaemiGTPWidgetDock = {
    initialize,
    add,
    remove,
    getActiveIds: () => [...activeIds],
    isActive: (id) => activeIds.includes(id),
  };
}());
