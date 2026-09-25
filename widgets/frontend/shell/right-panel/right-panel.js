/* Right Panel Shell Controller — v7.2
   책임: 패널 너비/리사이즈만 담당.
   책임 밖: 패널 열기/닫기 상태 전환, 데이터, 위젯 렌더링.
   전역 호환 API를 window에 제공해 기존 app.js/onclick이 계속 동작하도록 한다.
*/
(function () {
  'use strict';

  const PANEL_WIDTH_KEY = 'gaemiGTP_panel_width_v3';

  function getWorkspace() {
    return document.getElementById('gaemiWorkspace');
  }

  function setPanelWidth(px) {
    const workspace = getWorkspace();
    if (!workspace) return;
    const rect = workspace.getBoundingClientRect();
    const minMainWidth = window.innerWidth < 1024 ? 0 : 360;
    const maxWidth = Math.max(280, Math.min(1200, rect.width - minMainWidth - 5));
    const width = Math.max(280, Math.min(Number(px) || 360, maxWidth));
    const rounded = Math.round(width);
    workspace.style.setProperty('--right-panel-width', `${rounded}px`);
    localStorage.setItem(PANEL_WIDTH_KEY, String(rounded));
  }

  function getSavedPanelWidth(fallback = 360) {
    const value = parseInt(localStorage.getItem(PANEL_WIDTH_KEY) || String(fallback), 10);
    return Number.isFinite(value) ? value : fallback;
  }

  function initializeWorkspaceInteractions() {
    const workspace = getWorkspace();
    const resizer = document.getElementById('rightPanelResizer');
    const panel = document.getElementById('rightPanel');
    if (!workspace || !resizer || !panel || resizer.dataset.rightPanelBound === 'true') return;

    if (window.ResizeObserver) {
      const observer = new ResizeObserver(() => {
        if (document.body.classList.contains('right-panel-maximized')) return;
        const current = parseInt(getComputedStyle(workspace).getPropertyValue('--right-panel-width') || '360', 10);
        setPanelWidth(Number.isFinite(current) ? current : 360);
      });
      observer.observe(workspace);
      workspace.__rightPanelResizeObserver = observer;
    }

    resizer.addEventListener('pointerdown', (event) => {
      if (!document.body.classList.contains('right-panel-open') || document.body.classList.contains('right-panel-maximized')) return;
      event.preventDefault();
      const rect = workspace.getBoundingClientRect();

      const onMove = (moveEvent) => {
        // 패널은 항상 Workspace 오른쪽에 고정한다.
        setPanelWidth(rect.right - moveEvent.clientX);
      };

      const onUp = () => {
        window.removeEventListener('pointermove', onMove);
        window.removeEventListener('pointerup', onUp);
        document.body.classList.remove('panel-resizing');
      };

      document.body.classList.add('panel-resizing');
      window.addEventListener('pointermove', onMove);
      window.addEventListener('pointerup', onUp);
    });

    resizer.dataset.rightPanelBound = 'true';
  }

  window.GaemiGTPRightPanelShell = {
    PANEL_WIDTH_KEY,
    getWorkspace,
    setPanelWidth,
    getSavedPanelWidth,
    initializeWorkspaceInteractions,
  };
})();
