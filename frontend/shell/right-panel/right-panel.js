/* Right Panel Shell Controller — v8.3
   desktop:
   - AI dock width controls the boundary.
   - default AI dock = 296px.
   - right panel automatically consumes all remaining workspace.
   mobile:
   - keeps legacy panel-width compatibility.
*/
(function () {
  'use strict';

  const PANEL_WIDTH_KEY = 'gaemiGTP_panel_width_v3';
  const AI_DOCK_WIDTH_KEY = 'gaemiGTP_ai_dock_width_v1';

  const DEFAULT_AI_DOCK = 296;
  const MIN_AI_DOCK = 240;
  const MAX_AI_DOCK = 520;
  const MIN_HTS = 560;
  const RESIZER_WIDTH = 5;

  function getWorkspace() {
    return document.getElementById('gaemiWorkspace');
  }

  function isDesktop() {
    return window.innerWidth >= 1024;
  }

  function getAIDockBounds() {
    const workspace = getWorkspace();
    const width = workspace ? workspace.getBoundingClientRect().width : window.innerWidth;
    const dynamicMax = Math.max(
      MIN_AI_DOCK,
      Math.min(MAX_AI_DOCK, width - MIN_HTS - RESIZER_WIDTH)
    );
    return { min: MIN_AI_DOCK, max: dynamicMax };
  }

  function setAIDockWidth(px, persist = true) {
    const workspace = getWorkspace();
    if (!workspace) return;

    const bounds = getAIDockBounds();
    const requested = Number(px);
    const width = Math.max(
      bounds.min,
      Math.min(Number.isFinite(requested) ? requested : DEFAULT_AI_DOCK, bounds.max)
    );
    const rounded = Math.round(width);

    workspace.style.setProperty('--ai-dock-width', `${rounded}px`);
    if (persist) localStorage.setItem(AI_DOCK_WIDTH_KEY, String(rounded));
  }

  function getSavedAIDockWidth(fallback = DEFAULT_AI_DOCK) {
    const value = parseInt(localStorage.getItem(AI_DOCK_WIDTH_KEY) || String(fallback), 10);
    return Number.isFinite(value) ? value : fallback;
  }

  /* 기존 app.js 호환 API.
     desktop에서는 실제 배치를 AI dock이 결정하므로 이 값은 레거시 상태 저장용이다. */
  function setPanelWidth(px) {
    const workspace = getWorkspace();
    if (!workspace) return;

    const rect = workspace.getBoundingClientRect();
    const minMainWidth = isDesktop() ? MIN_AI_DOCK : 0;
    const maxWidth = Math.max(280, rect.width - minMainWidth - RESIZER_WIDTH);
    const width = Math.max(280, Math.min(Number(px) || 360, maxWidth));
    const rounded = Math.round(width);

    workspace.style.setProperty('--right-panel-width', `${rounded}px`);
    localStorage.setItem(PANEL_WIDTH_KEY, String(rounded));

    /* 새 레이아웃에서 desktop panel width는 시각적 폭을 직접 제어하지 않는다. */
    if (!isDesktop()) return rounded;
    return rounded;
  }

  function getSavedPanelWidth(fallback = 360) {
    const value = parseInt(localStorage.getItem(PANEL_WIDTH_KEY) || String(fallback), 10);
    return Number.isFinite(value) ? value : fallback;
  }

  function initializeWorkspaceInteractions() {
    const workspace = getWorkspace();
    const resizer = document.getElementById('rightPanelResizer');
    const panel = document.getElementById('rightPanel');

    if (!workspace || !resizer || !panel || resizer.dataset.rightPanelBound === 'true') {
      return;
    }

    if (isDesktop()) {
      setAIDockWidth(getSavedAIDockWidth(DEFAULT_AI_DOCK), false);
    }

    if (window.ResizeObserver) {
      const observer = new ResizeObserver(() => {
        if (!isDesktop()) return;
        if (document.body.classList.contains('right-panel-maximized')) return;
        setAIDockWidth(getSavedAIDockWidth(DEFAULT_AI_DOCK), false);
      });
      observer.observe(workspace);
      workspace.__rightPanelResizeObserver = observer;
    }

    resizer.addEventListener('pointerdown', (event) => {
      if (!document.body.classList.contains('right-panel-open')) return;
      if (document.body.classList.contains('right-panel-maximized')) return;
      if (!isDesktop()) return;

      event.preventDefault();
      const rect = workspace.getBoundingClientRect();

      const onMove = (moveEvent) => {
        /* resizer 왼쪽 = AI dock 폭 */
        setAIDockWidth(moveEvent.clientX - rect.left, false);
      };

      const onUp = () => {
        window.removeEventListener('pointermove', onMove);
        window.removeEventListener('pointerup', onUp);
        document.body.classList.remove('panel-resizing');

        const current = parseInt(
          getComputedStyle(workspace).getPropertyValue('--ai-dock-width') || String(DEFAULT_AI_DOCK),
          10
        );
        if (Number.isFinite(current)) {
          localStorage.setItem(AI_DOCK_WIDTH_KEY, String(current));
        }
      };

      document.body.classList.add('panel-resizing');
      window.addEventListener('pointermove', onMove);
      window.addEventListener('pointerup', onUp);
    });

    resizer.dataset.rightPanelBound = 'true';
  }

  window.GaemiGTPRightPanelShell = {
    PANEL_WIDTH_KEY,
    AI_DOCK_WIDTH_KEY,
    getWorkspace,
    setPanelWidth,
    getSavedPanelWidth,
    setAIDockWidth,
    getSavedAIDockWidth,
    initializeWorkspaceInteractions,
  };
})();
