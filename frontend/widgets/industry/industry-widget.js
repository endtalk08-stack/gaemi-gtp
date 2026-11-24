/* Shares the original sidebar renderer, data, selection and socket. */
(function () {
  'use strict';
  let target = null;
  function mount() {
    const next = document.querySelector('[data-industry-widget-target="center"]');
    if (target && target !== next) window.GaemiGTPMarketSidebar?.unmountIndustryView?.(target);
    target = next;
    if (target) window.GaemiGTPMarketSidebar?.mountIndustryView?.(target);
  }
  window.GaemiGTPIndustryWidget = { mount };
  document.addEventListener('DOMContentLoaded', mount);
}());
