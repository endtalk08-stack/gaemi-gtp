/* Dashboard page shell.
   Dashboard widgets were intentionally removed without changing the panel shell. */
(function () {
  'use strict';

  const STORAGE_KEY = 'gaemi.dashboard.responsive-grid.v8.5';

  function mount() {
    const root = document.getElementById('rightPanelDashboard');
    if (!root || root.dataset.dashboardMounted === 'true') return;

    // Remove the saved arrangement from the retired widget workspace as well.
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (_) {}

    // A saved Marketaux news view is mounted by the panel-tab controller
    // before this legacy empty dashboard shell finishes initializing.
    if (!root.querySelector('#rightPanelNews')) {
      root.replaceChildren();
    }
    root.dataset.dashboardMounted = 'true';
  }

  window.GaemiGTPDashboard = {
    mount,
    openWidget: () => false,
    resetLayout: () => {},
    saveLayout: () => {},
    widgetSlots: [],
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount, { once: true });
  } else {
    mount();
  }
})();
