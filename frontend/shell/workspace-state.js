/* Workspace state — persisted shell layout state only. */
(function () {
  'use strict';

  const KEY = 'gaemiGTP_workspace_state_v1';
  let restoring = false;

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

  function setRestoring(value) {
    restoring = !!value;
  }

  window.GaemiGTPWorkspaceState = { read, save, setRestoring };
}());
