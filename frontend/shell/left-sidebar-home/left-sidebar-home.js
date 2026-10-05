/* Sidebar Home — projects are intentionally title-only until their data model is defined. */
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

  function render() {
    const list = document.getElementById('leftSidebarHomePluginList');
    if (!list) return;
    const catalog = window.GaemiGTPWidgetCatalog || {};
    const active = window.GaemiGTPWidgetDock?.getActiveIds?.() || [];
    list.innerHTML = active
      .filter((id) => catalog[id])
      .map((id) => `<li class="left-sidebar-home__item">${escapeHtml(catalog[id].title)}</li>`)
      .join('');
  }

  window.GaemiGTPSidebarHome = { render };
  document.addEventListener('DOMContentLoaded', render);
}());
