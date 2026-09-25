/* Dashboard v8.1 — layout only; data remains owned by each widget. */
(function () {
  'use strict';
  const STORAGE_KEY = 'gaemi.dashboard.layout.v8.1';
  const WIDGET_SLOTS = [
    { id: 'market-state', title: '시장 상태', widgetKey: 'market-state' },
    { id: 'chart', title: '차트' },
    { id: 'volume', title: '거래량' },
    { id: 'trading-value', title: '거래대금' },
    { id: 'news', title: '뉴스' },
    { id: 'economic', title: '경제일정' },
    { id: 'earnings', title: '실적' },
    { id: 'event', title: '이벤트' },
    { id: 'ranking', title: '순위' },
  ];
  const defaults = () => WIDGET_SLOTS.slice(0, 6).map((slot, index) => ({
    id: slot.id, width: index < 2 ? 2 : 1, height: index < 2 ? 300 : 220,
  }));
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
  function load() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
      const ids = new Set();
      if (!saved || saved.version !== 1 || !Array.isArray(saved.items) || !saved.items.length) return defaults();
      const items = saved.items.filter(item => {
        if (!item || !WIDGET_SLOTS.some(slot => slot.id === item.id) || ids.has(item.id)) return false;
        ids.add(item.id);
        return true;
      }).map(item => ({ id: item.id,
        width: Number.isInteger(item.width) ? clamp(item.width, 1, 4) : 1,
        height: Number.isFinite(item.height) ? clamp(item.height, 180, 720) : 220,
      }));
      return items.length ? items : defaults();
    } catch (_) { return defaults(); }
  }
  function mount() {
    const root = document.getElementById('rightPanelDashboard');
    if (!root || root.dataset.dashboardMounted === 'true') return;
    let items = load();
    root.innerHTML = `
      <div class="dashboard-toolbar">
        <strong>대시보드</strong>
        <select class="dashboard-add" aria-label="위젯 추가"></select>
        <button type="button" data-action="save">레이아웃 저장</button>
        <button type="button" data-action="reset">기본 2+4</button>
        <span class="dashboard-status" role="status" aria-live="polite"></span>
      </div>
      <p class="dashboard-hint">제목을 끌어 이동 · 오른쪽 아래에서 크기 조절 · 방향키로도 조작할 수 있습니다</p>
      <section class="right-panel-dashboard__grid" aria-label="대시보드 위젯"></section>
      <dialog class="dashboard-expanded" aria-label="위젯 크게 보기">
        <button type="button" class="dashboard-expanded__close">닫기 ✕</button>
        <div class="dashboard-expanded__content"></div>
      </dialog>`;
    const grid = root.querySelector('.right-panel-dashboard__grid');
    const status = root.querySelector('.dashboard-status');
    const select = root.querySelector('.dashboard-add');
    const dialog = root.querySelector('dialog');
    let expanded = null;
    function dirty() { status.textContent = '변경됨 · 저장 버튼을 눌러 주세요'; }
    function apply(article, item) {
      article.style.setProperty('--widget-span', item.width);
      article.style.setProperty('--widget-height', `${item.height}px`);
    }
    function syncOrder() {
      items.forEach(item => grid.appendChild(grid.querySelector(`[data-widget-slot="${item.id}"]`)));
    }
    function options() {
      select.innerHTML = '<option value="">위젯 추가</option>';
      WIDGET_SLOTS.filter(slot => !items.some(item => item.id === slot.id)).forEach(slot => {
        select.add(new Option(slot.title, slot.id));
      });
      select.disabled = items.length === WIDGET_SLOTS.length;
    }
    function create(item) {
      const slot = WIDGET_SLOTS.find(slot => slot.id === item.id);
      const article = document.createElement('article');
      article.className = 'dashboard-widget-slot';
      article.dataset.widgetSlot = item.id;
      article.setAttribute('aria-label', slot.title);
      article.innerHTML = `
        <div class="dashboard-widget-slot__head">
          <button type="button" class="dashboard-widget-slot__drag" aria-label="${slot.title} 이동 (방향키 지원)">⠿ <span>${slot.title}</span></button>
          <button type="button" class="dashboard-widget-slot__expand" aria-label="${slot.title} 크게 보기" title="크게 보기">⛶</button>
        </div>
        <div class="dashboard-widget-slot__body">${slot.title} 위젯 영역</div>
        <div class="dashboard-widget-slot__mount"></div>
        <button type="button" class="dashboard-widget-slot__resize" aria-label="${slot.title} 크기 조절 (방향키 지원)" title="끌어서 크기 조절">◢</button>`;
      apply(article, item);
      const widget = window.GaemiGTPWidgets && window.GaemiGTPWidgets[slot.widgetKey];
      if (widget && typeof widget.mount === 'function') {
        widget.mount(article.querySelector('.dashboard-widget-slot__mount'));
        article.classList.add('dashboard-widget-slot--mounted');
      }
      const drag = article.querySelector('.dashboard-widget-slot__drag');
      const resize = article.querySelector('.dashboard-widget-slot__resize');
      function moveTo(targetId) {
        const from = items.indexOf(item);
        const to = items.findIndex(entry => entry.id === targetId);
        if (to < 0 || from === to) return;
        items.splice(from, 1);
        items.splice(to, 0, item);
        syncOrder();
        dirty();
      }
      function gesture(handle, resizing) {
        handle.addEventListener('pointerdown', event => {
          if (event.button !== 0 || expanded) return;
          event.preventDefault();
          const x = event.clientX, y = event.clientY;
          const width = item.width, height = item.height;
          const columns = getComputedStyle(grid).gridTemplateColumns.split(' ').length;
          const step = (grid.clientWidth + 12) / columns;
          let targetId = null;
          let target = null;
          handle.setPointerCapture(event.pointerId);
          article.classList.add(resizing ? 'is-resizing' : 'is-dragging');
          function update(e) {
            if (resizing) {
              item.width = clamp(width + Math.round((e.clientX - x) / step), 1, columns);
              item.height = clamp(height + e.clientY - y, 180, 720);
              apply(article, item);
            } else {
              if (target) target.classList.remove('is-drop-target');
              target = document.elementFromPoint(e.clientX, e.clientY)?.closest('.dashboard-widget-slot');
              targetId = target && target.parentElement === grid && target !== article ? target.dataset.widgetSlot : null;
              if (targetId) target.classList.add('is-drop-target');
            }
          }
          function finish(e) {
            handle.removeEventListener('pointermove', update);
            handle.removeEventListener('pointerup', finish);
            handle.removeEventListener('pointercancel', finish);
            handle.removeEventListener('lostpointercapture', finish);
            if (handle.hasPointerCapture(event.pointerId)) handle.releasePointerCapture(event.pointerId);
            article.classList.remove('is-resizing', 'is-dragging');
            if (target) target.classList.remove('is-drop-target');
            if (e.type === 'pointerup') {
              if (resizing) dirty();
              else if (targetId) moveTo(targetId);
            } else if (resizing) {
              item.width = width; item.height = height; apply(article, item);
            }
            handle.focus();
          }
          handle.addEventListener('pointermove', update);
          handle.addEventListener('pointerup', finish);
          handle.addEventListener('pointercancel', finish);
          handle.addEventListener('lostpointercapture', finish);
        });
      }
      gesture(drag, false);
      gesture(resize, true);
      drag.addEventListener('keydown', event => {
        if (!event.key.startsWith('Arrow') || expanded) return;
        event.preventDefault();
        const offset = ['ArrowLeft', 'ArrowUp'].includes(event.key) ? -1 : 1;
        const next = items[items.indexOf(item) + offset];
        if (next) moveTo(next.id);
        drag.focus();
      });
      resize.addEventListener('keydown', event => {
        if (!event.key.startsWith('Arrow') || expanded) return;
        event.preventDefault();
        if (event.key === 'ArrowLeft') item.width = clamp(item.width - 1, 1, 4);
        if (event.key === 'ArrowRight') item.width = clamp(item.width + 1, 1, 4);
        if (event.key === 'ArrowUp') item.height = clamp(item.height - 20, 180, 720);
        if (event.key === 'ArrowDown') item.height = clamp(item.height + 20, 180, 720);
        apply(article, item); dirty();
      });
      article.querySelector('.dashboard-widget-slot__expand').addEventListener('click', () => {
        const placeholder = document.createComment('expanded widget');
        article.replaceWith(placeholder);
        expanded = { article, placeholder };
        dialog.querySelector('.dashboard-expanded__content').appendChild(article);
        dialog.showModal();
        dialog.querySelector('.dashboard-expanded__close').focus();
      });
      return article;
    }
    dialog.querySelector('.dashboard-expanded__close').addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', () => {
      if (!expanded) return;
      const { article, placeholder } = expanded;
      placeholder.replaceWith(article);
      expanded = null;
      article.querySelector('.dashboard-widget-slot__expand').focus();
    });
    function render() {
      grid.replaceChildren(...items.map(create));
      options();
    }
    select.addEventListener('change', () => {
      if (!select.value || items.some(item => item.id === select.value)) return;
      const item = { id: select.value, width: 1, height: 220 };
      items.push(item); grid.appendChild(create(item)); options(); dirty();
    });
    root.querySelector('[data-action="save"]').addEventListener('click', () => {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ version: 1, items }));
        status.textContent = '이 브라우저에 레이아웃을 저장했습니다';
      } catch (_) { status.textContent = '저장하지 못했습니다. 브라우저 저장 공간 설정을 확인해 주세요'; }
    });
    root.querySelector('[data-action="reset"]').addEventListener('click', () => {
      items = defaults(); render(); dirty();
    });
    render();
    root.dataset.dashboardMounted = 'true';
  }
  window.GaemiGTPDashboard = { mount, widgetSlots: WIDGET_SLOTS.map(slot => ({ ...slot })) };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount, { once: true });
  else mount();
})();
