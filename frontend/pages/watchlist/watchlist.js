/* Left context sidebar: browser-local watchlist. */
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

  function writeWatchlist(stocks) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(stocks));
  }

  function removeWatchlistStock(name) {
    writeWatchlist(readWatchlist().filter((stock) => stock !== name));
    render(document.getElementById('leftContextContent'));
  }

  function render(root) {
    if (!root) return;
    const stocks = readWatchlist();
    const stockList = stocks.length
      ? `<div class="mt-1 space-y-1">${stocks.map((name) => `
          <div class="flex items-center gap-2 rounded-lg px-2 py-2 text-sm font-semibold text-[#475569] dark:text-[#d4d4d8]">
            <i data-lucide="star" class="h-4 w-4 shrink-0 fill-current text-[#db2777] dark:text-[#e889aa]"></i>
            <span class="min-w-0 flex-1 truncate">${escapeHtml(name)}</span>
            <button type="button" class="shrink-0 rounded p-1 text-[#94a3b8] transition hover:text-[#475569] dark:text-[#71717a] dark:hover:text-white" data-watchlist-remove="${escapeHtml(name)}" aria-label="${escapeHtml(name)} 관심종목 삭제" title="관심종목 삭제">
              <i data-lucide="x" class="h-3.5 w-3.5"></i>
            </button>
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
    `;

    root.querySelectorAll('[data-watchlist-remove]').forEach((button) => {
      button.addEventListener('click', () => removeWatchlistStock(button.dataset.watchlistRemove));
    });

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
