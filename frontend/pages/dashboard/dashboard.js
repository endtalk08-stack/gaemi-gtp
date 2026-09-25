/* Dashboard v8.3 — Toss-style binary split layout engine.
   핵심:
   - 좌표 그리드 대신 Split Tree 사용
   - 빈 공간 없이 항상 직사각형으로 채움
   - 경계선을 움직이면 인접 패널 비율이 같이 변함
   - 패널 이동 시 위/아래/왼쪽/오른쪽 분할로 트리를 재구성
   - 레이아웃 자동 저장
*/
(function () {
  'use strict';

  const STORAGE_KEY = 'gaemi.dashboard.split-tree.v8.3';
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
  let focusedId = null;
  let draggingId = null;
  let dropState = null;

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
    /* top 52% / bottom 48%
       top: chart 66% | market 34%
       bottom: news | economic | ranking | earnings
    */
    return split(
      'column',
      0.52,
      split('row', 0.66, panel('chart'), panel('market-state')),
      split(
        'row',
        0.5,
        split('row', 0.5, panel('news'), panel('economic')),
        split('row', 0.5, panel('ranking'), panel('earnings'))
      )
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
      if (node.id === id) return { node: null, removed: node };
      return { node, removed: null };
    }

    const left = removePanel(node.a, id);
    if (left.removed) {
      if (!left.node) return { node: node.b, removed: left.removed };
      return {
        node: { ...node, a: left.node },
        removed: left.removed,
      };
    }

    const right = removePanel(node.b, id);
    if (right.removed) {
      if (!right.node) return { node: node.a, removed: right.removed };
      return {
        node: { ...node, b: right.node },
        removed: right.removed,
      };
    }

    return { node, removed: null };
  }

  function insertAroundTarget(node, targetId, sourceNode, zone) {
    if (!node) return node;

    if (node.type === 'panel') {
      if (node.id !== targetId) return node;

      const horizontal = zone === 'left' || zone === 'right';
      const direction = horizontal ? 'row' : 'column';
      const sourceFirst = zone === 'left' || zone === 'top';

      return sourceFirst
        ? split(direction, 0.5, sourceNode, node)
        : split(direction, 0.5, node, sourceNode);
    }

    return {
      ...node,
      a: insertAroundTarget(node.a, targetId, sourceNode, zone),
      b: insertAroundTarget(node.b, targetId, sourceNode, zone),
    };
  }

  function addPanel(id) {
    if (!widgetById(id) || containsPanel(tree, id)) return false;
    tree = split('row', 0.74, tree, panel(id));
    saveTree();
    render();
    return true;
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

    article.innerHTML = `
      <div class="dashboard-widget-slot__head" draggable="true">
        <span class="dashboard-widget-slot__title">${widget.title}</span>
        <button type="button"
                class="dashboard-widget-slot__expand"
                data-expand="${id}"
                aria-label="${widget.title} 크게 보기"
                title="크게 보기">
          <i data-lucide="maximize-2"></i>
        </button>
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

    const bWrap = document.createElement('div');
    bWrap.className = 'dashboard-split__pane dashboard-split__pane--b';

    const divider = document.createElement('div');
    divider.className = 'dashboard-split__divider';
    divider.setAttribute('role', 'separator');
    divider.setAttribute('aria-label', '패널 크기 조절');

    if (node.direction === 'row') {
      aWrap.style.flexBasis = `${node.ratio * 100}%`;
      bWrap.style.flexBasis = `${(1 - node.ratio) * 100}%`;
    } else {
      aWrap.style.flexBasis = `${node.ratio * 100}%`;
      bWrap.style.flexBasis = `${(1 - node.ratio) * 100}%`;
    }

    aWrap.appendChild(renderNode(node.a));
    bWrap.appendChild(renderNode(node.b));

    el.append(aWrap, divider, bWrap);
    bindDivider(divider, el, node);
    return el;
  }

  function renderNode(node) {
    return node.type === 'panel' ? createPanelNode(node.id) : createSplitNode(node);
  }

  function bindDivider(divider, splitEl, node) {
    divider.addEventListener('pointerdown', (event) => {
      if (focusedId) return;

      event.preventDefault();
      divider.setPointerCapture?.(event.pointerId);
      splitEl.classList.add('is-resizing');

      const rect = splitEl.getBoundingClientRect();

      function move(e) {
        let ratio;
        if (node.direction === 'row') {
          ratio = (e.clientX - rect.left) / rect.width;
        } else {
          ratio = (e.clientY - rect.top) / rect.height;
        }

        node.ratio = clampRatio(ratio);

        const a = splitEl.querySelector(':scope > .dashboard-split__pane--a');
        const b = splitEl.querySelector(':scope > .dashboard-split__pane--b');
        a.style.flexBasis = `${node.ratio * 100}%`;
        b.style.flexBasis = `${(1 - node.ratio) * 100}%`;
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
    const x = (event.clientX - rect.left) / rect.width;
    const y = (event.clientY - rect.top) / rect.height;

    const dx = x - 0.5;
    const dy = y - 0.5;

    if (Math.abs(dx) > Math.abs(dy)) {
      return dx < 0 ? 'left' : 'right';
    }
    return dy < 0 ? 'top' : 'bottom';
  }

  function setDropZone(article, zone) {
    article.dataset.dropZone = zone || '';
  }

  function bindPanelDnD(article, id) {
    const head = article.querySelector('.dashboard-widget-slot__head');

    head.addEventListener('dragstart', (event) => {
      if (focusedId) {
        event.preventDefault();
        return;
      }

      draggingId = id;
      article.classList.add('is-dragging');

      if (event.dataTransfer) {
        event.dataTransfer.effectAllowed = 'move';
        event.dataTransfer.setData('text/plain', id);
      }
    });

    head.addEventListener('dragend', () => {
      draggingId = null;
      dropState = null;
      root.querySelectorAll('.dashboard-widget-slot').forEach((el) => {
        el.classList.remove('is-dragging');
        setDropZone(el, '');
      });
    });

    article.addEventListener('dragover', (event) => {
      if (!draggingId || draggingId === id) return;
      event.preventDefault();

      const zone = getDropZone(article, event);
      dropState = { targetId: id, zone };
      setDropZone(article, zone);

      if (event.dataTransfer) event.dataTransfer.dropEffect = 'move';
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
      const zone = getDropZone(article, event);

      const removed = removePanel(tree, sourceId);
      if (!removed.removed || !removed.node) return;

      tree = insertAroundTarget(removed.node, id, removed.removed, zone);
      saveTree();
      draggingId = null;
      dropState = null;
      render();
    });
  }

  function setFocus(id) {
    focusedId = id || null;
    root.classList.toggle('is-widget-focused', !!focusedId);

    root.querySelectorAll('.dashboard-widget-slot').forEach((article) => {
      article.classList.toggle(
        'is-focused',
        article.dataset.widgetSlot === focusedId
      );
    });

    const back = root.querySelector('.dashboard-focus-back');
    if (back) back.hidden = !focusedId;
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

    if (options.focus !== false) {
      requestAnimationFrame(() => setFocus(id));
    }

    return true;
  }

  function resetLayout() {
    setFocus(null);
    splitSeq = 0;
    tree = defaultTree();
    saveTree();
    render();
  }

  function render() {
    if (!stage) return;

    const wasFocused = focusedId;
    stage.replaceChildren(renderNode(tree));

    if (window.lucide) window.lucide.createIcons();
    if (wasFocused) setFocus(wasFocused);
  }

  function mount() {
    root = document.getElementById('rightPanelDashboard');
    if (!root || root.dataset.dashboardMounted === 'true') return;

    tree = loadTree();

    root.innerHTML = `
      <button type="button"
              class="dashboard-focus-back"
              aria-label="대시보드로 돌아가기"
              title="대시보드로 돌아가기"
              hidden>
        <i data-lucide="arrow-left"></i>
      </button>
      <section class="dashboard-tree-stage"
               aria-label="대시보드 패널 레이아웃"></section>
    `;

    stage = root.querySelector('.dashboard-tree-stage');

    root.querySelector('.dashboard-focus-back').addEventListener('click', () => {
      setFocus(null);
    });

    root.addEventListener('click', (event) => {
      const expand = event.target.closest('[data-expand]');
      if (!expand) return;
      event.stopPropagation();
      setFocus(expand.dataset.expand);
    });

    render();
    root.dataset.dashboardMounted = 'true';

    if (window.lucide) window.lucide.createIcons();
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
