/* Left Sidebar Shell Controller — STEP 2
   One shared width is used by the market, context, and plugin sidebars.
   The right-panel controller remains the owner of the right panel width. */
(function () {
  'use strict';

  const LEFT_WIDTH_KEY = 'gaemiGTP_left_sidebar_width_v1';
  const DEFAULT_LEFT_WIDTH = 320;
  const MIN_LEFT_WIDTH = 240;
  const MAX_LEFT_WIDTH = 520;
  const MIN_CHAT_WIDTH = 240;
  const RESIZER_WIDTH = 5;

  function isDesktop() {
    return window.innerWidth >= 1024;
  }

  function isLeftPanelOpen() {
    const body = document.body;
    return body.classList.contains('left-market-open') ||
      body.classList.contains('left-context-open') ||
      body.classList.contains('left-plugin-open');
  }

  function getRightReservedWidth() {
    const body = document.body;
    if (!body.classList.contains('right-panel-open') ||
        body.classList.contains('right-panel-maximized')) {
      return 0;
    }

    const panel = document.getElementById('rightPanel');
    const resizer = document.getElementById('rightPanelResizer');
    return (panel ? panel.getBoundingClientRect().width : 0) +
      (resizer ? resizer.getBoundingClientRect().width : RESIZER_WIDTH);
  }

  function getSafeMaxLeftWidth() {
    const navRail = document.getElementById('leftNavRail');
    const navWidth = navRail ? navRail.getBoundingClientRect().width : 0;
    const available = window.innerWidth - navWidth - getRightReservedWidth() -
      RESIZER_WIDTH - MIN_CHAT_WIDTH;
    return Math.max(0, Math.min(MAX_LEFT_WIDTH, Math.floor(available)));
  }

  function getRequestedLeftWidth(px) {
    const value = Number(px);
    return Math.max(
      MIN_LEFT_WIDTH,
      Math.min(Number.isFinite(value) ? value : DEFAULT_LEFT_WIDTH, MAX_LEFT_WIDTH)
    );
  }

  function applyLeftWidth(px, persist = false) {
    if (!isDesktop()) return null;

    const requested = getRequestedLeftWidth(px);
    /* On a narrow desktop, only the rendered width is reduced.  The saved
       preference remains intact and is restored when space becomes available. */
    const rounded = Math.round(Math.min(requested, getSafeMaxLeftWidth()));

    document.documentElement.style.setProperty('--left-sidebar-width', `${rounded}px`);
    if (persist) localStorage.setItem(LEFT_WIDTH_KEY, String(Math.round(requested)));
    return rounded;
  }

  function restoreLeftWidth() {
    const saved = parseInt(localStorage.getItem(LEFT_WIDTH_KEY) || '', 10);
    return applyLeftWidth(Number.isFinite(saved) ? saved : DEFAULT_LEFT_WIDTH, false);
  }

  function initializeLeftPanelResizer() {
    const resizer = document.getElementById('leftPanelResizer');
    if (!resizer || resizer.dataset.leftPanelBound === 'true') return;

    restoreLeftWidth();

    resizer.addEventListener('pointerdown', (event) => {
      if (!isDesktop() || !isLeftPanelOpen()) return;
      if (document.body.classList.contains('right-panel-maximized')) return;

      event.preventDefault();
      const navRail = document.getElementById('leftNavRail');
      const leftEdge = navRail ? navRail.getBoundingClientRect().right : 0;
      let lastRequestedWidth = getRequestedLeftWidth(event.clientX - leftEdge);

      const onMove = (moveEvent) => {
        lastRequestedWidth = getRequestedLeftWidth(moveEvent.clientX - leftEdge);
        applyLeftWidth(lastRequestedWidth, false);
      };

      const onUp = () => {
        window.removeEventListener('pointermove', onMove);
        window.removeEventListener('pointerup', onUp);
        document.body.classList.remove('left-panel-resizing');

        localStorage.setItem(LEFT_WIDTH_KEY, String(Math.round(lastRequestedWidth)));
      };

      document.body.classList.add('left-panel-resizing');
      window.addEventListener('pointermove', onMove);
      window.addEventListener('pointerup', onUp);
    });

    window.addEventListener('resize', restoreLeftWidth);
    if (window.ResizeObserver) {
      const viewportObserver = new ResizeObserver(restoreLeftWidth);
      viewportObserver.observe(document.documentElement);
      resizer.__leftPanelViewportObserver = viewportObserver;
    }
    resizer.dataset.leftPanelBound = 'true';
  }

  window.GaemiGTPLeftPanelShell = {
    LEFT_WIDTH_KEY,
    applyLeftWidth,
    restoreLeftWidth,
    initializeLeftPanelResizer,
  };

  document.addEventListener('DOMContentLoaded', initializeLeftPanelResizer);
}());
