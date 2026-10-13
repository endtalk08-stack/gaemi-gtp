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

  // The restored market list is a fixed layout sample, not a live ranking feed.
  function bindMarketControls() {
    const sidebar = document.getElementById('leftMarketSidebar');
    if (!sidebar || sidebar.dataset.marketControlsBound === 'true') return;

    function bindStaticSelection(selector) {
      const buttons = [...sidebar.querySelectorAll(selector)];
      buttons.forEach((button) => {
        button.addEventListener('click', () => {
          buttons.forEach((item) => {
            const active = item === button;
            item.classList.toggle('bg-[#eef2f7]', active);
            item.classList.toggle('dark:bg-[#272a31]', active);
            item.classList.toggle('gtp-dark-text', active);
            item.classList.toggle('text-[#0f172a]', active);
            item.classList.toggle('text-[#64748b]', !active);
            item.classList.toggle('dark:text-[#a1a1aa]', !active);
            item.setAttribute('aria-pressed', String(active));
          });
        });
      });
      buttons.forEach((button, index) => button.setAttribute('aria-pressed', String(index === 0)));
    }

    // Only the domestic trading-value tab uses a live, market-wide result.
    // Other tabs retain their existing UI and do not start new collectors.
    const list = sidebar.querySelector('#marketRankingList');
    const title = sidebar.querySelector('#rightListTitle');
    const subtitle = sidebar.querySelector('.market-sidebar-subtitle');
    const initialMarkup = list?.innerHTML || '';
    const backendUrl = window.location.hostname.endsWith('github.io')
      ? 'https://gaemi-gtp.onrender.com' : window.location.origin;
    let region = '전체';
    let tab = 'popular';
    let requestId = 0;

    const formatMoney = (value) => {
      if (typeof value !== 'number' || !Number.isFinite(value)) return null;
      if (value >= 1e12) return (value / 1e12).toLocaleString('ko-KR', { maximumFractionDigits: 2 }) + '조원';
      if (value >= 1e8) return (value / 1e8).toLocaleString('ko-KR', { maximumFractionDigits: 1 }) + '억원';
      return value.toLocaleString('ko-KR') + '원';
    };

    const showDomesticRanking = async () => {
      const id = ++requestId;
      if (!list) return;
      if (tab !== 'value') {
        list.innerHTML = initialMarkup;
        if (title) title.textContent = '인기 TOP 20';
        if (subtitle) subtitle.textContent = '/ 고정 예시 데이터';
        return;
      }
      if (title) title.textContent = '거래대금 TOP 20';
      if (region !== '국내') {
        list.replaceChildren();
        list.textContent = '현재 국내 거래대금 순위만 원천 데이터에 연결되어 있어.';
        return;
      }

      if (subtitle) subtitle.textContent = '/ 네이버 시장 원천';
      list.replaceChildren();
      list.textContent = '거래대금 순위를 불러오는 중이야.';
      try {
        const response = await fetch(backendUrl + '/market/trading-value');
        if (!response.ok) throw new Error('market ranking unavailable');
        const result = await response.json();
        if (id !== requestId) return;
        list.replaceChildren();
        if (result.ok !== true || !Array.isArray(result.items) || !result.items.length) {
          list.textContent = '조회 가능한 거래대금 원천 데이터가 없어.';
          return;
        }
        result.items.forEach((item, index) => {
          const button = document.createElement('button');
          button.type = 'button';
          button.className = 'w-full py-3 text-left hover:bg-[#f1f5f9] dark:hover:bg-[#1b1c20] transition cursor-pointer';
          button.addEventListener('click', () => window.openStockInChat?.(item.name));

          const top = document.createElement('div');
          top.className = 'grid grid-cols-[24px_minmax(0,1fr)_auto] gap-2 items-start';
          const rank = document.createElement('span');
          rank.className = 'text-[11px] font-bold text-[#64748b] dark:text-[#a1a1aa]';
          rank.textContent = String(item.rank || index + 1).padStart(2, '0');
          const name = document.createElement('span');
          name.className = 'font-bold text-[13px] text-[#0f172a] gtp-dark-text truncate';
          name.textContent = item.name;
          const price = document.createElement('span');
          price.className = 'font-black text-[13px] text-[#0f172a] gtp-dark-text text-right';
          price.textContent = typeof item.price === 'number' && Number.isFinite(item.price)
            ? item.price.toLocaleString('ko-KR') + '원' : '';
          top.append(rank, name, price);

          // Match popular ranking's second row; display turnover in the blank
          // cell beneath the stock name and leave the change at the right.
          const secondRow = document.createElement('div');
          secondRow.className = 'grid grid-cols-[24px_minmax(0,1fr)_auto] gap-2 mt-0.5';
          secondRow.appendChild(document.createElement('span'));
          const turnover = document.createElement('span');
          turnover.className = 'text-[11px] font-semibold text-[#64748b] dark:text-[#a1a1aa] truncate';
          const amount = formatMoney(item.trading_value) || item.trading_value_text;
          turnover.textContent = amount ? '거래대금 ' + amount : '';
          const change = document.createElement('span');
          const pct = item.change_pct;
          change.className = 'text-[11px] font-bold text-right' +
            (pct > 0 ? ' text-rose-500' : pct < 0 ? ' text-sky-500' : ' text-[#64748b] dark:text-[#a1a1aa]');
          change.textContent = typeof pct === 'number' && Number.isFinite(pct)
            ? (pct > 0 ? '+' : '') + pct.toFixed(2) + '%' : '';
          secondRow.append(turnover, change);

          // Preserve the existing third-row space without inventing industry
          // or rising/falling explanations that have no verified source.
          const thirdRow = document.createElement('div');
          thirdRow.className = 'grid grid-cols-[24px_minmax(0,0.7fr)_minmax(0,1.3fr)] gap-2 mt-1 items-center';
          thirdRow.append(
            document.createElement('span'),
            document.createElement('span'),
            document.createElement('span')
          );
          button.append(top, secondRow, thirdRow);
          list.appendChild(button);
        });
      } catch (_) {
        if (id === requestId) list.textContent = '거래대금 원천 데이터를 가져오지 못했어.';
      }
    };

    bindStaticSelection('[data-legacy-region]');
    bindStaticSelection('[data-info-tab-action]');
    sidebar.querySelectorAll('[data-legacy-region]').forEach((button) => {
      button.addEventListener('click', () => {
        region = button.textContent.trim();
        void showDomesticRanking();
      });
    });
    sidebar.querySelectorAll('[data-info-tab-action]').forEach((button) => {
      button.addEventListener('click', () => {
        tab = button.dataset.infoTabAction;
        void showDomesticRanking();
      });
    });
    sidebar.dataset.marketControlsBound = 'true';
  }

  document.addEventListener('DOMContentLoaded', bindMarketControls);

  window.toggleLeftSidebar = toggle;
  window.GaemiGTPMarketSidebar = { toggle, bindMarketControls };
}());
