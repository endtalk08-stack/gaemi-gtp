/* Left context sidebar: browser-local watchlist and recent-stock placeholder. */
(function () {
  'use strict';

  const STORAGE_KEY = 'gaemiGTP_watchlist_v1';

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (character) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
    }[character]));
  }

  function readWatchlist() {
    try {
      const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
      return Array.isArray(stored) ? stored.filter(Boolean) : [];
    } catch (_) {
      return [];
    }
  }

  function render(root) {
    if (!root) return;
    const stocks = readWatchlist();
    const stockList = stocks.length
      ? `<div class="mt-1 space-y-1">${stocks.map((name) => `
          <div class="flex items-center gap-2 rounded-lg px-2 py-2 text-sm font-semibold text-[#475569] dark:text-[#d4d4d8]">
            <i data-lucide="star" class="h-4 w-4 shrink-0 fill-current text-[#db2777] dark:text-[#e889aa]"></i>
            <span class="min-w-0 truncate">${escapeHtml(name)}</span>
          </div>`).join('')}</div>`
      : `
        <div class="context-sidebar-empty">
          <div class="context-sidebar-empty-icon"><i data-lucide="star" class="w-5 h-5"></i></div>
          <div class="context-sidebar-empty-title">관심종목을 추가하세요</div>
          <div class="context-sidebar-empty-copy">관련 종목의 별 아이콘을 누르면 이곳에 저장됩니다.</div>
        </div>`;

    root.innerHTML = `
      <section class="context-sidebar-section" aria-label="관심종목">
        <div class="context-sidebar-section-head">
          <div class="context-sidebar-section-title">관심종목</div>
          <button type="button" class="context-sidebar-section-action" onclick="focusStockInput()" title="종목 검색으로 추가">+ 추가</button>
        </div>
        ${stockList}
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
          <div class="context-sidebar-empty-copy">종목을 확인하면 최근 기록이 이곳에 모입니다.</div>
        </div>
      </section>
    `;

    root.dataset.watchlistMounted = 'true';
    if (window.lucide) window.lucide.createIcons();
  }

  function mount(root) {
    render(root);
  }

  function initialize() {
    mount(document.getElementById('leftContextContent'));
  }

  window.GaemiGTPWatchlist = { mount, initialize, refresh: initialize };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, { once: true });
  } else {
    initialize();
  }
}());
