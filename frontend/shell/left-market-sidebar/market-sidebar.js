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

  const REGION_LABELS = { all: '전체', KR: '국내', global: '해외', crypto: '코인' };
  const RANK_LABELS = {
    popularity: '인기순위',
    trading_value: '거래대금',
    gainers: '상승률',
    losers: '하락률'
  };

  function bindMarketControls() {
    const sidebar = document.getElementById('leftMarketSidebar');
    if (!sidebar || sidebar.dataset.marketControlsBound === 'true') return;

    let region = 'all';
    let rankType = 'popularity';
    const selection = document.getElementById('marketSidebarSelection');
    const copy = document.getElementById('marketSidebarEmptyCopy');

    function renderSelection() {
      const regionLabel = REGION_LABELS[region];
      const rankLabel = RANK_LABELS[rankType];
      if (selection) selection.textContent = `${regionLabel} ${rankLabel}`;
      if (copy) copy.textContent = `키움 원천 데이터가 수집되면 ${regionLabel} ${rankLabel} Top 20을 표시합니다.`;
    }

    sidebar.querySelectorAll('[data-market-region]').forEach((button) => {
      button.addEventListener('click', () => {
        region = button.dataset.marketRegion;
        sidebar.querySelectorAll('[data-market-region]').forEach((item) => {
          const active = item === button;
          item.classList.toggle('is-active', active);
          item.setAttribute('aria-selected', String(active));
        });
        renderSelection();
      });
    });

    sidebar.querySelectorAll('[data-market-rank]').forEach((button) => {
      button.addEventListener('click', () => {
        rankType = button.dataset.marketRank;
        sidebar.querySelectorAll('[data-market-rank]').forEach((item) => {
          const active = item === button;
          item.classList.toggle('is-active', active);
          item.setAttribute('aria-selected', String(active));
        });
        renderSelection();
      });
    });

    sidebar.dataset.marketControlsBound = 'true';
    renderSelection();
  }

  document.addEventListener('DOMContentLoaded', bindMarketControls);

  window.toggleLeftSidebar = toggle;
  window.GaemiGTPMarketSidebar = { toggle, bindMarketControls };
}());
