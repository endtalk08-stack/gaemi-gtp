/* Right Panel Shell Controller — fixed work-area-3-12
   - 왼쪽 사이드바는 건드리지 않는다.
   - desktop 폭은 항상 전체 작업영역의 3/12.
   - 폭 저장과 경계선 드래그는 사용하지 않는다.
*/
(function () {
  'use strict';

  const DEFAULT_PANEL_WIDTH_RATIO = 3 / 12;
  const MIN_CHAT_WIDTH = 240;

  function getWorkspace() {
    return document.getElementById('gaemiWorkspace');
  }

  function isDesktop() {
    return window.innerWidth >= 1024;
  }

  function getWorkAreaWidth() {
    const navRail = document.getElementById('leftNavRail');
    const navWidth = navRail ? navRail.getBoundingClientRect().width : 0;
    return Math.max(0, window.innerWidth - navWidth);
  }

  function getDefaultPanelWidth() {
    if (!isDesktop()) return 360;
    const workAreaWidth = getWorkAreaWidth();
    const maxWidth = Math.max(0, workAreaWidth - MIN_CHAT_WIDTH);
    return Math.round(Math.min(workAreaWidth * DEFAULT_PANEL_WIDTH_RATIO, maxWidth));
  }

  function applyPanelWidth() {
    const workspace = getWorkspace();
    if (!workspace) return;

    const rounded = getDefaultPanelWidth();

    workspace.style.setProperty('--right-panel-width', `${rounded}px`);
    return rounded;
  }

  function setPanelWidth() {
    return applyPanelWidth();
  }

  function initializeWorkspaceInteractions() {
    const workspace = getWorkspace();
    const panel = document.getElementById('rightPanel');

    if (!workspace || !panel || panel.dataset.rightPanelBound === 'true') {
      return;
    }

    setPanelWidth();

    if (window.ResizeObserver) {
      const observer = new ResizeObserver(() => {
        if (document.body.classList.contains('right-panel-maximized')) return;
        setPanelWidth();
      });
      observer.observe(workspace);
      workspace.__rightPanelResizeObserver = observer;
    }

    panel.dataset.rightPanelBound = 'true';
  }

  window.GaemiGTPRightPanelShell = {
    getWorkspace,
    getWorkAreaWidth,
    setPanelWidth,
    initializeWorkspaceInteractions,
  };
})();
