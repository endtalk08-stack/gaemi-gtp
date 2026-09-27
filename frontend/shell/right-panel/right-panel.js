/* Right Panel Shell Controller — user-resizable desktop panel. */
(function () {
  'use strict';

  const DEFAULT_PANEL_WIDTH_RATIO = 3 / 12;
  const MIN_PANEL_WIDTH = 240;
  const MIN_CHAT_WIDTH = 300;
  const STORAGE_KEY = 'gaemi-right-panel-width';

  function getWorkspace() { return document.getElementById('gaemiWorkspace'); }
  function isDesktop() { return window.innerWidth >= 1024; }
  function getWorkAreaWidth() {
    const navRail = document.getElementById('leftNavRail');
    const navWidth = navRail ? navRail.getBoundingClientRect().width : 0;
    return Math.max(0, window.innerWidth - navWidth);
  }
  function clampWidth(width) {
    const max = Math.max(MIN_PANEL_WIDTH, getWorkAreaWidth() - MIN_CHAT_WIDTH);
    return Math.max(MIN_PANEL_WIDTH, Math.min(Math.round(width), max));
  }
  function getDefaultPanelWidth() { return clampWidth(getWorkAreaWidth() * DEFAULT_PANEL_WIDTH_RATIO); }
  function getSavedPanelWidth() {
    const saved = Number(localStorage.getItem(STORAGE_KEY));
    return Number.isFinite(saved) && saved > 0 ? clampWidth(saved) : getDefaultPanelWidth();
  }
  function applyPanelWidth(width) {
    const workspace = getWorkspace(); if (!workspace) return;
    const rounded = clampWidth(width == null ? getSavedPanelWidth() : width);
    workspace.style.setProperty('--right-panel-width', `${rounded}px`);
    return rounded;
  }
  function setPanelWidth(width, persist) {
    const applied = applyPanelWidth(width);
    if (persist && applied) localStorage.setItem(STORAGE_KEY, String(applied));
    return applied;
  }
  function initializeWorkspaceInteractions() {
    const workspace = getWorkspace();
    const panel = document.getElementById('rightPanel');
    const resizer = document.getElementById('rightPanelResizer');
    if (!workspace || !panel || !resizer || panel.dataset.rightPanelBound === 'true') return;

    setPanelWidth();
    let dragging = false;

    const move = event => {
      if (!dragging || !isDesktop()) return;
      const workspaceRect = workspace.getBoundingClientRect();
      setPanelWidth(workspaceRect.right - event.clientX, false);
    };
    const stop = () => {
      if (!dragging) return;
      dragging = false;
      document.body.classList.remove('right-panel-resizing');
      const width = panel.getBoundingClientRect().width;
      setPanelWidth(width, true);
    };
    resizer.addEventListener('pointerdown', event => {
      if (!isDesktop() || document.body.classList.contains('right-panel-maximized')) return;
      dragging = true;
      document.body.classList.add('right-panel-resizing');
      resizer.setPointerCapture?.(event.pointerId);
      event.preventDefault();
    });
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', stop);
    window.addEventListener('pointercancel', stop);
    window.addEventListener('resize', () => {
      if (!dragging && !document.body.classList.contains('right-panel-maximized')) setPanelWidth();
    });
    panel.dataset.rightPanelBound = 'true';
  }

  window.GaemiGTPRightPanelShell = { getWorkspace, getWorkAreaWidth, setPanelWidth, initializeWorkspaceInteractions };
})();
