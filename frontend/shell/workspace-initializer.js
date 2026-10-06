// gaemiGTP - workspace startup ownership
(function () {
  function initialize() {
    // 새 접속은 항상 검색 홈에서 시작하고, 저장된 shell 레이아웃만 복원한다.
    const saved = window.GaemiGTPWorkspaceState?.read?.() || null;
    window.GaemiGTPWorkspaceState?.setRestoring?.(true);

    document.body.classList.remove('left-home-open','left-market-open','left-context-open','left-plugin-open','right-panel-open','right-panel-maximized','analysis-mode');
    document.getElementById('mainHeroView')?.classList.remove('hidden');

    const state = window.GaemiGTPAppState;
    if (typeof saved?.stock === 'string' && saved.stock.trim()) state?.setActiveStock?.(saved.stock.trim());
    if (typeof saved?.appMode === 'string' && ['gaemi', 'info', 'pro'].includes(saved.appMode)) state?.setCurrentAppMode?.(saved.appMode);
    window.GaemiGTPCenterChatSearch?.selectAppMode?.(state?.getCurrentAppMode?.() || 'gaemi');

    window.workspaceUIReady = true;

    const restoreWorkspace = () => {
      document.body.classList.toggle('right-panel-open', !!saved?.rightPanelOpen);
      document.body.classList.toggle('right-panel-maximized', !!(saved?.rightPanelOpen && saved?.rightPanelMaximized));
      document.body.classList.toggle('left-home-open', !!saved?.leftHomeOpen);
      document.body.classList.toggle('left-market-open', !!saved?.leftMarketOpen);
      document.body.classList.toggle('left-context-open', !!saved?.leftContextOpen);
      document.body.classList.toggle('left-plugin-open', !!saved?.leftPluginOpen);

      if (saved?.leftContextOpen || saved?.leftPluginOpen) document.body.classList.remove('left-market-open');
      if (saved?.leftContextOpen) document.body.classList.remove('left-plugin-open');
      if (saved?.leftPluginOpen) document.body.classList.remove('left-context-open');

      if (!document.body.classList.contains('right-panel-maximized')) window.GaemiGTPRightPanelShell?.setPanelWidth?.();
      window.GaemiGTPWorkspaceShellState?.apply?.();
    };

    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        restoreWorkspace();
        window.GaemiGTPWorkspaceState?.setRestoring?.(false);
        window.GaemiGTPWorkspaceShellState?.save?.();
      });
    });

    window.GaemiGTPRightPanelShell?.initializeWorkspaceInteractions?.();
  }

  window.GaemiGTPWorkspaceInitializer = { initialize };
})();
