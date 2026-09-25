/* Dashboard v8.4 — individual widget split layout
   이번 버전의 범위:
   - 채팅/왼쪽 사이드바/오른쪽 패널 폭은 건드리지 않음
   - 위젯 하나씩 드래그 이동
   - 위/아래 크기 조절이 전체 행에 걸리지 않도록 기본 트리를 '열별 독립 분할'로 구성
   - 빈 공간 없이 split tree 유지
   - 개별 위젯 전체화면/집중보기 기능 제거
   - 레이아웃 자동 저장
*/
(function () {
  'use strict';

  /* v8.3의 '위 전체 / 아래 전체' 저장 트리를 다시 불러오지 않도록 새 키 사용 */
  const STORAGE_KEY = 'gaemi.dashboard.split-tree.v8.4-individual';
  const MIN_RATIO = 0.18;
  const MAX_RATIO = 0.82;

  const WIDGETS = [
    { id: 'chart', title: '차트', widgetKey: 'chart' },
    { id: 'market-state', title: '시장 상태', widgetKey: 'market-state' },
    { id: 'news', title: '뉴스', widgetKey: 'news' },
    { id: 'economic', title: '경제일정', widgetKey: 'economic' },
    { id: 'ranking', title: '실시간 순위', widgetKey: 'ranking' },
    { id: 'earnings', title: '실적', widgetKey: 'earnings' },
    { id: 'order', title: '주문', widgetKey: 'order' },
    { id: 'orderbook', title: '호가', widgetKey: 'orderbook' },
    { id: 'community', title: '커뮤니티', widgetKey: 'community' },
  ];

  let splitSeq = 0;
  let root = null;
  let stage = null;
  let tree = null;
  let draggingId = null;

  const panel = (id) => ({ type: 'panel', id });
  const split = (direction, ratio, a, b) => ({
    type: 'split',
    id: `split-${++splitSeq}`,
    direction,
    ratio,
    a,
    b,
  });

  function defaultTree() {
    /*
      핵심: 화면 전체를 먼저 위/아래로 자르지 않는다.

      [ 차트        ] | [ 시장 상태 ] | [ 실적      ]
      [ 뉴스        ] | [ 경제일정   ] | [ 실시간순위 ]

      각 열 안의 가로 경계는 그 열의 위젯 2개만 조절한다.
      따라서 차트/뉴스 높이를 바꿔도 다른 열 전체가 같이 위아래로 움직이지 않는다.
    */
    const col1 = split('column', 0.56, panel('chart'), panel('news'));
    const col2 = split('column', 0.50, panel('market-state'), panel('economic'));
    const col3 = split('column', 0.50, panel('earnings'), panel('ranking'));

    return split(
      'row',
      0.42,
      col1,
      split('row', 0.50, col2, col3)
    );
  }

  function widgetById(id) {
    return WIDGETS.find((widget) => widget.id === id);
  }

  function clampRatio(value) {
    return Math.max(MIN_RATIO, Math.min(MAX_RATIO, value));
  }

  function sanitizeNode(node, seen = new Set()) {
    if (!node || typeof node !== 'object') return null;

    if (node.type === 'panel') {
      if (!widgetById(node.id) || seen.has(node.id)) return null;
      seen.add(node.id);
      return panel(node.id);
    }

    if (node.type === 'split') {
      const a = sanitizeNode(node.a, seen);
      const b = sanitizeNode(node.b, seen);

      if (!a && !b) return null;
      if (!a) return b;
      if (!b) return a;

      return split(
        node.direction === 'column' ? 'column' : 'row',
        clampRatio(Number(node.ratio) || 0.5),
        a,
        b
      );
    }

    return null;
  }

  function loadTree() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
      const restored = saved?.version === 1 ? sanitizeNode(saved.tree) : null;
      return restored || defaultTree();
    } catch (_) {
      return defaultTree();
    }
  }

  function stripRuntimeIds(node) {
    if (!node) return null;
    if (node.type === 'panel') return { type: 'panel', id: node.id };

    return {
      type: 'split',
      direction: node.direction,
      ratio: node.ratio,
      a: stripRuntimeIds(node.a),
      b: stripRuntimeIds(node.b),
    };
  }

  function saveTree() {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ version: 1, tree: stripRuntimeIds(tree) })
      );
    } catch (_) {}
  }

  function containsPanel(node, id) {
    if (!node) return false;
    if (node.type === 'panel') return node.id === id;
    return containsPanel(node.a, id) || containsPanel(node.b, id);
  }

  function removePanel(node, id) {
    if (!node) return { node: null, removed: null };

    if (node.type === 'panel') {
      return node.id === id
        ? { node: null, removed: node }
        : { node, removed: null };
    }

    const fromA = removePanel(node.a, id);
    if (fromA.removed) {
      if (!fromA.node) return { node: node.b, removed: fromA.removed };
      return { node: { ...node, a: fromA.node }, removed: fromA.removed };
    }

    const fromB = removePanel(node.b, id);
    if (fromB.removed) {
      if (!fromB.node) return { node: node.a, removed: fromB.removed };
      return { node: { ...node, b: fromB.node }, removed: fromB.removed };
    }

    return { node, removed: null };
  }

  function insertAroundTarget(node, targetId, sourceNode, zone) {
    if (!node) return node;

    if (node.type === 'panel') {
      if (node.id !== targetId) return node;

      const direction = (zone === 'left' || zone === 'right') ? 'row' : 'column';
      const sourceFirst = zone === 'left' || zone === 'top';

      return sourceFirst
        ? split(direction, 0.50, sourceNode, node)
        : split(direction, 0.50, node, sourceNode);
    }

    return {
      ...node,
      a: insertAroundTarget(node.a, targetId, sourceNode, zone),
      b: insertAroundTarget(node.b, targetId, sourceNode, zone),
    };
  }

  function addPanel(id) {
    if (!widgetById(id) || containsPanel(tree, id)) return false;

    /* 새 위젯은 기존 화면 전체를 다시 자르지 않고 우측 끝 패널 하나를 분할한다. */
    const targetId = findRightmostPanelId(tree);
    tree = targetId
      ? insertAroundTarget(tree, targetId, panel(id), 'right')
      : panel(id);

    saveTree();
    render();
    return true;
  }

  function findRightmostPanelId(node) {
    if (!node) return null;
    if (node.type === 'panel') return node.id;
    return findRightmostPanelId(node.b) || findRightmostPanelId(node.a);
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

  function createPanelNode(id) {
    const widget = widgetById(id);
    const article = document.createElement('article');

    article.className = 'dashboard-widget-slot';
    article.dataset.widgetSlot = id;

    /* 확대/집중보기 버튼 제거: 제목 영역 전체가 드래그 핸들 */
    article.innerHTML = `
      <div class="dashboard-widget-slot__head" draggable="true">
        <span class="dashboard-widget-slot__title">${widget.title}</span>
      </div>
      <div class="dashboard-widget-slot__content">
        <div class="dashboard-widget-slot__mount"></div>
      </div>
      <div class="dashboard-drop-overlay" aria-hidden="true">
        <span data-zone="top"></span>
        <span data-zone="right"></span>
        <span data-zone="bottom"></span>
        <span data-zone="left"></span>
      </div>
    `;

    mountWidget(article, id);
    bindPanelDnD(article, id);
    return article;
  }

  function createSplitNode(node) {
    const el = document.createElement('div');
    el.className = `dashboard-split dashboard-split--${node.direction}`;
    el.dataset.splitId = node.id;

    const aWrap = document.createElement('div');
    aWrap.className = 'dashboard-split__pane dashboard-split__pane--a';
    aWrap.style.flexBasis = `${node.ratio * 100}%`;

    const bWrap = document.createElement('div');
    bWrap.className = 'dashboard-split__pane dashboard-split__pane--b';
    bWrap.style.flexBasis = `${(1 - node.ratio) * 100}%`;

    const divider = document.createElement('div');
    divider.className = 'dashboard-split__divider';
    divider.setAttribute('role', 'separator');
    divider.setAttribute('aria-label', '위젯 크기 조절');

    aWrap.appendChild(renderNode(node.a));
    bWrap.appendChild(renderNode(node.b));

    el.append(aWrap, divider, bWrap);
    bindDivider(divider, el, node);

    return el;
  }

  function renderNode(node) {
    return node.type === 'panel'
      ? createPanelNode(node.id)
      : createSplitNode(node);
  }

  function bindDivider(divider, splitEl, node) {
    divider.addEventListener('pointerdown', (event) => {
      event.preventDefault();
      divider.setPointerCapture?.(event.pointerId);
      splitEl.classList.add('is-resizing');

      const rect = splitEl.getBoundingClientRect();

      function move(e) {
        const rawRatio = node.direction === 'row'
          ? (e.clientX - rect.left) / Math.max(rect.width, 1)
          : (e.clientY - rect.top) / Math.max(rect.height, 1);

        node.ratio = clampRatio(rawRatio);

        const a = splitEl.querySelector(':scope > .dashboard-split__pane--a');
        const b = splitEl.querySelector(':scope > .dashboard-split__pane--b');

        if (a) a.style.flexBasis = `${node.ratio * 100}%`;
        if (b) b.style.flexBasis = `${(1 - node.ratio) * 100}%`;
      }

      function finish() {
        divider.removeEventListener('pointermove', move);
        divider.removeEventListener('pointerup', finish);
        divider.removeEventListener('pointercancel', finish);
        divider.removeEventListener('lostpointercapture', finish);
        splitEl.classList.remove('is-resizing');
        saveTree();
      }

      divider.addEventListener('pointermove', move);
      divider.addEventListener('pointerup', finish);
      divider.addEventListener('pointercancel', finish);
      divider.addEventListener('lostpointercapture', finish);
    });
  }

  function getDropZone(article, event) {
    const rect = article.getBoundingClientRect();
    const x = (event.clientX - rect.left) / Math.max(rect.width, 1);
    const y = (event.clientY - rect.top) / Math.max(rect.height, 1);

    const dx = x - 0.5;
    const dy = y - 0.5;

    return Math.abs(dx) > Math.abs(dy)
      ? (dx < 0 ? 'left' : 'right')
      : (dy < 0 ? 'top' : 'bottom');
  }

  function setDropZone(article, zone) {
    article.dataset.dropZone = zone || '';
  }

  function clearDragUI() {
    if (!root) return;
    root.querySelectorAll('.dashboard-widget-slot').forEach((el) => {
      el.classList.remove('is-dragging');
      setDropZone(el, '');
    });
  }

  function bindPanelDnD(article, id) {
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
      clearDragUI();
    });

    article.addEventListener('dragover', (event) => {
      if (!draggingId || draggingId === id) return;

      event.preventDefault();
      const zone = getDropZone(article, event);
      setDropZone(article, zone);

      if (event.dataTransfer) {
        event.dataTransfer.dropEffect = 'move';
      }
    });

    article.addEventListener('dragleave', (event) => {
      if (!article.contains(event.relatedTarget)) {
        setDropZone(article, '');
      }
    });

    article.addEventListener('drop', (event) => {
      if (!draggingId || draggingId === id) return;

      event.preventDefault();

      const sourceId = draggingId;
      const targetId = id;
      const zone = getDropZone(article, event);

      /* source 한 개만 떼어서 target 주변에 다시 삽입 */
      const removed = removePanel(tree, sourceId);
      if (!removed.removed || !removed.node) {
        draggingId = null;
        clearDragUI();
        return;
      }

      tree = insertAroundTarget(removed.node, targetId, removed.removed, zone);

      draggingId = null;
      saveTree();
      render();
    });
  }

  function openWidget(id, options = {}) {
    if (!widgetById(id)) return false;
    if (!containsPanel(tree, id)) addPanel(id);

    if (
      document.body.classList.contains('right-panel-closed') &&
      typeof window.toggleRightPanel === 'function'
    ) {
      window.toggleRightPanel();
    }

    /* options.focus는 이전 API 호환만 유지하고 실제 확대는 하지 않음 */
    return true;
  }

  function resetLayout() {
    splitSeq = 0;
    tree = defaultTree();
    saveTree();
    render();
  }

  function render() {
    if (!stage || !tree) return;

    stage.replaceChildren(renderNode(tree));

    if (window.lucide) {
      window.lucide.createIcons();
    }
  }

  function mount() {
    root = document.getElementById('rightPanelDashboard');
    if (!root || root.dataset.dashboardMounted === 'true') return;

    tree = loadTree();

    root.innerHTML = `
      <section class="dashboard-tree-stage"
               aria-label="대시보드 패널 레이아웃"></section>
    `;

    stage = root.querySelector('.dashboard-tree-stage');

    render();
    root.dataset.dashboardMounted = 'true';
  }

  window.GaemiGTPDashboard = {
    mount,
    openWidget,
    resetLayout,
    saveLayout: saveTree,
    widgetSlots: WIDGETS.map((widget) => ({ ...widget })),
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount, { once: true });
  } else {
    mount();
  }
})();
