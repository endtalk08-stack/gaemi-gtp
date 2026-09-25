/* Left Context Sidebar — shell toggle only. Content is mounted by pages/watchlist. */
(function () {
  'use strict';

  window.toggleLeftContextSidebar = function toggleLeftContextSidebar() {
    const body = document.body;
    const isOpen = body.classList.contains('left-context-open');

    if (typeof window.workspaceUIReady !== 'undefined' && !window.workspaceUIReady) return;

    if (!isOpen) {
      body.classList.remove('left-market-open', 'left-plugin-open');
      if (window.innerWidth < 1024) {
        body.classList.remove('right-panel-open', 'right-panel-maximized');
      }
      body.classList.add('left-context-open');
    } else {
      body.classList.remove('left-context-open');
    }

    if (typeof window.applySidebarState === 'function') window.applySidebarState();
  };

  window.closeLeftContextSidebar = function closeLeftContextSidebar() {
    document.body.classList.remove('left-context-open');
    if (typeof window.applySidebarState === 'function') window.applySidebarState();
  };
}());
