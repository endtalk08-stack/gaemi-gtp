/* Watchlist Page Container — v7.11
   책임: 왼쪽 '내 종목' 컨텍스트 영역 안의 관심종목/최근 본 종목 화면만 담당한다.
   책임 밖: 저장/DB/API/종목 검색 결과/실시간 데이터.
*/
(function () {
  'use strict';

  function mount(root) {
    if (!root || root.dataset.watchlistMounted === 'true') return;

    root.innerHTML = `
      <section class="context-sidebar-section" aria-label="관심종목">
        <div class="context-sidebar-section-head">
          <div class="context-sidebar-section-title">관심종목</div>
          <button type="button" class="context-sidebar-section-action" onclick="focusStockInput()" title="종목 검색으로 추가">+ 추가</button>
        </div>
        <div class="context-sidebar-empty">
          <div class="context-sidebar-empty-icon"><i data-lucide="star" class="w-5 h-5"></i></div>
          <div class="context-sidebar-empty-title">관심종목을 추가하세요</div>
          <div class="context-sidebar-empty-copy">나중에 종목을 등록하면 이곳에 모아볼 수 있습니다.</div>
        </div>
      </section>

      <div class="context-sidebar-divider"></div>

      <section class="context-sidebar-section" aria-label="최근 본 종목">
        <div class="context-sidebar-section-head">
          <div class="context-sidebar-section-title">최근 본 종목</div>
          <button type="button" class="context-sidebar-section-action" disabled>전체삭제</button>
        </div>
        <div class="context-sidebar-empty">
          <div class="context-sidebar-empty-icon"><i data-lucide="history" class="w-5 h-5"></i></div>
          <div class="context-sidebar-empty-title">최근 본 종목이 없습니다</div>
          <div class="context-sidebar-empty-copy">종목을 확인하면 최근 기록이 이곳에 표시됩니다.</div>
        </div>
      </section>

      <div class="context-sidebar-note">현재는 화면 구조만 준비되어 있습니다. 저장/DB 연결은 구조가 확정된 뒤 별도 단계에서 진행합니다.</div>
    `;

    root.dataset.watchlistMounted = 'true';
    if (window.lucide) window.lucide.createIcons();
  }

  function initialize() {
    const root = document.getElementById('leftContextContent');
    mount(root);
  }

  window.GaemiGTPWatchlist = { mount, initialize };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, { once: true });
  } else {
    initialize();
  }
}());
