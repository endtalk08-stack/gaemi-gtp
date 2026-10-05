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

  window.GaemiGTPSidebarHome = { render, setActiveNav };

  document.addEventListener('DOMContentLoaded', () => {
    setActiveNav('home');
    render();
  });
}());
