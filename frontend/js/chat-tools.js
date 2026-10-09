(() => {
  const menu = document.getElementById('bottomResourceMenu');
  const resourceButtons = [...document.querySelectorAll('[data-bottom-resource]')];
  const modeButton = document.getElementById('bottomModeBtn');

  if (!menu || !resourceButtons.length) return;

  const WATCHLIST_STORAGE_KEY = 'gaemiGTP_watchlist_v1';
  let activeResource = '';

  const escapeHtml = (value) => String(value || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

  const closeMenu = ({ restoreFocus = false } = {}) => {
    const trigger = resourceButtons.find((button) => button.dataset.bottomResource === activeResource);
    menu.hidden = true;
    menu.replaceChildren();
    resourceButtons.forEach((button) => button.setAttribute('aria-expanded', 'false'));
    activeResource = '';
    if (restoreFocus) trigger?.focus();
  };

  const readWatchlist = () => {
    try {
      const value = JSON.parse(localStorage.getItem(WATCHLIST_STORAGE_KEY) || '[]');
      return Array.isArray(value)
        ? value.map((item) => String(item || '').trim()).filter(Boolean)
        : [];
    } catch (_) {
      return [];
    }
  };

  const renderPluginMenu = () => {
    const catalog = window.GaemiGTPWidgetCatalog || {};
    const active = window.GaemiGTPWidgetDock?.getActiveIds?.() || [];
    const entries = Object.entries(catalog);
    if (!entries.length) {
      menu.innerHTML = '<div class="gaemi-chat-resource-menu__empty">사용 가능한 플러그인이 없습니다</div>';
      return;
    }

    menu.innerHTML = entries.map(([id, meta]) => {
      const used = active.includes(id);
      return `<button type="button" class="gaemi-chat-resource-menu__item" data-bottom-plugin="${escapeHtml(id)}" ${used ? 'disabled' : ''}>
        <span>${escapeHtml(meta.title)}</span>
        ${used ? '<small>사용 중</small>' : ''}
      </button>`;
    }).join('');
  };

  const renderWatchlistMenu = () => {
    const stocks = readWatchlist();
    menu.innerHTML = stocks.length
      ? stocks.map((name) => `<button type="button" class="gaemi-chat-resource-menu__item" data-bottom-watchlist-stock="${escapeHtml(name)}">${escapeHtml(name)}</button>`).join('')
      : '<div class="gaemi-chat-resource-menu__empty">관심종목이 없습니다</div>';
  };

  const renderProjectMenu = () => {
    menu.innerHTML = '<div class="gaemi-chat-resource-menu__empty">프로젝트가 없습니다</div>';
  };

  const renderMenu = (resource) => {
    if (resource === 'plugin') renderPluginMenu();
    else if (resource === 'watchlist') renderWatchlistMenu();
    else renderProjectMenu();
  };

  const openMenu = (resource) => {
    document.getElementById('bottomModeMenu')?.classList.add('hidden');
    activeResource = resource;
    renderMenu(resource);
    menu.hidden = false;
    resourceButtons.forEach((button) => {
      button.setAttribute('aria-expanded', String(button.dataset.bottomResource === resource));
    });
  };

  const toggleMenu = (resource) => {
    if (!menu.hidden && activeResource === resource) closeMenu();
    else openMenu(resource);
  };

  resourceButtons.forEach((button) => {
    button.addEventListener('click', (event) => {
      event.stopPropagation();
      toggleMenu(button.dataset.bottomResource || '');
    });
  });

  modeButton?.addEventListener('click', () => closeMenu());

  menu.addEventListener('click', (event) => {
    const pluginButton = event.target.closest('[data-bottom-plugin]');
    if (pluginButton) {
      const id = pluginButton.dataset.bottomPlugin;
      if (!pluginButton.disabled && id && window.GaemiGTPWidgetDock?.add) {
        window.GaemiGTPWidgetDock.add(id);
        window.GaemiGTPSidebarHome?.render?.();
      }
      closeMenu();
      return;
    }

    const stockButton = event.target.closest('[data-bottom-watchlist-stock]');
    if (stockButton) {
      const stockName = stockButton.dataset.bottomWatchlistStock;
      closeMenu();
      if (stockName) window.openStockInChat?.(stockName);
    }
  });

  document.addEventListener('click', (event) => {
    if (menu.hidden) return;
    if (menu.contains(event.target) || event.target.closest('[data-bottom-resource]')) return;
    closeMenu();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape' || menu.hidden) return;
    closeMenu({ restoreFocus: true });
  });

  window.GaemiGTPChatTools = {
    closeMenu,
    openMenu,
    toggleMenu
  };
})();