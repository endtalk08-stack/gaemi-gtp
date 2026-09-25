/* Dashboard v8.5 — responsive workspace grid
   핵심 원리:
   - 채팅 폭 자체가 아니라 '오른쪽 대시보드의 실제 가로폭'을 ResizeObserver로 감시한다.
   - 넓음(>=1200): 3열, 차트는 2열 차지 -> 차트 + 보조위젯 / 아래 3개
   - 중간(620~1199): 2열, 차트는 2열 전체 -> 차트 1개 / 아래 2개씩
   - 좁음(<620): 1열 -> 위젯 1개씩 세로
   - 위젯은 하나씩 드래그 순서 이동
   - 개별 전체화면/집중보기 없음
   - 채팅/왼쪽 사이드바/오른쪽 패널 폭은 이 파일에서 건드리지 않음
*/
(function () {
  'use strict';

  const STORAGE_KEY = 'gaemi.dashboard.responsive-grid.v8.5';

  const WIDGETS = [
    { id: 'chart', title: '차트', widgetKey: 'chart', span: 2 },
    { id: 'market-state', title: '시장 상태', widgetKey: 'market-state', span: 1 },
    { id: 'news', title: '뉴스', widgetKey: 'news', span: 1 },
    { id: 'economic', title: '경제일정', widgetKey: 'economic', span: 1 },
    { id: 'ranking', title: '실시간 순위', widgetKey: 'ranking', span: 1 },
    { id: 'earnings', title: '실적', widgetKey: 'earnings', span: 1 },
    { id: 'order', title: '주문', widgetKey: 'order', span: 1 },
    { id: 'orderbook', title: '호가', widgetKey: 'orderbook', span: 1 },
    { id: 'community', title: '커뮤니티', widgetKey: 'community', span: 1 },
  ];

  const DEFAULT_ORDER = [
    'chart',
    'market-state',
    'news',
    'economic',
    'ranking',
    'earnings',
  ];

  let root = null;
  let stage = null;
  let resizeObserver = null;
  let cols = 3;
  let order = [];
  let draggingId = null;

  function widgetById(id) {
    return WIDGETS.find((widget) => widget.id === id) || null;
  }

  function loadOrder() {
    try {
      const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
      if (!parsed || !Array.isArray(parsed.order)) return [...DEFAULT_ORDER];

      const seen = new Set();
      const valid = parsed.order.filter((id) => {
        if (!widgetById(id) || seen.has(id)) return false;
        seen.add(id);
        return true;
      });

      return valid.length ? valid : [...DEFAULT_ORDER];
    } catch (_) {
      return [...DEFAULT_ORDER];
    }
  }

  function saveOrder() {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ version: 1, order: [...order] })
      );
    } catch (_) {}
  }

  function getCols(width) {
    if (width < 620) return 1;
    if (width < 1200) return 2;
    return 3;
  }

  function applyResponsiveCols(width) {
    const next = getCols(width);
    if (next === cols && stage?.dataset.cols) return;

    cols = next;
    if (stage) {
      stage.dataset.cols = String(cols);
      stage.style.setProperty('--dashboard-cols', String(cols));
    }
  }

  function mountWidget(article, id) {
    const widget = widgetById(id);
    const mountPoint = article.querySelector('.dashboard-widget-slot__mount');
    const registered =
      window.GaemiGTPWidgets &&
      window.GaemiGTPWidgets[widget.widgetKey || widget.id];

    if (registered && typeof registered.mount === 'function') {
      registered.mount(mountPoint);
      article.classList.add('dashboard-widget-slot--mounted');
    }
  }

  function effectiveSpan(widget) {
    return Math.max(1, Math.min(widget.span || 1, cols));
  }

  function createPanel(id) {
    const widget = widgetById(id);
    const article = document.createElement('article');

    article.className = 'dashboard-widget-slot';
    article.dataset.widgetSlot = id;
    article.style.gridColumn = `span ${effectiveSpan(widget)}`;

    article.innerHTML = `
      <div class="dashboard-widget-slot__head" draggable="true">
        <span class="dashboard-widget-slot__title">${widget.title}</span>
        <span class="dashboard-widget-slot__drag-dot" aria-hidden="true">⋮⋮</span>
      </div>
      <div class="dashboard-widget-slot__content">
        <div class="dashboard-widget-slot__mount"></div>
      </div>
    `;

    mountWidget(article, id);
    bindDrag(article, id);
    return article;
  }

  function bindDrag(article, id) {
    const head = article.querySelector('.dashboard-widget-slot__head');

    head.addEventListener('dragstart', (event) => {
      draggingId = id;
      article.classList.add('is-dragging');

      if (event.dataTransfer) {
        event.dataTransfer.effectAllowed = 'move';
        event.dataTransfer.setData('text/plain', id);
      }
    });

    head.addEventListener('dragend', () => {
      draggingId = null;
      root?.querySelectorAll('.dashboard-widget-slot').forEach((el) => {
        el.classList.remove('is-dragging', 'is-drop-target');
      });
    });

    article.addEventListener('dragover', (event) => {
      if (!draggingId || draggingId === id) return;
      event.preventDefault();

      root?.querySelectorAll('.dashboard-widget-slot').forEach((el) => {
        el.classList.toggle('is-drop-target', el === article);
      });

      if (event.dataTransfer) {
        event.dataTransfer.dropEffect = 'move';
      }
    });

    article.addEventListener('dragleave', (event) => {
      if (!article.contains(event.relatedTarget)) {
        article.classList.remove('is-drop-target');
      }
    });

    article.addEventListener('drop', (event) => {
      if (!draggingId || draggingId === id) return;
      event.preventDefault();

      const sourceIndex = order.indexOf(draggingId);
      const targetIndex = order.indexOf(id);

      if (sourceIndex < 0 || targetIndex < 0) return;

      const next = [...order];
      const [moved] = next.splice(sourceIndex, 1);
      next.splice(targetIndex, 0, moved);

      order = next;
      draggingId = null;
      saveOrder();
      render();
    });
  }

  function render() {
    if (!stage) return;

    const styles = getComputedStyle(stage);
    // ResizeObserver.contentRect와 동일하게 패딩·스크롤바를 제외한 폭을 사용한다.
    const width = Math.max(0, stage.clientWidth
      - (parseFloat(styles.paddingLeft) || 0)
      - (parseFloat(styles.paddingRight) || 0));
    applyResponsiveCols(width);

    stage.replaceChildren(...order.map(createPanel));
  }

  function addPanel(id) {
    if (!widgetById(id) || order.includes(id)) return false;

    order = [...order, id];
    saveOrder();
    render();
    return true;
  }

  function openWidget(id) {
    if (!widgetById(id)) return false;
    if (!order.includes(id)) addPanel(id);

    if (
      document.body.classList.contains('right-panel-closed') &&
      typeof window.toggleRightPanel === 'function'
    ) {
      window.toggleRightPanel();
    }

    requestAnimationFrame(() => {
      const panel = root?.querySelector(`[data-widget-slot="${CSS.escape(id)}"]`);
      panel?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    });

    return true;
  }

  function resetLayout() {
    order = [...DEFAULT_ORDER];
    saveOrder();
    render();
  }

  function mount() {
    root = document.getElementById('rightPanelDashboard');
    if (!root || root.dataset.dashboardMounted === 'true') return;

    order = loadOrder();

    root.innerHTML = `
      <section class="dashboard-responsive-grid"
               aria-label="반응형 대시보드 위젯 영역"></section>
    `;

    stage = root.querySelector('.dashboard-responsive-grid');

    resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;

      const width = entry.contentRect.width;
      const nextCols = getCols(width);

      if (nextCols !== cols || !stage.dataset.cols) {
        cols = nextCols;
        stage.dataset.cols = String(cols);
        stage.style.setProperty('--dashboard-cols', String(cols));

        /* chart span이 cols에 맞게 즉시 바뀌도록 재렌더 */
        render();
      }
    });

    resizeObserver.observe(stage);
    render();

    root.dataset.dashboardMounted = 'true';
  }

  window.GaemiGTPDashboard = {
    mount,
    openWidget,
    resetLayout,
    saveLayout: saveOrder,
    widgetSlots: WIDGETS.map((widget) => ({ ...widget })),
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount, { once: true });
  } else {
    mount();
  }
})();
