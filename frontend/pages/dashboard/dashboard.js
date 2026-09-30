/* Dashboard page shell.
   STEP 2: 12-column test grid only. Existing panel/news/API structure is untouched. */
(function () {
  'use strict';

  const STORAGE_KEY = 'gaemi.dashboard.responsive-grid.step2';
  const MIN_HEIGHT = 220;
  const MIN_SPAN = 2;
  const DEFAULTS = [
    { id: 'dashboard-test-a', title: '테스트 위젯 A', span12: 8, height: 420 },
    { id: 'dashboard-test-b', title: '테스트 위젯 B', span12: 4, height: 420 },
    { id: 'dashboard-test-c', title: '테스트 위젯 C', span12: 4, height: 320 },
    { id: 'dashboard-test-d', title: '테스트 위젯 D', span12: 4, height: 320 },
    { id: 'dashboard-test-e', title: '테스트 위젯 E', span12: 4, height: 320 },
  ];

  let widgets = loadLayout();
  let editMode = false;
  let dragId = null;
  let resizeCleanup = null;

  function cloneDefaults() {
    return DEFAULTS.map((item) => ({ ...item }));
  }

  function loadLayout() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
      if (Array.isArray(saved) && saved.length === DEFAULTS.length) {
        const ids = new Set(DEFAULTS.map((item) => item.id));
        if (saved.every((item) => ids.has(item.id))) {
          return saved.map((item) => ({
            id: item.id,
            title: DEFAULTS.find((base) => base.id === item.id).title,
            span12: clampSpan(item.span12),
            height: Math.max(MIN_HEIGHT, Number(item.height) || 320),
          }));
        }
      }
    } catch (_) {}
    return cloneDefaults();
  }

  function saveLayout() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(
        widgets.map(({ id, span12, height }) => ({ id, span12, height }))
      ));
    } catch (_) {}
  }

  function clampSpan(value) {
    return Math.max(MIN_SPAN, Math.min(12, Math.round(Number(value) || 4)));
  }

  function getRows(list) {
    const rows = [];
    let row = [];
    let used = 0;
    list.forEach((widget) => {
      const span = clampSpan(widget.span12);
      if (row.length && used + span > 12) {
        rows.push(row);
        row = [];
        used = 0;
      }
      row.push(widget.id);
      used += span;
      if (used >= 12) {
        rows.push(row);
        row = [];
        used = 0;
      }
    });
    if (row.length) rows.push(row);
    return rows;
  }

  function normalizeRows(anchorId) {
    getRows(widgets).forEach((row) => {
      const anchor = widgets.find((item) => item.id === anchorId && row.includes(item.id));
      const first = widgets.find((item) => item.id === row[0]);
      const height = Math.max(MIN_HEIGHT, Math.round((anchor || first || {}).height || 320));
      widgets = widgets.map((item) => row.includes(item.id) ? { ...item, height } : item);
    });
  }

  function createCard(widget) {
    const card = document.createElement('article');
    card.className = 'dashboard-test-widget';
    card.dataset.widgetId = widget.id;
    card.style.gridColumn = `span ${clampSpan(widget.span12)}`;
    card.style.height = `${Math.max(MIN_HEIGHT, widget.height)}px`;

    const header = document.createElement('header');
    header.className = 'dashboard-test-widget__header';
    header.draggable = editMode;
    header.innerHTML = `<span>${widget.title}</span><span class="dashboard-test-widget__drag" aria-hidden="true">⋮⋮</span>`;
    header.addEventListener('dragstart', (event) => {
      if (!editMode) return event.preventDefault();
      dragId = widget.id;
      card.classList.add('is-dragging');
      try { event.dataTransfer.setData('text/plain', widget.id); } catch (_) {}
      event.dataTransfer.effectAllowed = 'move';
    });
    header.addEventListener('dragend', () => {
      dragId = null;
      card.classList.remove('is-dragging');
      document.querySelectorAll('.dashboard-test-widget.is-drop-target').forEach((el) => el.classList.remove('is-drop-target'));
    });

    const body = document.createElement('div');
    body.className = 'dashboard-test-widget__body';
    body.innerHTML = '<span>빈 위젯</span><small>배치 기능 테스트용</small>';

    const resize = document.createElement('button');
    resize.type = 'button';
    resize.className = 'dashboard-test-widget__resize';
    resize.setAttribute('aria-label', `${widget.title} 크기 조절`);
    resize.addEventListener('mousedown', (event) => startResize(event, widget.id));

    card.addEventListener('dragover', (event) => {
      if (!editMode || !dragId || dragId === widget.id) return;
      event.preventDefault();
      card.classList.add('is-drop-target');
    });
    card.addEventListener('dragleave', () => card.classList.remove('is-drop-target'));
    card.addEventListener('drop', (event) => {
      if (!editMode || !dragId || dragId === widget.id) return;
      event.preventDefault();
      const from = widgets.findIndex((item) => item.id === dragId);
      const to = widgets.findIndex((item) => item.id === widget.id);
      if (from < 0 || to < 0) return;
      const [moved] = widgets.splice(from, 1);
      widgets.splice(to, 0, moved);
      normalizeRows(moved.id);
      saveLayout();
      renderGrid();
    });

    card.append(header, body, resize);
    return card;
  }

  function startResize(event, id) {
    if (!editMode) return;
    event.preventDefault();
    event.stopPropagation();

    const root = document.getElementById('rightPanelDashboard');
    const grid = root && root.querySelector('.dashboard-test-grid');
    const target = widgets.find((item) => item.id === id);
    if (!grid || !target) return;

    if (resizeCleanup) resizeCleanup();
    const startX = event.clientX;
    const startY = event.clientY;
    const startSpan = clampSpan(target.span12);
    const startHeight = Math.max(MIN_HEIGHT, target.height);
    const styles = getComputedStyle(grid);
    const gap = parseFloat(styles.columnGap) || 16;
    const width = grid.getBoundingClientRect().width;
    const unit = (width - gap * 11) / 12 + gap;

    document.body.classList.add('dashboard-grid-resizing');

    const move = (moveEvent) => {
      const nextSpan = clampSpan(startSpan + Math.round((moveEvent.clientX - startX) / unit));
      const nextHeight = Math.max(MIN_HEIGHT, Math.round(startHeight + moveEvent.clientY - startY));
      widgets = widgets.map((item) => item.id === id ? { ...item, span12: nextSpan, height: nextHeight } : item);
      const activeRow = getRows(widgets).find((row) => row.includes(id)) || [id];
      widgets = widgets.map((item) => activeRow.includes(item.id) ? { ...item, height: nextHeight } : item);
      renderGrid();
    };

    const up = () => {
      normalizeRows(id);
      saveLayout();
      renderGrid();
      cleanup();
    };

    const cleanup = () => {
      document.body.classList.remove('dashboard-grid-resizing');
      document.removeEventListener('mousemove', move);
      document.removeEventListener('mouseup', up);
      resizeCleanup = null;
    };

    resizeCleanup = cleanup;
    document.addEventListener('mousemove', move);
    document.addEventListener('mouseup', up);
  }

  function renderGrid() {
    const root = document.getElementById('rightPanelDashboard');
    if (!root || root.querySelector('#rightPanelNews')) return;
    const grid = root.querySelector('.dashboard-test-grid');
    if (!grid) return;
    grid.replaceChildren(...widgets.map(createCard));
    root.classList.toggle('dashboard-layout-editing', editMode);
  }

  function resetLayout() {
    widgets = cloneDefaults();
    try { localStorage.removeItem(STORAGE_KEY); } catch (_) {}
    renderGrid();
  }

  function mount() {
    const root = document.getElementById('rightPanelDashboard');
    if (!root || root.dataset.dashboardMounted === 'true') return;

    // The saved Marketaux news page owns this same container when its tab is active.
    if (root.querySelector('#rightPanelNews')) {
      root.dataset.dashboardMounted = 'true';
      return;
    }

    root.replaceChildren();

    const shell = document.createElement('section');
    shell.className = 'dashboard-test-shell';

    const toolbar = document.createElement('div');
    toolbar.className = 'dashboard-test-toolbar';

    const editButton = document.createElement('button');
    editButton.type = 'button';
    editButton.className = 'dashboard-test-toolbar__button';
    editButton.addEventListener('click', () => {
      editMode = !editMode;
      editButton.textContent = editMode ? '편집 완료 · 잠그기' : '레이아웃 잠김 · 편집하기';
      renderGrid();
    });
    editButton.textContent = '레이아웃 잠김 · 편집하기';

    const resetButton = document.createElement('button');
    resetButton.type = 'button';
    resetButton.className = 'dashboard-test-toolbar__button dashboard-test-toolbar__button--sub';
    resetButton.textContent = '기본 배치';
    resetButton.addEventListener('click', resetLayout);

    toolbar.append(editButton, resetButton);

    const grid = document.createElement('div');
    grid.className = 'dashboard-test-grid';
    shell.append(toolbar, grid);
    root.append(shell);
    root.dataset.dashboardMounted = 'true';
    renderGrid();
  }

  window.GaemiGTPDashboard = {
    mount,
    openWidget: () => false,
    resetLayout,
    saveLayout,
    get widgetSlots() { return widgets.map((item) => item.id); },
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount, { once: true });
  } else {
    mount();
  }
})();
