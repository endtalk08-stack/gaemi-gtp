/* Sidebar Home — visual navigation/layout only.
   The primary menu deliberately does not open market/watchlist/plugin views yet. */
(function () {
  'use strict';

  function escapeHtml(value) {
    return String(value)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function setActiveNav(id) {
    const target = id || 'home';
    document.querySelectorAll('#leftSidebarHome [data-left-home-nav]').forEach((button) => {
      const active = button.dataset.leftHomeNav === target;
      button.classList.toggle('is-active', active);
      if (active) button.setAttribute('aria-current', 'page');
      else button.removeAttribute('aria-current');
    });
  }

  function applyState() {
    if (typeof window.applySidebarState === 'function') window.applySidebarState();
  }

  function close() {
    document.body.classList.remove('left-home-open');
    applyState();
  }

  function toggleMenu() {
    const menu = document.getElementById('leftSidebarHomeMenu');
    const button = document.querySelector('[data-left-sidebar-home-menu-toggle]');
    if (!menu || !button) return;
    const open = menu.classList.toggle('hidden') === false;
    button.setAttribute('aria-expanded', String(open));
  }

  const sectionOrigins = new Map();

  function showSection(section = 'home') {
    if (typeof window.workspaceUIReady !== 'undefined' && !window.workspaceUIReady) return;
    const homeDefault = document.getElementById('leftSidebarHomeDefault');
    const host = document.getElementById('leftSidebarHomeSectionContent');
    if (!homeDefault || !host) return;

    sectionOrigins.forEach((origin, node) => {
      if (node.parentNode === host) {
        node.style.removeProperty('width');
        node.style.removeProperty('flex-basis');
        origin.parent.insertBefore(node, origin.nextSibling);
      }
    });
    sectionOrigins.clear();
    host.replaceChildren();
    host.classList.add('hidden');
    homeDefault.classList.remove('hidden');

    if (section !== 'home') {
      const idBySection = {
        market: 'leftMarketSidebar',
        context: 'leftContextSidebar',
        plugin: 'leftPluginSidebar'
      };
      const node = document.getElementById(idBySection[section]);
      if (!node || !node.parentNode) return;
      sectionOrigins.set(node, { parent: node.parentNode, nextSibling: node.nextSibling });
      host.appendChild(node);
      homeDefault.classList.add('hidden');
      host.classList.remove('hidden');
    }

    document.body.classList.add('left-home-open');
    document.body.classList.remove('left-market-open', 'left-context-open', 'left-plugin-open');
    document.getElementById('leftSidebarHomeMenu')?.classList.add('hidden');
    document.querySelector('[data-left-sidebar-home-menu-toggle]')?.setAttribute('aria-expanded', 'false');

    const embedded = host.firstElementChild;
    if (embedded) {
      embedded.removeAttribute('aria-hidden');
      embedded.style.width = '100%';
      embedded.style.flexBasis = '100%';
    }
    if (section === 'plugin') window.GaemiGTPPluginSidebar?.render?.();
    applyState();
  }

  function render() {
    const list = document.getElementById('leftSidebarHomePluginList');
    const empty = document.getElementById('leftSidebarHomePluginEmpty');
    if (!list) return;

    const catalog = window.GaemiGTPWidgetCatalog || {};
    const active = window.GaemiGTPWidgetDock?.getActiveIds?.() || [];
    const visible = active.filter((id) => catalog[id]);

    list.innerHTML = visible
      .map((id) => `<li class="left-sidebar-home__item">${escapeHtml(catalog[id].title)}</li>`)
      .join('');

    if (empty) empty.hidden = visible.length > 0;
    if (window.lucide) window.lucide.createIcons();
  }

  document.addEventListener('click', (event) => {
    const navButton = event.target.closest('#leftSidebarHome [data-left-home-nav]');
    if (navButton) {
      setActiveNav(navButton.dataset.leftHomeNav);
      return;
    }

    const sectionMenu = event.target.closest('#leftSidebarHome [data-left-home-section-menu]');
    if (sectionMenu) {
      /* Layout placeholder only. Management actions will be connected later. */
      return;
    }
  });

  window.GaemiGTPSidebarHome = { render, setActiveNav, close, toggleMenu, showSection };
  window.closeLeftSidebarHome = close;
  window.toggleLeftSidebarHomeMenu = toggleMenu;
  window.showLeftSidebarHomeSection = showSection;
  window.openLeftSidebarSection = showSection;

  document.addEventListener('DOMContentLoaded', () => {
    setActiveNav('home');
    render();
  });
}());
