/* Left Market Sidebar — market shell open/close controls only. */
(function () {
  'use strict';

  function applyState() {
    window.GaemiGTPWorkspaceShellState?.apply?.();
  }

  function toggle() {
    if (typeof window.workspaceUIReady !== 'undefined' && !window.workspaceUIReady) return;

    const isOpen = document.body.classList.contains('left-market-open');
    if (!isOpen) {
      document.body.classList.remove('left-home-open', 'left-context-open', 'left-plugin-open');
      if (window.innerWidth < 1024) {
        document.body.classList.remove('right-panel-open', 'right-panel-maximized');
      }
    }

    document.body.classList.toggle('left-market-open', !isOpen);
    applyState();
  }

  // Phase 1: preserve the sidebar shell and menus, but display no old KR/US
  // popular or trading-value stocks. A verified market-cap API is not wired yet.
  function bindMarketControls() {
    const sidebar = document.getElementById('leftMarketSidebar');
    if (!sidebar || sidebar.dataset.marketControlsBound === 'true') return;

    const list = sidebar.querySelector('#marketRankingList');
    const title = sidebar.querySelector('#rightListTitle');
    const subtitle = sidebar.querySelector('.market-sidebar-subtitle');
    const regionButtons = [...sidebar.querySelectorAll('[data-legacy-region]')]
      .filter((button) => !button.disabled);
    const tabButtons = [...sidebar.querySelectorAll('[data-info-tab-action]')]
      .filter((button) => !button.disabled);
    let region = '해외';
    let tab = 'cap';

    function selectButton(buttons, current) {
      buttons.forEach((button) => {
        const active = button === current;
        button.classList.toggle('bg-[#eef2f7]', active);
        button.classList.toggle('dark:bg-[#272a31]', active);
        button.classList.toggle('gtp-dark-text', active);
        button.classList.toggle('text-[#0f172a]', active);
        button.classList.toggle('text-[#64748b]', !active);
        button.classList.toggle('dark:text-[#a1a1aa]', !active);
        button.setAttribute('aria-pressed', String(active));
      });
    }

    // The 20 company names and existing AI issue titles are already fetched
    // by the watchlist. Never request quotes, market rankings, or news here.
    function showUsCapStocks() {
      if (region !== '해외' || tab !== 'cap' || !list) return false;
      const watchlist = window.GaemiGTPWatchlist;
      const rows = watchlist?.getDisplayRows?.('US') || [];
      if (rows.length !== 20) return false;
      list.replaceChildren();
      rows.forEach((row) => {
        const item = document.createElement('div');
        item.className = 'border-b border-[#e2e8f0] px-2 py-2 text-[13px] dark:border-[#3f3f46]';
        const name = document.createElement('button');
        name.type = 'button';
        name.className = 'block w-full truncate text-left font-semibold text-[#334155] dark:text-[#e4e4e7]';
        name.textContent = row.name;
        name.addEventListener('click', () => watchlist.openSavedIssues('US', row.symbol));
        item.appendChild(name);
        (row.issues || []).forEach((issue, index) => {
          const title = document.createElement('button');
          title.type = 'button';
          title.className = 'mt-1 block w-full truncate text-left text-[12px] text-[#64748b] dark:text-[#a1a1aa]';
          title.textContent = issue.headline;
          title.title = issue.headline;
          title.addEventListener('click', () => watchlist.openSavedIssues('US', row.symbol, index));
          item.appendChild(title);
        });
        list.appendChild(item);
      });
      return true;
    }

    function showEmptyList() {
      const menuLabel = tab === 'cap' ? '시가총액' : tab === 'popular' ? '인기' : '거래대금';
      if (title) title.textContent = region === '해외' && tab === 'cap'
        ? '미국 시가총액 TOP 20' : menuLabel + ' TOP 20';
      if (subtitle) subtitle.textContent = region === '해외' ? '/ 미국 20종목 준비' : '/ 준비 중';
      if (!list) return;
      if (showUsCapStocks()) return;
      list.replaceChildren();
      const message = document.createElement('p');
      message.className = 'py-6 text-center text-[12px] text-[#64748b] dark:text-[#a1a1aa]';
      message.textContent = region === '국내'
        ? '국내 종목은 1차 서비스에서 제외되었습니다.'
        : tab === 'cap'
          ? '미국 시가총액 TOP 20 데이터 연결 전입니다.'
          : '기존 종목 목록을 비웠습니다. 새로운 데이터 연결 전입니다.';
      list.appendChild(message);
    }

    regionButtons.forEach((button) => {
      button.addEventListener('click', () => {
        region = button.textContent.trim();
        selectButton(regionButtons, button);
        showEmptyList();
      });
    });
    tabButtons.forEach((button) => {
      button.addEventListener('click', () => {
        tab = button.dataset.infoTabAction;
        selectButton(tabButtons, button);
        showEmptyList();
      });
    });

    selectButton(regionButtons, regionButtons.find((button) => button.textContent.trim() === region));
    selectButton(tabButtons, tabButtons.find((button) => button.dataset.infoTabAction === tab));
    showEmptyList();
    // Populate the active tab as soon as the existing Neon-only watchlist read ends.
    window.addEventListener('gaemi:fixed-stocks-ready', showEmptyList);
    sidebar.dataset.marketControlsBound = 'true';
  }

  document.addEventListener('DOMContentLoaded', bindMarketControls);

  window.toggleLeftSidebar = toggle;
  window.GaemiGTPMarketSidebar = { toggle, bindMarketControls };
}());
