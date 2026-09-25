/* Right Panel Shell Controller — v8.3.1 hotfix
   - 왼쪽 사이드바는 건드리지 않는다.
   - desktop 기본 상태: 중앙 채팅 약 296px만 남기고 오른쪽 패널이 나머지를 사용.
   - 사용자가 경계선을 끌면 그 폭을 저장하고 그대로 복원.
*/
(function () {
  'use strict';

  const PANEL_WIDTH_KEY = 'gaemiGTP_panel_width_v3';
  const USER_PANEL_WIDTH_KEY = 'gaemiGTP_panel_width_v4';
  const DEFAULT_CHAT_WIDTH = 296;
  const MIN_CHAT_WIDTH = 240;
  const MIN_PANEL_WIDTH = 280;
  const RESIZER_WIDTH = 5;

  function getWorkspace() {
    return document.getElementById('gaemiWorkspace');
  }

  function isDesktop() {
    return window.innerWidth >= 1024;
  }

  function getMaxPanelWidth() {
    const workspace = getWorkspace();
    if (!workspace) return 1200;
    const width = workspace.getBoundingClientRect().width;
    return Math.max(MIN_PANEL_WIDTH, width - MIN_CHAT_WIDTH - RESIZER_WIDTH);
  }

  function getDefaultPanelWidth() {
    const workspace = getWorkspace();
    if (!workspace) return 900;
    const width = workspace.getBoundingClientRect().width;
    return Math.max(
      MIN_PANEL_WIDTH,
      width - DEFAULT_CHAT_WIDTH - RESIZER_WIDTH
    );
  }

  function applyPanelWidth(px, persistUser = false) {
    const workspace = getWorkspace();
    if (!workspace) return;

    const maxWidth = getMaxPanelWidth();
    const value = Number(px);
    const width = Math.max(
      MIN_PANEL_WIDTH,
      Math.min(Number.isFinite(value) ? value : getDefaultPanelWidth(), maxWidth)
    );
    const rounded = Math.round(width);

    workspace.style.setProperty('--right-panel-width', `${rounded}px`);
    localStorage.setItem(PANEL_WIDTH_KEY, String(rounded));

    if (persistUser) {
      localStorage.setItem(USER_PANEL_WIDTH_KEY, String(rounded));
    }

    return rounded;
  }

  function getSavedUserPanelWidth() {
    const value = parseInt(localStorage.getItem(USER_PANEL_WIDTH_KEY) || '', 10);
    return Number.isFinite(value) ? value : null;
  }

  /* app.js의 기존 호출과 호환.
     예전 360px 저장값 때문에 채팅이 다시 커지지 않도록
     실제 사용자 저장값(v4)이 있으면 그것을 우선하고,
     없으면 '채팅 296px' 기준으로 계산한다. */
  function setPanelWidth() {
    if (!isDesktop()) {
      const legacy = parseInt(localStorage.getItem(PANEL_WIDTH_KEY) || '360', 10);
      return applyPanelWidth(Number.isFinite(legacy) ? legacy : 360, false);
    }

    const saved = getSavedUserPanelWidth();
    return applyPanelWidth(saved ?? getDefaultPanelWidth(), false);
  }

  function getSavedPanelWidth() {
    const saved = getSavedUserPanelWidth();
    return saved ?? getDefaultPanelWidth();
  }

  function initializeWorkspaceInteractions() {
    const workspace = getWorkspace();
    const resizer = document.getElementById('rightPanelResizer');
    const panel = document.getElementById('rightPanel');

    if (!workspace || !resizer || !panel || resizer.dataset.rightPanelBound === 'true') {
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

    resizer.addEventListener('pointerdown', (event) => {
      if (!document.body.classList.contains('right-panel-open')) return;
      if (document.body.classList.contains('right-panel-maximized')) return;
      if (!isDesktop()) return;

      event.preventDefault();
      const rect = workspace.getBoundingClientRect();

      const onMove = (moveEvent) => {
        const panelWidth = rect.right - moveEvent.clientX;
        applyPanelWidth(panelWidth, false);
      };

      const onUp = () => {
        window.removeEventListener('pointermove', onMove);
        window.removeEventListener('pointerup', onUp);
        document.body.classList.remove('panel-resizing');

        const current = parseInt(
          getComputedStyle(workspace).getPropertyValue('--right-panel-width') || '',
          10
        );
        if (Number.isFinite(current)) {
          localStorage.setItem(USER_PANEL_WIDTH_KEY, String(current));
          localStorage.setItem(PANEL_WIDTH_KEY, String(current));
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
    getWorkspace,
    setPanelWidth,
    getSavedPanelWidth,
    initializeWorkspaceInteractions,
  };
})();
