/* Sidebar Home — left-home presentation only. */
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

  function setActive(section) {
    const next = section || 'home';
    document.querySelectorAll('#leftSidebarHome [data-sidebar-section]').forEach((button) => {
      const active = button.dataset.sidebarSection === next;
      button.classList.toggle('is-active', active);
      if (button.classList.contains('left-sidebar-home__menu-item')) {
        if (active) button.setAttribute('aria-current', 'page');
        else button.removeAttribute('aria-current');
      }
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
    const button = event.target.closest('#leftSidebarHome [data-sidebar-section]');
    if (!button) return;
    setActive(button.dataset.sidebarSection);
  });

  window.GaemiGTPSidebarHome = { render, setActive };
  document.addEventListener('DOMContentLoaded', () => {
    setActive('home');
    render();
  });
}());
