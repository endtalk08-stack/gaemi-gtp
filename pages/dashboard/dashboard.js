/* Dashboard Workspace — v8.0
   토스식 공통 위젯 Shell: 이동 / 리사이즈 / 배치저장 / 집중보기.
   데이터/API/DB 로직은 각 위젯이 담당한다.
*/
(function () {
  'use strict';

  const LAYOUT_KEY = 'gaemiGTP_dashboard_layout_v8';
  const WIDGET_SLOTS = [
    { id: 'chart', title: '차트', icon: 'chart-candlestick', description: '차트 위젯 영역', x: 1, y: 1, w: 8, h: 4 },
    { id: 'market-state', title: '시장 상태', icon: 'activity', description: '시장 상태 위젯 영역', widgetKey: 'market-state', x: 9, y: 1, w: 4, h: 4 },
    { id: 'news', title: '뉴스', icon: 'newspaper', description: '뉴스 위젯 영역', x: 1, y: 5, w: 3, h: 4 },
    { id: 'economic', title: '경제일정', icon: 'calendar-days', description: '경제일정 위젯 영역', x: 4, y: 5, w: 3, h: 4 },
    { id: 'ranking', title: '실시간 순위', icon: 'trophy', description: '실시간 순위 위젯 영역', x: 7, y: 5, w: 3, h: 4 },
    { id: 'earnings', title: '실적', icon: 'badge-dollar-sign', description: '실적 위젯 영역', x: 10, y: 5, w: 3, h: 4 },
  ];

  let layout = null;
  let focusWidgetId = null;

  function cloneDefaultLayout() {
    return Object.fromEntries(WIDGET_SLOTS.map(s => [s.id, { x: s.x, y: s.y, w: s.w, h: s.h }]));
  }

  function readLayout() {
    try {
      const saved = JSON.parse(localStorage.getItem(LAYOUT_KEY) || 'null');
      const base = cloneDefaultLayout();
      if (!saved || typeof saved !== 'object') return base;
      WIDGET_SLOTS.forEach(s => {
        const p = saved[s.id];
        if (!p) return;
        base[s.id] = {
          x: Math.max(1, Math.min(12, Number(p.x) || s.x)),
          y: Math.max(1, Math.min(8, Number(p.y) || s.y)),
          w: Math.max(2, Math.min(12, Number(p.w) || s.w)),
          h: Math.max(2, Math.min(8, Number(p.h) || s.h)),
        };
        if (base[s.id].x + base[s.id].w - 1 > 12) base[s.id].x = 13 - base[s.id].w;
        if (base[s.id].y + base[s.id].h - 1 > 8) base[s.id].y = 9 - base[s.id].h;
      });
      return base;
    } catch (_) { return cloneDefaultLayout(); }
  }

  function saveLayout() {
    try { localStorage.setItem(LAYOUT_KEY, JSON.stringify(layout)); } catch (_) {}
  }

  function applyPosition(el, p) {
    el.style.gridColumn = `${p.x} / span ${p.w}`;
    el.style.gridRow = `${p.y} / span ${p.h}`;
  }

  function createSlot(slot) {
    const article = document.createElement('article');
    article.className = 'dashboard-widget-slot';
    article.dataset.widgetSlot = slot.id;
    applyPosition(article, layout[slot.id]);
    article.innerHTML = `
      <div class="dashboard-widget-slot__head" data-widget-drag-handle title="드래그하여 이동">
        <span class="dashboard-widget-slot__drag" aria-hidden="true"><i data-lucide="grip-vertical"></i></span>
        <span class="dashboard-widget-slot__icon" aria-hidden="true"><i data-lucide="${slot.icon}"></i></span>
        <span class="dashboard-widget-slot__title">${slot.title}</span>
        <span class="dashboard-widget-slot__actions">
          <button type="button" data-widget-focus="${slot.id}" aria-label="${slot.title} 크게 보기" title="크게 보기"><i data-lucide="maximize-2"></i></button>
        </span>
      </div>
      <div class="dashboard-widget-slot__content">
        <div class="dashboard-widget-slot__body">${slot.description}</div>
        <div class="dashboard-widget-slot__mount"></div>
      </div>
      <button type="button" class="dashboard-widget-slot__resize" data-widget-resize aria-label="${slot.title} 크기 조절" title="드래그하여 크기 조절"></button>
    `;

    const widget = slot.widgetKey && window.GaemiGTPWidgets ? window.GaemiGTPWidgets[slot.widgetKey] : null;
    if (widget && typeof widget.mount === 'function') {
      widget.mount(article.querySelector('.dashboard-widget-slot__mount'));
      article.classList.add('dashboard-widget-slot--mounted');
    }
    return article;
  }

  function gridMetrics(grid) {
    const r = grid.getBoundingClientRect();
    const cs = getComputedStyle(grid);
    const gap = parseFloat(cs.columnGap) || 8;
    const rowGap = parseFloat(cs.rowGap) || gap;
    return { r, gap, rowGap, cellW: (r.width - gap * 11) / 12, cellH: (r.height - rowGap * 7) / 8 };
  }

  function bindInteractions(grid) {
    let state = null;

    grid.addEventListener('pointerdown', (e) => {
      const slotEl = e.target.closest('.dashboard-widget-slot');
      if (!slotEl || focusWidgetId) return;
      const isResize = !!e.target.closest('[data-widget-resize]');
      const isDrag = !!e.target.closest('[data-widget-drag-handle]');
      if (!isResize && !isDrag) return;
      e.preventDefault();
      const id = slotEl.dataset.widgetSlot;
      const start = { ...layout[id] };
      state = { id, slotEl, isResize, startX: e.clientX, startY: e.clientY, start };
      slotEl.classList.add(isResize ? 'is-resizing' : 'is-dragging');
      slotEl.setPointerCapture?.(e.pointerId);
    });

    grid.addEventListener('pointermove', (e) => {
      if (!state) return;
      const m = gridMetrics(grid);
      const dx = Math.round((e.clientX - state.startX) / (m.cellW + m.gap));
      const dy = Math.round((e.clientY - state.startY) / (m.cellH + m.rowGap));
      let next = { ...state.start };
      if (state.isResize) {
        next.w = Math.max(2, Math.min(12 - next.x + 1, state.start.w + dx));
        next.h = Math.max(2, Math.min(8 - next.y + 1, state.start.h + dy));
      } else {
        next.x = Math.max(1, Math.min(13 - next.w, state.start.x + dx));
        next.y = Math.max(1, Math.min(9 - next.h, state.start.y + dy));
      }
      layout[state.id] = next;
      applyPosition(state.slotEl, next);
    });

    function end() {
      if (!state) return;
      state.slotEl.classList.remove('is-resizing', 'is-dragging');
      saveLayout();
      state = null;
    }
    grid.addEventListener('pointerup', end);
    grid.addEventListener('pointercancel', end);
  }

  function setFocus(id) {
    const root = document.getElementById('rightPanelDashboard');
    if (!root) return;
    focusWidgetId = id || null;
    root.classList.toggle('is-widget-focused', !!focusWidgetId);
    root.querySelectorAll('.dashboard-widget-slot').forEach(el => {
      const active = el.dataset.widgetSlot === focusWidgetId;
      el.classList.toggle('is-focused', active);
      el.hidden = !!focusWidgetId && !active;
      if (active) {
        el.style.gridColumn = '1 / -1';
        el.style.gridRow = '1 / -1';
      } else if (!focusWidgetId) {
        applyPosition(el, layout[el.dataset.widgetSlot]);
      }
    });
    const back = root.querySelector('[data-dashboard-back]');
    if (back) back.hidden = !focusWidgetId;
  }

  function openWidget(id, options = {}) {
    const exists = WIDGET_SLOTS.some(s => s.id === id);
    if (!exists) return false;
    if (!document.body.classList.contains('right-panel-open') && typeof window.toggleRightPanel === 'function') window.toggleRightPanel();
    setFocus(options.focus === false ? null : id);
    const el = document.querySelector(`[data-widget-slot="${id}"]`);
    if (el) {
      el.classList.add('is-pulsed');
      setTimeout(() => el.classList.remove('is-pulsed'), 700);
    }
    return true;
  }

  function resetLayout() {
    layout = cloneDefaultLayout();
    saveLayout();
    document.querySelectorAll('.dashboard-widget-slot').forEach(el => applyPosition(el, layout[el.dataset.widgetSlot]));
  }

  function mount() {
    const root = document.getElementById('rightPanelDashboard');
    if (!root || root.dataset.dashboardMounted === 'true') return;
    layout = readLayout();
    root.innerHTML = `
      <div class="right-panel-dashboard__toolbar">
        <button type="button" data-dashboard-back hidden><i data-lucide="arrow-left"></i><span>대시보드</span></button>
        <span class="right-panel-dashboard__hint">위젯 이동 · 크기 조절</span>
        <button type="button" data-dashboard-reset title="기본 배치로 복원"><i data-lucide="rotate-ccw"></i></button>
      </div>
      <section class="right-panel-dashboard__grid" aria-label="위젯 영역"></section>
    `;
    const grid = root.querySelector('.right-panel-dashboard__grid');
    WIDGET_SLOTS.forEach(slot => grid.appendChild(createSlot(slot)));
    bindInteractions(grid);
    root.addEventListener('click', e => {
      const focus = e.target.closest('[data-widget-focus]');
      if (focus) setFocus(focus.dataset.widgetFocus);
      if (e.target.closest('[data-dashboard-back]')) setFocus(null);
      if (e.target.closest('[data-dashboard-reset]')) resetLayout();
    });
    root.dataset.dashboardMounted = 'true';
    if (window.lucide) window.lucide.createIcons();
  }

  window.GaemiGTPDashboard = {
    mount,
    openWidget,
    closeFocus: () => setFocus(null),
    resetLayout,
    widgetSlots: WIDGET_SLOTS.map(s => ({ ...s })),
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount, { once: true });
  else mount();
})();
