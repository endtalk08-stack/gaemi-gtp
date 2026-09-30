/* Legacy compatibility loader.
   Source of truth moved to pages/panel-workspace/panel-workspace.js. */
(function () {
  'use strict';

  function mountWorkspace() {
    const root = document.getElementById('rightPanelDashboard');
    if (!window.GaemiGTPPanelWorkspace) return;

    // Preserve the old global name temporarily so existing callers do not break.
    window.GaemiGTPDashboard = window.GaemiGTPPanelWorkspace;

    if (typeof window.GaemiGTPPanelWorkspace.mount === 'function') {
      window.GaemiGTPPanelWorkspace.mount(root);
    }
  }

  if (window.GaemiGTPPanelWorkspace) {
    mountWorkspace();
    return;
  }

  const script = document.createElement('script');
  script.src = 'pages/panel-workspace/panel-workspace.js?v=20261001-name-cleanup';
  script.onload = mountWorkspace;
  document.head.appendChild(script);
})();
