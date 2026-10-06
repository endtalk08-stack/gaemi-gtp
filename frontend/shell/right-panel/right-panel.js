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
  function applyState() { window.GaemiGTPWorkspaceShellState?.apply?.(); }

  function toggle() {
    const isOpen = document.body.classList.contains('right-panel-open');
    if (isOpen) {
      document.body.classList.remove('right-panel-open', 'right-panel-maximized');
    } else {
      if (window.innerWidth < 1024) {
        document.body.classList.remove('left-home-open', 'left-market-open', 'left-context-open', 'left-plugin-open');
      }
      document.body.classList.add('right-panel-open');
    }
    applyState();
  }

  function toggleMaximize() {
    if (!document.body.classList.contains('right-panel-open')) {
      if (window.innerWidth < 1024) {
        document.body.classList.remove('left-home-open', 'left-market-open', 'left-context-open', 'left-plugin-open');
      }
      document.body.classList.add('right-panel-open');
    }
    const maximized = document.body.classList.toggle('right-panel-maximized');
    const button = document.querySelector('[data-panel-maximize]');
    if (button) {
      button.setAttribute('aria-label', maximized ? '패널 원래 크기로' : '패널 최대화');
      button.setAttribute('title', maximized ? '패널 원래 크기로' : '패널 최대화');
    }
    if (!maximized) requestAnimationFrame(() => setPanelWidth());
    applyState();
  }

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

  window.GaemiGTPRightPanelShell = { getWorkspace, getWorkAreaWidth, setPanelWidth, toggle, toggleMaximize, initializeWorkspaceInteractions };
  window.toggleRightPanel = toggle;
  window.toggleRightPanelMaximize = toggleMaximize;
})();
