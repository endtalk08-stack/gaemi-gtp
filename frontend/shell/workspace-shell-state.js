/* Workspace shell state — synchronize left shells, right panel, and shared controls. */
(function () {
  'use strict';

  function apply() {
    const market = document.getElementById('leftMarketSidebar');
    const home = document.getElementById('leftSidebarHome');
    const context = document.getElementById('leftContextSidebar');
    const plugin = document.getElementById('leftPluginSidebar');
    const panel = document.getElementById('rightPanel');
    const resizer = document.getElementById('rightPanelResizer');
    const backdrop = document.getElementById('sidebarBackdrop');

    const marketOpen = document.body.classList.contains('left-market-open');
    const homeOpen = document.body.classList.contains('left-home-open');
    const contextOpen = document.body.classList.contains('left-context-open');
    const pluginOpen = document.body.classList.contains('left-plugin-open');
    const panelOpen = document.body.classList.contains('right-panel-open');
    const panelMaximized = document.body.classList.contains('right-panel-maximized');
    const mobile = window.innerWidth < 1024;
    const heroView = document.getElementById('mainHeroView');
    const onHero = !!heroView && !heroView.classList.contains('hidden');

    document.body.classList.toggle('left-home-closed', !homeOpen);
    document.body.classList.toggle('left-market-closed', !marketOpen);
    document.body.classList.toggle('left-context-closed', !contextOpen);
    document.body.classList.toggle('left-plugin-closed', !pluginOpen);
    document.body.classList.toggle('right-panel-closed', !panelOpen);

    if (home) home.setAttribute('aria-hidden', homeOpen ? 'false' : 'true');
    if (market) market.setAttribute('aria-hidden', marketOpen ? 'false' : 'true');
    if (context) context.setAttribute('aria-hidden', contextOpen ? 'false' : 'true');
    if (plugin) plugin.setAttribute('aria-hidden', pluginOpen ? 'false' : 'true');
    if (panel) panel.setAttribute('aria-hidden', panelOpen ? 'false' : 'true');

    document.querySelectorAll('[data-panel-maximize-icon="maximize"]').forEach(el => el.classList.toggle('hidden', panelMaximized));
    document.querySelectorAll('[data-panel-maximize-icon="restore"]').forEach(el => el.classList.toggle('hidden', !panelMaximized));

    if (resizer) {
      resizer.classList.toggle('is-open', panelOpen);
      resizer.classList.toggle('hidden', !panelOpen);
      resizer.style.display = panelOpen ? '' : 'none';
    }
    if (panel) {
      panel.classList.toggle('hidden', !panelOpen);
      panel.style.display = panelOpen ? '' : 'none';
    }

    document.querySelectorAll('[data-panel-toggle-icon="closed"]').forEach(el => el.classList.toggle('hidden', panelOpen));
    document.querySelectorAll('[data-panel-toggle-icon="open"]').forEach(el => el.classList.toggle('hidden', !panelOpen));

    document.querySelectorAll('[data-left-sidebar-toggle]').forEach(el => {
      const shouldShow = el.getAttribute('data-left-sidebar-top') === 'hero' ? onHero : !onHero;
      el.classList.toggle('hidden', !shouldShow);
      el.setAttribute('aria-hidden', shouldShow ? 'false' : 'true');
      el.tabIndex = shouldShow ? 0 : -1;
    });

    document.querySelectorAll('[data-panel-header-toggle]').forEach(el => {
      el.setAttribute('aria-label', panelOpen ? '패널 닫기' : '패널 열기');
      el.setAttribute('title', panelOpen ? '패널 닫기' : '패널 열기');
      const shouldShow = el.getAttribute('data-panel-top') === 'hero' ? onHero : !onHero;
      el.classList.toggle('hidden', !shouldShow);
      el.setAttribute('aria-hidden', shouldShow ? 'false' : 'true');
      el.tabIndex = shouldShow ? 0 : -1;
    });

    if (backdrop) backdrop.classList.toggle('hidden', !(mobile && (homeOpen || marketOpen || contextOpen || pluginOpen)));
    if (homeOpen) window.GaemiGTPSidebarHome?.render?.();
    if (window.lucide) window.lucide.createIcons();
  }

  window.GaemiGTPWorkspaceShellState = { apply };
}());
