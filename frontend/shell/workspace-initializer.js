// gaemiGTP - workspace startup ownership
(function () {
  function initialize() {
    // Sidebar controls stay locked until the saved workspace has been restored.
    window.workspaceUIReady = false;
    const saved = window.GaemiGTPWorkspaceState?.read?.() || null;
    window.GaemiGTPWorkspaceState?.setRestoring?.(true);

    document.body.classList.remove('left-home-open','left-market-open','left-context-open','left-plugin-open','right-panel-open','right-panel-maximized','analysis-mode');
    document.getElementById('mainHeroView')?.classList.remove('hidden');
    document.getElementById('mainContent')?.classList.remove('is-news-view');
    document.getElementById('gaemiCenterNewsFeed')?.setAttribute('hidden', '');

    const state = window.GaemiGTPAppState;
    if (typeof saved?.stock === 'string' && saved.stock.trim()) state?.setActiveStock?.(saved.stock.trim());
    if (typeof saved?.appMode === 'string' && ['gaemi', 'info', 'pro'].includes(saved.appMode)) state?.setCurrentAppMode?.(saved.appMode);
    window.GaemiGTPCenterChatSearch?.selectAppMode?.(state?.getCurrentAppMode?.() || 'gaemi');

    // Restore the exact center surface without changing the saved sidebar layout.
    if (saved?.centerView === 'news') {
      window.GaemiCenterNews?.showNews?.();
      window.GaemiCenterNews?.restoreScroll?.(saved.newsScrollTop || 0);
    } else if (saved?.centerView === 'chat') {
      window.GaemiGTPCenterChatSearch?.enterChatWorkspace?.();
      window.GaemiGTPApp?.restoreLastConversation?.();
    }

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
        window.workspaceUIReady = true;
        window.GaemiGTPWorkspaceShellState?.save?.();
      });
    });

    window.GaemiGTPRightPanelShell?.initializeWorkspaceInteractions?.();
  }

  window.GaemiGTPWorkspaceInitializer = { initialize };
})();
