/* Auto Trade Page Container — v7.6
   책임: 자동매매 탭의 화면 컨테이너만 담당한다.
   책임 밖: 실매매/주문/API/DB/전략 계산.
*/
(function () {
  'use strict';

  function mount(root) {
    if (!root || root.dataset.autoTradeMounted === 'true') return;

    root.innerHTML = `
      <div class="auto-trade-page right-panel-tab-placeholder">
        <div class="right-panel-tab-placeholder__icon"><i data-lucide="bot"></i></div>
        <div class="right-panel-tab-placeholder__title">자동매매</div>
        <div class="right-panel-tab-placeholder__text">자동매매 화면은 대시보드와 분리된 독립 영역으로 구성합니다.</div>
      </div>
    `;

    root.dataset.autoTradeMounted = 'true';
    if (window.lucide) window.lucide.createIcons();
  }

  window.GaemiGTPAutoTrade = { mount };
})();
