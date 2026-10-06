/* Left Navigation Rail — shell entry-point bindings only. */
(function () {
  'use strict';

  function initialize() {
    document.querySelectorAll('[data-left-sidebar-toggle]').forEach((el) => {
      if (el.dataset.sidebarListenerBound === 'true') return;
      el.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        window.toggleLeftSidebarHome?.();
      });
      el.dataset.sidebarListenerBound = 'true';
    });
  }

  window.GaemiGTPLeftNavRail = { initialize };
}());
