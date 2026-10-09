/* Analysis-screen resource shortcuts.
   Reuses existing plugin, watchlist and center-chat actions. */
(() => {
  'use strict';

  const menu = document.getElementById('analysisResourceMenu');
  const buttons = [...document.querySelectorAll('[data-analysis-resource]')];
  if (!menu || !buttons.length) return;

  const WATCHLIST_STORAGE_KEY = 'gaemiGTP_watchlist_v1';
  let activeResource = '';

  const escapeHtml = (value) => String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  const closeMenu = ({ restoreFocus = false } = {}) => {
    const trigger = buttons.find((button) => button.dataset.analysisResource === activeResource);
    menu.hidden = true;
    menu.replaceChildren();
    buttons.forEach((button) => button.setAttribute('aria-expanded', 'false'));
    activeResource = '';
    if (restoreFocus) trigger?.focus();
  };

  const readWatchlist = () => {
    try {
      const parsed = JSON.parse(localStorage.getItem(WATCHLIST_STORAGE_KEY) || '[]');
      return Array.isArray(parsed)
        ? parsed.map((name) => String(name || '').trim()).filter(Boolean)
        : [];
    } catch (_) {
      return [];
    }
  };

  const renderPlugins = () => {
    const catalog = window.GaemiGTPWidgetCatalog || {};
    const activeIds = window.GaemiGTPWidgetDock?.getActiveIds?.() || [];
    const entries = Object.entries(catalog);

    if (!entries.length) {
      menu.innerHTML = '<div class="analysis-resource-menu__empty">사용 가능한 플러그인이 없습니다</div>';
      return;
    }

    menu.innerHTML = entries.map(([id, meta]) => {
      const isActive = activeIds.includes(id);
      return `<button type="button" class="analysis-resource-menu__item" data-analysis-plugin="${escapeHtml(id)}" ${isActive ? 'disabled' : ''}>
        <span>${escapeHtml(meta?.title || id)}</span>
        ${isActive ? '<span class="analysis-resource-menu__meta">사용 중</span>' : ''}
      </button>`;
    }).join('');
  };

  const renderWatchlist = () => {
    const stocks = readWatchlist();
    menu.innerHTML = stocks.length
      ? stocks.map((name) => `<button type="button" class="analysis-resource-menu__item" data-analysis-watchlist-stock="${escapeHtml(name)}">${escapeHtml(name)}</button>`).join('')
      : '<div class="analysis-resource-menu__empty">관심종목이 없습니다</div>';
  };

  const renderProject = () => {
    menu.innerHTML = '<div class="analysis-resource-menu__empty">프로젝트가 없습니다</div>';
  };

  const renderMenu = (resource) => {
    if (resource === 'plugin') renderPlugins();
    else if (resource === 'watchlist') renderWatchlist();
    else renderProject();
  };

  const openMenu = (resource) => {
    activeResource = resource;
    renderMenu(resource);
    menu.hidden = false;
    buttons.forEach((button) => {
      button.setAttribute('aria-expanded', String(button.dataset.analysisResource === resource));
    });
  };

  const toggleMenu = (resource) => {
    if (!menu.hidden && activeResource === resource) closeMenu();
    else openMenu(resource);
  };

  buttons.forEach((button) => {
    button.addEventListener('click', (event) => {
      event.stopPropagation();
      toggleMenu(button.dataset.analysisResource || '');
    });
  });

  menu.addEventListener('click', (event) => {
    const pluginButton = event.target.closest('[data-analysis-plugin]');
    if (pluginButton) {
      const id = pluginButton.dataset.analysisPlugin;
      if (!pluginButton.disabled && id) {
        window.GaemiGTPWidgetDock?.add?.(id);
        window.GaemiGTPSidebarHome?.render?.();
      }
      closeMenu();
      return;
    }

    const stockButton = event.target.closest('[data-analysis-watchlist-stock]');
    if (stockButton) {
      const stockName = stockButton.dataset.analysisWatchlistStock;
      closeMenu();
      if (stockName) window.openStockInChat?.(stockName);
    }
  });

  document.addEventListener('click', (event) => {
    if (menu.hidden) return;
    if (menu.contains(event.target) || event.target.closest('[data-analysis-resource]')) return;
    closeMenu();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape' || menu.hidden) return;
    closeMenu({ restoreFocus: true });
  });
})();
