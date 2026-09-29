/* Right Panel Shell Controller — fixed three-column desktop panel. */
(function () {
  'use strict';

  const DEFAULT_PANEL_WIDTH_RATIO = 3 / 12;
  const MIN_PANEL_WIDTH = 240;
  const MIN_CHAT_WIDTH = 300;

  function getWorkspace() { return document.getElementById('gaemiWorkspace'); }
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
  function applyPanelWidth() {
    const workspace = getWorkspace(); if (!workspace) return;
    const rounded = getDefaultPanelWidth();
    workspace.style.setProperty('--right-panel-width', `${rounded}px`);
    return rounded;
  }
  function setPanelWidth() { return applyPanelWidth(); }
  function initializeWorkspaceInteractions() {
    const workspace = getWorkspace();
    const panel = document.getElementById('rightPanel');
    if (!workspace || !panel || panel.dataset.rightPanelBound === 'true') return;

    setPanelWidth();
    window.addEventListener('resize', () => {
      if (!document.body.classList.contains('right-panel-maximized')) setPanelWidth();
    });
    panel.dataset.rightPanelBound = 'true';
  }

  window.GaemiGTPRightPanelShell = { getWorkspace, getWorkAreaWidth, setPanelWidth, initializeWorkspaceInteractions };
})();
