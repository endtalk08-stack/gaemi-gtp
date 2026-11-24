/* The original sidebar industry map is the one portable DOM node. */
(function () {
  'use strict';

  let industryMap = null;

  function getIndustryMap() {
    if (!industryMap) industryMap = document.getElementById('marketIndustryMap');
    return industryMap;
  }

  function mount() {
    const map = getIndustryMap();
    if (!map) return;

    const widgetTarget = document.querySelector('[data-industry-widget-target]');
    const homeSlot = document.getElementById('marketIndustryWidgetSlot');

    if (widgetTarget) {
      if (map.parentElement !== widgetTarget) widgetTarget.appendChild(map);
    } else if (homeSlot && map.parentElement !== homeSlot) {
      // Removing the plugin returns the same map node to its original sidebar position.
      homeSlot.appendChild(map);
    }

    window.GaemiGTPMarketSidebar?.syncIndustryLayout?.();
  }

  window.GaemiGTPIndustryWidget = { mount };
  document.addEventListener('DOMContentLoaded', mount);
}());
