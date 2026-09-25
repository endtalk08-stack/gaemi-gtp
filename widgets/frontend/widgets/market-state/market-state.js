/* Market State Widget — v7.4
   독립 위젯 모듈.
   현재는 화면 구조만 담당하며 데이터/API/DB/분석 로직은 연결하지 않는다.
*/
(function () {
  'use strict';

  const WIDGET_KEY = 'market-state';
  const WIDGET_META = {
    id: WIDGET_KEY,
    title: '시장 상태',
    icon: 'activity',
    description: '시장 상태 위젯 영역',
  };

  function render(root) {
    if (!root) return;

    root.innerHTML = `
      <div class="market-state-widget">
        <p class="market-state-widget__description">${WIDGET_META.description}</p>
      </div>
    `;
  }

  function mount(root) {
    if (!root || root.dataset.marketStateMounted === 'true') return;
    render(root);
    root.dataset.marketStateMounted = 'true';
  }

  window.GaemiGTPWidgets = window.GaemiGTPWidgets || {};
  window.GaemiGTPWidgets[WIDGET_KEY] = {
    ...WIDGET_META,
    mount,
    render,
  };
})();
