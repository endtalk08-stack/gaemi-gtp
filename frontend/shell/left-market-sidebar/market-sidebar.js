/* Left Market Sidebar — market shell open/close controls only. */
(function () {
  'use strict';

  function applyState() {
    window.GaemiGTPWorkspaceShellState?.apply?.();
  }

  function toggle() {
    if (typeof window.workspaceUIReady !== 'undefined' && !window.workspaceUIReady) return;

    const isOpen = document.body.classList.contains('left-market-open');
    if (!isOpen) {
      document.body.classList.remove('left-home-open', 'left-context-open', 'left-plugin-open');
      if (window.innerWidth < 1024) {
        document.body.classList.remove('right-panel-open', 'right-panel-maximized');
      }
    }

    document.body.classList.toggle('left-market-open', !isOpen);
    applyState();
  }

  window.toggleLeftSidebar = toggle;
  window.GaemiGTPMarketSidebar = { toggle };
}());
