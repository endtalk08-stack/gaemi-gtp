/* Workspace state — persisted shell layout state only. */
(function () {
  'use strict';

  const KEY = 'gaemiGTP_workspace_state_v1';
  let restoring = false;
  let stateNewsScrollTop = 0;

  function read() {
    try {
      const raw = localStorage.getItem(KEY);
      if (!raw) return null;
      const state = JSON.parse(raw);
      return state && typeof state === 'object' ? state : null;
    } catch (e) {
      console.warn('[gaemiGTP] workspace state read warning:', e);
      return null;
    }
  }

  function save({ activeStock, currentAppMode } = {}) {
    if (restoring) return;
    try {
      const heroView = document.getElementById('mainHeroView');
      const panelOpen = document.body.classList.contains('right-panel-open');
      const state = {
        mode: document.body.classList.contains('analysis-mode') && heroView && heroView.classList.contains('hidden') ? 'analysis' : 'home',
        centerView: document.getElementById('mainContent')?.classList.contains('is-news-view') ? 'news' : (document.body.classList.contains('analysis-mode') && heroView?.classList.contains('hidden') ? 'chat' : 'home'),
        newsScrollTop: Number.isFinite(Number(stateNewsScrollTop)) ? Math.max(0, Number(stateNewsScrollTop)) : 0,
        stock: activeStock || '삼성전자',
        leftHomeOpen: document.body.classList.contains('left-home-open'),
        leftMarketOpen: document.body.classList.contains('left-market-open'),
        leftContextOpen: document.body.classList.contains('left-context-open'),
        leftPluginOpen: document.body.classList.contains('left-plugin-open'),
        rightPanelOpen: panelOpen,
        rightPanelMaximized: panelOpen && document.body.classList.contains('right-panel-maximized'),
        appMode: currentAppMode || 'gaemi'
      };
      localStorage.setItem(KEY, JSON.stringify(state));
    } catch (e) {
      console.warn('[gaemiGTP] workspace state save warning:', e);
    }
  }

  function setNewsScrollTop(value) {
    stateNewsScrollTop = Math.max(0, Number(value) || 0);
    if (restoring) return;
    const current = read() || {};
    current.newsScrollTop = stateNewsScrollTop;
    try { localStorage.setItem(KEY, JSON.stringify(current)); } catch (e) { /* storage unavailable */ }
  }

  function setRestoring(value) {
    restoring = !!value;
  }

  window.GaemiGTPWorkspaceState = { read, save, setRestoring, setNewsScrollTop };
}());
