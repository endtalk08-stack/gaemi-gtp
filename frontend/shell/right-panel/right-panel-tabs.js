/* Right Panel Tabs — v7.5
   책임: 오른쪽 패널의 상단 탭/추가/삭제/선택 상태만 담당한다.
   책임 밖: 위젯 데이터, API, DB, 분석, 패널 열기/닫기, 패널 너비.
*/
(function () {
  'use strict';

  const TABS_KEY = 'gaemiGTP_right_panel_tabs_v1';
  const DEFAULT_TABS = [
    { id: 'dashboard', label: '대시보드', icon: 'layout-dashboard', closable: false },
    { id: 'auto-trade', label: '자동매매', icon: 'bot', closable: true },
  ];

  let tabs = [];
  let activeTabId = 'dashboard';

  function readState() {
    try {
      const raw = localStorage.getItem(TABS_KEY);
      if (!raw) return null;
      const state = JSON.parse(raw);
      if (!state || !Array.isArray(state.tabs)) return null;
      const cleanTabs = state.tabs
        .filter(t => t && typeof t.id === 'string' && typeof t.label === 'string')
        .map(t => ({
          id: t.id,
          label: t.label,
          icon: typeof t.icon === 'string' ? t.icon : 'square-chart-gantt',
          closable: t.id !== 'dashboard',
        }));
      return {
        tabs: cleanTabs.length ? cleanTabs : null,
        activeTabId: typeof state.activeTabId === 'string' ? state.activeTabId : 'dashboard',
      };
    } catch (e) {
      console.warn('[gaemiGTP] right panel tabs read warning:', e);
      return null;
    }
  }

  function saveState() {
    try {
      localStorage.setItem(TABS_KEY, JSON.stringify({ tabs, activeTabId }));
    } catch (e) {
      console.warn('[gaemiGTP] right panel tabs save warning:', e);
    }
  }

  function getTabList() {
    return document.getElementById('rightPanelTabs');
  }

  function getContentRoot() {
    return document.getElementById('rightPanelContent');
  }

  function getView(id) {
    return document.getElementById(`rightPanelTabView-${id}`);
  }

  function makePlaceholderView(tab) {
    const root = getContentRoot();
    if (!root || getView(tab.id)) return;

    const section = document.createElement('section');
    section.id = `rightPanelTabView-${tab.id}`;
    section.className = 'right-panel-tab-view';
    section.dataset.tabView = tab.id;
    section.setAttribute('role', 'tabpanel');
    section.setAttribute('aria-label', tab.label);
    section.innerHTML = `
      <div class="right-panel-tab-placeholder">
        <div class="right-panel-tab-placeholder__icon"><i data-lucide="square-chart-gantt"></i></div>
        <div class="right-panel-tab-placeholder__title">${escapeHtml(tab.label)}</div>
        <div class="right-panel-tab-placeholder__text">이 탭에 원하는 분석 화면을 구성할 수 있습니다.</div>
      </div>
    `;
    root.appendChild(section);
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function renderTabs() {
    const list = getTabList();
    if (!list) return;

    list.innerHTML = '';

    tabs.forEach(tab => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = `right-panel-tab${activeTabId === tab.id ? ' is-active' : ''}`;
      button.dataset.rightPanelTab = tab.id;
      button.setAttribute('role', 'tab');
      button.setAttribute('aria-selected', activeTabId === tab.id ? 'true' : 'false');
      button.title = tab.label;

      const icon = document.createElement('i');
      icon.setAttribute('data-lucide', tab.icon || 'square-chart-gantt');
      icon.className = 'right-panel-tab__icon';
      button.appendChild(icon);

      const label = document.createElement('span');
      label.className = 'right-panel-tab__label';
      label.textContent = tab.label;
      button.appendChild(label);

      if (tab.closable) {
        const close = document.createElement('span');
        close.className = 'right-panel-tab__close';
        close.dataset.rightPanelTabClose = tab.id;
        close.setAttribute('role', 'button');
        close.setAttribute('aria-label', `${tab.label} 탭 닫기`);
        close.title = '탭 닫기';
        close.innerHTML = '<i data-lucide="x"></i>';
        button.appendChild(close);
      }

      list.appendChild(button);
    });

    const add = document.createElement('button');
    add.type = 'button';
    add.className = 'right-panel-tab-add';
    add.dataset.rightPanelTabAdd = 'true';
    add.setAttribute('aria-label', '새 탭 추가');
    add.title = '새 탭 추가';
    add.innerHTML = '<i data-lucide="plus"></i>';
    list.appendChild(add);

    if (window.lucide) window.lucide.createIcons();
  }

  function mountTabPage(tab) {
    if (!tab) return;
    if (tab.id === 'auto-trade') {
      const root = document.getElementById('rightPanelAutoTrade');
      if (root && window.GaemiGTPAutoTrade && typeof window.GaemiGTPAutoTrade.mount === 'function') {
        window.GaemiGTPAutoTrade.mount(root);
      }
      return;
    }
  }

  function setActiveTab(id, persist = true) {
    if (!tabs.some(t => t.id === id)) return;
    activeTabId = id;

    tabs.forEach(tab => {
      if (tab.id === 'auto-trade') {
        mountTabPage(tab);
      } else if (tab.id !== 'dashboard' && !getView(tab.id)) {
        makePlaceholderView(tab);
      }
    });

    document.querySelectorAll('[data-tab-view]').forEach(view => {
      const active = view.dataset.tabView === activeTabId;
      view.hidden = !active;
      view.setAttribute('aria-hidden', active ? 'false' : 'true');
    });

    renderTabs();
    if (persist) saveState();
  }

  function nextCustomLabel() {
    let n = 1;
    const existing = new Set(tabs.map(t => t.label));
    while (existing.has(`분석 #${n}`)) n += 1;
    return `분석 #${n}`;
  }

  function addTab() {
    const id = `tab_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    const tab = {
      id,
      label: nextCustomLabel(),
      icon: 'square-chart-gantt',
      closable: true,
    };
    tabs.push(tab);
    makePlaceholderView(tab);
    setActiveTab(id);
  }

  function removeTab(id) {
    const index = tabs.findIndex(t => t.id === id);
    if (index === -1 || tabs[index].closable === false || tabs.length <= 1) return;

    const wasActive = activeTabId === id;
    tabs.splice(index, 1);

    const view = getView(id);
    if (view) view.remove();

    if (wasActive) {
      const fallback = tabs[Math.max(0, index - 1)] || tabs[0];
      activeTabId = fallback.id;
    }

    setActiveTab(activeTabId);
  }

  function initialize() {
    if (!getTabList() || !getContentRoot() || getTabList().dataset.bound === 'true') return;

    const stored = readState();
    tabs = stored?.tabs?.length ? stored.tabs : DEFAULT_TABS.map(t => ({ ...t }));
    activeTabId = tabs.some(t => t.id === stored?.activeTabId) ? stored.activeTabId : 'dashboard';

    tabs.forEach(tab => {
      if (tab.id !== 'dashboard') makePlaceholderView(tab);
    });

    getTabList().addEventListener('click', (event) => {
      const close = event.target.closest('[data-right-panel-tab-close]');
      if (close) {
        event.stopPropagation();
        removeTab(close.dataset.rightPanelTabClose);
        return;
      }

      const add = event.target.closest('[data-right-panel-tab-add]');
      if (add) {
        addTab();
        return;
      }

      const tab = event.target.closest('[data-right-panel-tab]');
      if (tab) setActiveTab(tab.dataset.rightPanelTab);
    });

    getTabList().dataset.bound = 'true';
    setActiveTab(activeTabId, false);
  }

  window.GaemiGTPRightPanelTabs = {
    initialize,
    addTab,
    removeTab,
    setActiveTab,
    getTabs: () => tabs.map(tab => ({ ...tab })),
    getActiveTab: () => activeTabId,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, { once: true });
  } else {
    initialize();
  }
})();
