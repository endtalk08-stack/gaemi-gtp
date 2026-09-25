/* Dashboard v8.2 — Toss-like one-screen workspace.
   - 실제 Render 서비스 경로(frontend/)용
   - 기본 2+4 배치
   - 자동 저장
   - 드래그 이동 / 리사이즈 / 크게 보기
   - 개발용 툴바 제거
   - 외부 hashtag/widget 호출용 openWidget API 제공
*/
(function () {
  'use strict';

  const STORAGE_KEY = 'gaemi.dashboard.layout.v8.2';
  const COLS = 12;
  const ROWS = 8;

  const WIDGETS = [
    { id: 'chart', title: '차트', widgetKey: 'chart' },
    { id: 'market-state', title: '시장 상태', widgetKey: 'market-state' },
    { id: 'news', title: '뉴스', widgetKey: 'news' },
    { id: 'economic', title: '경제일정', widgetKey: 'economic' },
    { id: 'ranking', title: '실시간 순위', widgetKey: 'ranking' },
    { id: 'earnings', title: '실적', widgetKey: 'earnings' },
    { id: 'volume', title: '거래량', widgetKey: 'volume' },
    { id: 'trading-value', title: '거래대금', widgetKey: 'trading-value' },
    { id: 'event', title: '이벤트', widgetKey: 'event' },
  ];

  const DEFAULT_LAYOUT = {
    chart:          { x: 1,  y: 1, w: 8, h: 4 },
    'market-state': { x: 9,  y: 1, w: 4, h: 4 },
    news:           { x: 1,  y: 5, w: 3, h: 4 },
    economic:       { x: 4,  y: 5, w: 3, h: 4 },
    ranking:        { x: 7,  y: 5, w: 3, h: 4 },
    earnings:       { x: 10, y: 5, w: 3, h: 4 },
  };

  const DEFAULT_IDS = Object.keys(DEFAULT_LAYOUT);

  let root = null;
  let grid = null;
  let layout = {};
  let transientIds = new Set();
  let focusedId = null;

  const clone = (value) => JSON.parse(JSON.stringify(value));
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

  function widgetById(id) {
    return WIDGETS.find((widget) => widget.id === id);
  }

  function normalizeRect(rect) {
    const w = clamp(Math.round(Number(rect?.w) || 3), 2, COLS);
    const h = clamp(Math.round(Number(rect?.h) || 4), 2, ROWS);
    const x = clamp(Math.round(Number(rect?.x) || 1), 1, COLS - w + 1);
    const y = clamp(Math.round(Number(rect?.y) || 1), 1, ROWS - h + 1);
    return { x, y, w, h };
  }

  function loadLayout() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
      if (!saved || saved.version !== 2 || !saved.layout) return clone(DEFAULT_LAYOUT);

      const next = {};
      DEFAULT_IDS.forEach((id) => {
        next[id] = normalizeRect(saved.layout[id] || DEFAULT_LAYOUT[id]);
      });

      // 저장값이 충돌하면 안전하게 기본 배치로 복귀
      if (hasAnyOverlap(next)) return clone(DEFAULT_LAYOUT);
      return next;
    } catch (_) {
      return clone(DEFAULT_LAYOUT);
    }
  }

  function saveLayout() {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ version: 2, layout })
      );
    } catch (_) {}
  }

  function rectsOverlap(a, b) {
    return !(
      a.x + a.w - 1 < b.x ||
      b.x + b.w - 1 < a.x ||
      a.y + a.h - 1 < b.y ||
      b.y + b.h - 1 < a.y
    );
  }

  function hasAnyOverlap(candidateLayout) {
    const ids = Object.keys(candidateLayout);
    for (let i = 0; i < ids.length; i += 1) {
      for (let j = i + 1; j < ids.length; j += 1) {
        if (rectsOverlap(candidateLayout[ids[i]], candidateLayout[ids[j]])) {
          return true;
        }
      }
    }
    return false;
  }

  function canPlace(id, rect) {
    if (
      rect.x < 1 ||
      rect.y < 1 ||
      rect.w < 2 ||
      rect.h < 2 ||
      rect.x + rect.w - 1 > COLS ||
      rect.y + rect.h - 1 > ROWS
    ) {
      return false;
    }

    return Object.entries(layout).every(([otherId, otherRect]) => {
      if (otherId === id) return true;
      return !rectsOverlap(rect, otherRect);
    });
  }

  function applyRect(article, rect) {
    article.style.gridColumn = `${rect.x} / span ${rect.w}`;
    article.style.gridRow = `${rect.y} / span ${rect.h}`;
  }

  function refreshAllRects() {
    if (!grid) return;
    Object.entries(layout).forEach(([id, rect]) => {
      const article = grid.querySelector(`[data-widget-slot="${id}"]`);
      if (article) applyRect(article, rect);
    });
  }

  function firstAvailableRect(w = 3, h = 4) {
    for (let y = 1; y <= ROWS - h + 1; y += 1) {
      for (let x = 1; x <= COLS - w + 1; x += 1) {
        const rect = { x, y, w, h };
        const collision = Object.values(layout).some((other) =>
          rectsOverlap(rect, other)
        );
        if (!collision) return rect;
      }
    }
    return null;
  }

  function gridMetrics() {
    const bounds = grid.getBoundingClientRect();
    const styles = getComputedStyle(grid);
    const colGap = parseFloat(styles.columnGap) || 10;
    const rowGap = parseFloat(styles.rowGap) || 10;

    return {
      bounds,
      colGap,
      rowGap,
      cellW: (bounds.width - colGap * (COLS - 1)) / COLS,
      cellH: (bounds.height - rowGap * (ROWS - 1)) / ROWS,
    };
  }

  function mountWidgetContent(article, widget) {
    const mountPoint = article.querySelector('.dashboard-widget-slot__mount');
    const registered =
      window.GaemiGTPWidgets &&
      window.GaemiGTPWidgets[widget.widgetKey || widget.id];

    if (registered && typeof registered.mount === 'function') {
      registered.mount(mountPoint);
      article.classList.add('dashboard-widget-slot--mounted');
    }
  }

  function createArticle(id) {
    const widget = widgetById(id);
    if (!widget) return null;

    const article = document.createElement('article');
    article.className = 'dashboard-widget-slot';
    article.dataset.widgetSlot = id;
    article.setAttribute('aria-label', widget.title);

    article.innerHTML = `
      <div class="dashboard-widget-slot__head" data-widget-drag-handle>
        <span class="dashboard-widget-slot__title">${widget.title}</span>
        <div class="dashboard-widget-slot__actions">
          <button type="button"
                  class="dashboard-widget-slot__expand"
                  data-widget-expand="${id}"
                  aria-label="${widget.title} 크게 보기"
                  title="크게 보기">
            <i data-lucide="maximize-2"></i>
          </button>
        </div>
      </div>

      <div class="dashboard-widget-slot__content">
        <div class="dashboard-widget-slot__mount"></div>
      </div>

      <button type="button"
              class="dashboard-widget-slot__resize"
              data-widget-resize
              aria-label="${widget.title} 크기 조절"
              title="크기 조절"></button>
    `;

    if (layout[id]) applyRect(article, layout[id]);
    mountWidgetContent(article, widget);
    bindArticleInteractions(article, id);

    return article;
  }

  function bindArticleInteractions(article, id) {
    const dragHandle = article.querySelector('[data-widget-drag-handle]');
    const resizeHandle = article.querySelector('[data-widget-resize]');

    dragHandle.addEventListener('pointerdown', (event) => {
      if (event.button !== 0 || focusedId) return;
      if (event.target.closest('button')) return;
      if (root.clientWidth <= 644) return;

      const origin = { ...layout[id] };
      const metrics = gridMetrics();
      let latest = { ...origin };

      event.preventDefault();
      dragHandle.setPointerCapture?.(event.pointerId);
      article.classList.add('is-dragging');

      function move(e) {
        const dx = Math.round(
          (e.clientX - event.clientX) / (metrics.cellW + metrics.colGap)
        );
        const dy = Math.round(
          (e.clientY - event.clientY) / (metrics.cellH + metrics.rowGap)
        );

        const next = {
          ...origin,
          x: clamp(origin.x + dx, 1, COLS - origin.w + 1),
          y: clamp(origin.y + dy, 1, ROWS - origin.h + 1),
        };

        article.classList.toggle('is-invalid', !canPlace(id, next));
        latest = next;
        applyRect(article, next);
      }

      function finish(e) {
        dragHandle.removeEventListener('pointermove', move);
        dragHandle.removeEventListener('pointerup', finish);
        dragHandle.removeEventListener('pointercancel', finish);
        dragHandle.removeEventListener('lostpointercapture', finish);

        article.classList.remove('is-dragging', 'is-invalid');

        if (e.type === 'pointerup' && canPlace(id, latest)) {
          layout[id] = latest;
          saveLayout();
        } else {
          applyRect(article, origin);
        }
      }

      dragHandle.addEventListener('pointermove', move);
      dragHandle.addEventListener('pointerup', finish);
      dragHandle.addEventListener('pointercancel', finish);
      dragHandle.addEventListener('lostpointercapture', finish);
    });

    resizeHandle.addEventListener('pointerdown', (event) => {
      if (event.button !== 0 || focusedId) return;

      const origin = { ...layout[id] };
      const metrics = gridMetrics();
      let latest = { ...origin };

      event.preventDefault();
      resizeHandle.setPointerCapture?.(event.pointerId);
      article.classList.add('is-resizing');

      function move(e) {
        const dw = Math.round(
          (e.clientX - event.clientX) / (metrics.cellW + metrics.colGap)
        );
        const dh = Math.round(
          (e.clientY - event.clientY) / (metrics.cellH + metrics.rowGap)
        );

        const next = {
          ...origin,
          w: clamp(origin.w + dw, 2, COLS - origin.x + 1),
          h: clamp(origin.h + dh, 2, ROWS - origin.y + 1),
        };

        const valid = canPlace(id, next);
        article.classList.toggle('is-invalid', !valid);

        if (valid) {
          latest = next;
          applyRect(article, next);
        }
      }

      function finish(e) {
        resizeHandle.removeEventListener('pointermove', move);
        resizeHandle.removeEventListener('pointerup', finish);
        resizeHandle.removeEventListener('pointercancel', finish);
        resizeHandle.removeEventListener('lostpointercapture', finish);

        article.classList.remove('is-resizing', 'is-invalid');

        if (e.type === 'pointerup' && canPlace(id, latest)) {
          layout[id] = latest;
          saveLayout();
        } else {
          applyRect(article, origin);
        }
      }

      resizeHandle.addEventListener('pointermove', move);
      resizeHandle.addEventListener('pointerup', finish);
      resizeHandle.addEventListener('pointercancel', finish);
      resizeHandle.addEventListener('lostpointercapture', finish);
    });
  }

  function setFocus(id) {
    if (focusedId && focusedId !== id && transientIds.has(focusedId)) {
      const previous = focusedId;
      transientIds.delete(previous);
      delete layout[previous];
      grid.querySelector(`[data-widget-slot="${previous}"]`)?.remove();
    }
    focusedId = id || null;
    root.classList.toggle('is-widget-focused', !!focusedId);

    grid.querySelectorAll('.dashboard-widget-slot').forEach((article) => {
      const active = article.dataset.widgetSlot === focusedId;
      article.hidden = !!focusedId && !active;
      article.classList.toggle('is-focused', active);

      if (active) {
        article.style.gridColumn = '1 / -1';
        article.style.gridRow = '1 / -1';
      } else if (!focusedId && layout[article.dataset.widgetSlot]) {
        applyRect(article, layout[article.dataset.widgetSlot]);
      }
    });

    root.querySelector('.dashboard-focus-back').hidden = !focusedId;
  }

  function ensureTransientWidget(id) {
    if (layout[id]) return true;
    if (!widgetById(id)) return false;

    const rect = firstAvailableRect(3, 4) || { x: 1, y: 1, w: 12, h: 8 };
    layout[id] = rect;
    transientIds.add(id);

    const article = createArticle(id);
    if (article) grid.appendChild(article);

    if (window.lucide) window.lucide.createIcons();
    return true;
  }

  function openWidget(id, options = {}) {
    if (!ensureTransientWidget(id)) return false;

    // 외부 hashtag 시스템이 호출하면 패널을 열고 해당 위젯 집중보기
    if (
      document.body.classList.contains('right-panel-closed') &&
      typeof window.toggleRightPanel === 'function'
    ) {
      window.toggleRightPanel();
    }

    if (options.focus !== false) setFocus(id);

    const article = grid.querySelector(`[data-widget-slot="${id}"]`);
    if (article) {
      article.classList.add('is-highlighted');
      window.setTimeout(() => article.classList.remove('is-highlighted'), 650);
    }

    return true;
  }

  function closeFocus() {
    const previous = focusedId;
    setFocus(null);

    // 임시 위젯은 집중보기 종료 시 기본 배치에서 제거
    if (previous && transientIds.has(previous)) {
      transientIds.delete(previous);
      delete layout[previous];
      const article = grid.querySelector(`[data-widget-slot="${previous}"]`);
      article?.remove();
      refreshAllRects();
    }
  }

  function resetLayout() {
    setFocus(null);
    layout = clone(DEFAULT_LAYOUT);
    transientIds.clear();
    saveLayout();
    render();
  }

  function render() {
    if (!grid) return;
    grid.replaceChildren();

    Object.keys(layout).forEach((id) => {
      const article = createArticle(id);
      if (article) grid.appendChild(article);
    });

    if (window.lucide) window.lucide.createIcons();
  }

  function mount() {
    root = document.getElementById('rightPanelDashboard');
    if (!root || root.dataset.dashboardMounted === 'true') return;

    layout = loadLayout();

    root.innerHTML = `
      <button type="button"
              class="dashboard-focus-back"
              aria-label="대시보드로 돌아가기"
              title="대시보드로 돌아가기"
              hidden>
        <i data-lucide="arrow-left"></i>
      </button>

      <section class="right-panel-dashboard__grid"
               aria-label="대시보드 위젯"></section>
    `;

    grid = root.querySelector('.right-panel-dashboard__grid');

    root.querySelector('.dashboard-focus-back').addEventListener('click', closeFocus);

    root.addEventListener('click', (event) => {
      const expand = event.target.closest('[data-widget-expand]');
      if (expand) {
        event.stopPropagation();
        setFocus(expand.dataset.widgetExpand);
      }
    });

    render();

    root.dataset.dashboardMounted = 'true';

    if (window.lucide) window.lucide.createIcons();
  }

  window.GaemiGTPDashboard = {
    mount,
    openWidget,
    closeFocus,
    resetLayout,
    saveLayout,
    widgetSlots: WIDGETS.map((widget) => ({ ...widget })),
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount, { once: true });
  } else {
    mount();
  }
})();
