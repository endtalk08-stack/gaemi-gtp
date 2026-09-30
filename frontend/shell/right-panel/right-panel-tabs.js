/* Right Panel Tabs — workspace menu
   책임: 오른쪽 패널의 상단 탭/추가/삭제/선택 상태만 담당한다.
   패널 너비/채팅/사이드바는 건드리지 않는다.
*/
(function () {
  'use strict';

  const TABS_KEY = 'gaemiGTP_right_panel_tabs_v1';
  const DASHBOARD_VIEW_KEY = 'gaemiGTP_right_panel_dashboard_view_v1';
  const DEFAULT_TABS = [
    { id: 'dashboard', label: '대시보드', icon: 'layout-dashboard', closable: false },
    { id: 'auto-trade', label: '자동매매', icon: 'bot', closable: true },
  ];

  let tabs = [];
  let activeTabId = 'dashboard';
  let dashboardView = '';

  const DASHBOARD_VIEWS = {
    dashboard: { label: '대시보드', icon: 'layout-dashboard' },
    news: { label: '뉴스', icon: 'newspaper' },
    disclosures: { label: '공시', icon: 'file-text' },
  };

  function readState() {
    try {
      const raw = localStorage.getItem(TABS_KEY);
      if (!raw) return null;
      const state = JSON.parse(raw);
      if (!state || !Array.isArray(state.tabs)) return null;

      const cleanTabs = state.tabs
        .filter(t => t && typeof t.id === 'string' && typeof t.label === 'string' && !['chart', 'news', 'industry', 'disclosures'].includes(t.id))
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

  function saveDashboardView() {
    try { localStorage.setItem(DASHBOARD_VIEW_KEY, dashboardView); } catch (_) {}
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

  function escapeHtml(value) {
    return String(value)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
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

  function renderDashboardView() {
    const root = document.getElementById('rightPanelDashboard');
    if (!root) return;

    if (!dashboardView) {
      root.innerHTML = '';
      return;
    }

    if (dashboardView === 'dashboard') {
      root.innerHTML = '<section id="rightPanelGrid" aria-label="대시보드"></section>';
      return;
    }

    if (dashboardView === 'news') {
      root.innerHTML = '<section id="rightPanelNews" style="height:100%;min-height:0;" aria-label="뉴스"></section>';
      mountNewsPage();
      return;
    }

    if (dashboardView === 'disclosures') {
      root.innerHTML = '<section id="rightPanelDisclosures" style="height:100%;min-height:0;" aria-label="공시"></section>';
      mountDisclosuresPage();
    }
  }

  function renderTabs() {
    const list = getTabList();
    if (!list) return;

    list.innerHTML = '';

    tabs.forEach(tab => {
      if (tab.id === 'dashboard') {
        const dashboardWrap = document.createElement('div');
        dashboardWrap.className = 'right-panel-dashboard-menu-wrap';

        const dashboard = document.createElement('button');
        dashboard.type = 'button';
        dashboard.className = 'right-panel-tab-add';
        dashboard.dataset.dashboardMenuToggle = 'true';
        dashboard.setAttribute('aria-label', '패널 메뉴');
        dashboard.setAttribute('aria-expanded', 'false');
        dashboard.title = '패널 메뉴';
        dashboard.innerHTML = '<i data-lucide="ellipsis"></i>';
        dashboardWrap.appendChild(dashboard);

        const dashboardMenu = document.createElement('div');
        dashboardMenu.className = 'right-panel-tab-menu right-panel-dashboard-menu';
        dashboardMenu.dataset.dashboardMenu = 'true';
        dashboardMenu.hidden = true;
        dashboardMenu.innerHTML = `
          <button type="button" class="right-panel-tab-menu__item" data-dashboard-view="dashboard"><i data-lucide="layout-dashboard"></i><span>대시보드</span></button>
          <button type="button" class="right-panel-tab-menu__item" data-dashboard-view="news"><i data-lucide="newspaper"></i><span>뉴스</span></button>
          <button type="button" class="right-panel-tab-menu__item" data-dashboard-view="disclosures"><i data-lucide="file-text"></i><span>공시</span></button>
        `;
        dashboardWrap.appendChild(dashboardMenu);
        list.appendChild(dashboardWrap);
        return;
      }

      const button = document.createElement('button');
      button.type = 'button';
      button.className = `right-panel-tab${activeTabId === tab.id ? ' is-active' : ''}`;
      button.dataset.rightPanelTab = tab.id;
      button.setAttribute('role', 'tab');
      button.setAttribute('aria-selected', activeTabId === tab.id ? 'true' : 'false');
      button.title = tab.label;

      const label = document.createElement('span');
      label.className = 'right-panel-tab__label';
      label.textContent = tab.label;
      button.appendChild(label);

      if (tab.closable !== false) {
        const close = document.createElement('span');
        close.className = 'right-panel-tab__close';
        close.dataset.closeTabId = tab.id;
        close.setAttribute('role', 'button');
        close.tabIndex = 0;
        close.setAttribute('aria-label', `${tab.label} 탭 닫기`);
        close.title = `${tab.label} 탭 닫기`;
        close.innerHTML = '<i data-lucide="x"></i>';
        button.appendChild(close);
      }
      list.appendChild(button);
    });

    if (window.lucide) window.lucide.createIcons();
  }

  function toggleTabMenu() {}

  function toggleDashboardMenu(force) {
    const menu = document.querySelector('[data-dashboard-menu]');
    const toggle = document.querySelector('[data-dashboard-menu-toggle]');
    if (!menu || !toggle) return;
    const next = typeof force === 'boolean' ? force : menu.hidden;
    menu.hidden = !next;
    toggle.setAttribute('aria-expanded', String(next));
    if (next && window.lucide) window.lucide.createIcons();
  }

  function addNamedTab(type) {
    if (!['dashboard', 'auto-trade'].includes(type)) return;

    const existing = tabs.find(t => t.id === type);
    if (existing) {
      setActiveTab(existing.id);
      toggleDashboardMenu(false);
      return;
    }

    const labels = {
      dashboard: '대시보드',
      'auto-trade': '자동매매',
    };

    const icons = {
      dashboard: 'layout-dashboard',
      'auto-trade': 'bot',
    };

    const tab = {
      id: type,
      label: labels[type],
      icon: icons[type],
      closable: type !== 'dashboard',
    };

    tabs.push(tab);
    if (type !== 'dashboard') makePlaceholderView(tab);
    setActiveTab(type);
    toggleDashboardMenu(false);
  }

  function selectDashboardView(type) {
    if (!DASHBOARD_VIEWS[type]) return;
    dashboardView = type;
    setActiveTab('dashboard');
    saveDashboardView();
    toggleDashboardMenu(false);
  }

  function mountNewsPage() {
    const root = document.getElementById('rightPanelNews');
    if (root && window.GaemiGTPMarketauxNews && typeof window.GaemiGTPMarketauxNews.mount === 'function') {
      window.GaemiGTPMarketauxNews.mount(root);
    } else if (root) {
      window.addEventListener('load', () => {
        if (activeTabId === 'dashboard' && dashboardView === 'news' && window.GaemiGTPMarketauxNews && typeof window.GaemiGTPMarketauxNews.mount === 'function') {
          window.GaemiGTPMarketauxNews.mount(root);
        }
      }, { once: true });
    }
  }

  function mountDisclosuresPage() {
    const root = document.getElementById('rightPanelDisclosures');
    if (!root) return;
    if (window.GaemiGTPDisclosuresPage && typeof window.GaemiGTPDisclosuresPage.mount === 'function') {
      window.GaemiGTPDisclosuresPage.mount(root);
    }
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
    if (activeTabId === 'dashboard') renderDashboardView();
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
    dashboardView = '';
    saveDashboardView();

    tabs.forEach(tab => {
      if (tab.id !== 'dashboard' && tab.id !== 'auto-trade') makePlaceholderView(tab);
    });

    getTabList().addEventListener('click', (event) => {
      const dashboardToggle = event.target.closest('[data-dashboard-menu-toggle]');
      if (dashboardToggle) {
        event.stopPropagation();
        toggleDashboardMenu();
        return;
      }

      const dashboardViewButton = event.target.closest('[data-dashboard-view]');
      if (dashboardViewButton) {
        event.stopPropagation();
        selectDashboardView(dashboardViewButton.dataset.dashboardView);
        return;
      }

      const close = event.target.closest('[data-close-tab-id]');
      if (close) {
        event.stopPropagation();
        removeTab(close.dataset.closeTabId);
        return;
      }

      const tab = event.target.closest('[data-right-panel-tab]');
      if (tab) {
        toggleDashboardMenu(false);
        setActiveTab(tab.dataset.rightPanelTab);
      }
    });

    document.addEventListener('click', (event) => {
      if (!event.target.closest('#rightPanelTabs')) {
        toggleDashboardMenu(false);
      }
    });

    getTabList().dataset.bound = 'true';
    setActiveTab(activeTabId, false);
    saveState();
  }

  window.GaemiGTPRightPanelTabs = {
    initialize,
    addTab,
    addNamedTab,
    selectDashboardView,
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
