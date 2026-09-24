/* Central Widget Dock — add/remove shell only.
   Actual widget data/rendering will be connected after architecture is finalized.
*/
(function () {
  'use strict';

  const STATE_KEY = 'gaemiGTP_central_widget_dock_v1';
  let activeIds = [];
  let menuOpen = false;

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
  function menu() { return document.getElementById('centralWidgetDockMenu'); }

  function render() {
    const dock = root();
    const bodyEl = body();
    const menuEl = menu();
    if (!dock || !bodyEl || !menuEl) return;

    const items = Object.entries(catalog());
    bodyEl.innerHTML = activeIds.map(id => {
      const meta = catalog()[id];
      return `
        <article class="central-widget-card" data-central-widget-id="${id}">
          <div class="central-widget-card__top">
            <div class="central-widget-card__name">${escapeHtml(meta.title)}</div>
            <button type="button" class="central-widget-card__close" data-central-widget-remove="${id}" aria-label="${escapeHtml(meta.title)} 위젯 삭제" title="위젯 삭제">
              <i data-lucide="x" class="w-3 h-3"></i>
            </button>
          </div>
          <div class="central-widget-card__desc">${escapeHtml(meta.description)} · 실제 데이터 위젯 영역</div>
        </article>`;
    }).join('');

    menuEl.innerHTML = `<div class="central-widget-dock__menu-title">분석 위젯 추가</div>` + items.map(([id, meta]) => {
      const active = activeIds.includes(id);
      return `
        <button type="button" class="central-widget-dock__menu-item${active ? ' is-active' : ''}" data-central-widget-add="${id}" ${active ? 'disabled' : ''}>
          <i data-lucide="${meta.icon}" class="w-3.5 h-3.5"></i>
          <span class="central-widget-dock__menu-meta">
            <span class="central-widget-dock__menu-label">${escapeHtml(meta.title)}</span>
            <span class="central-widget-dock__menu-desc">${escapeHtml(meta.description)}</span>
          </span>
        </button>`;
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

  function setMenu(open) {
    menuOpen = !!open;
    const menuEl = menu();
    const btn = document.querySelector('[data-central-widget-add-toggle]');
    if (menuEl) menuEl.hidden = !menuOpen;
    if (btn) btn.setAttribute('aria-expanded', menuOpen ? 'true' : 'false');
  }

  function add(id) {
    if (!catalog()[id] || activeIds.includes(id)) return;
    activeIds.push(id);
    saveState();
    render();
    setMenu(false);
  }

  function remove(id) {
    activeIds = activeIds.filter(item => item !== id);
    saveState();
    render();
  }

  function initialize() {
    if (!root() || root().dataset.bound === 'true') return;
    root().dataset.bound = 'true';
    activeIds = readState();
    render();

    root().addEventListener('click', (event) => {
      const addToggle = event.target.closest('[data-central-widget-add-toggle]');
      if (addToggle) { setMenu(!menuOpen); return; }

      const addBtn = event.target.closest('[data-central-widget-add]');
      if (addBtn) { add(addBtn.dataset.centralWidgetAdd); return; }

      const removeBtn = event.target.closest('[data-central-widget-remove]');
      if (removeBtn) { remove(removeBtn.dataset.centralWidgetRemove); return; }
    });

    document.addEventListener('click', (event) => {
      if (!menuOpen) return;
      if (!root().contains(event.target)) setMenu(false);
    });
  }

  window.GaemiGTPWidgetDock = { initialize, add, remove };
}());
