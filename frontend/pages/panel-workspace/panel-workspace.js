/* Panel Workspace page shell.
   This is the independent 12-grid workspace opened from the right-panel menu.
   It is not the right-panel shell itself and does not own news/disclosures/API/data. */
(function () {
  'use strict';

  const LEGACY_STORAGE_KEY = 'gaemi.dashboard.responsive-grid.v8.5';

  function mount(root) {
    const workspaceRoot = root || document.getElementById('rightPanelWorkspace');
    if (!workspaceRoot || workspaceRoot.dataset.panelWorkspaceMounted === 'true') return;

    try {
      localStorage.removeItem(LEGACY_STORAGE_KEY);
    } catch (_) {}

    workspaceRoot.dataset.panelWorkspaceMounted = 'true';
  }

  window.GaemiGTPPanelWorkspace = {
    mount,
    openWidget: () => false,
    resetLayout: () => {},
    saveLayout: () => {},
    widgetSlots: [],
  };
})();
