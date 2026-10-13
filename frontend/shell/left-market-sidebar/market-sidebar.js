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

    const list = sidebar.querySelector('#marketRankingList');
    const title = sidebar.querySelector('#rightListTitle');
    const metric = sidebar.querySelector('#rightListMetric');
    const subtitle = sidebar.querySelector('.market-sidebar-subtitle');
    const originalMarkup = list?.innerHTML || '';
    let requestId = 0;

    const backendUrl = window.location.hostname.endsWith('github.io')
      ? 'https://gaemi-gtp.onrender.com' : window.location.origin;
    const money = (value, market) => new Intl.NumberFormat(
      market === 'kr' ? 'ko-KR' : 'en-US',
      { maximumFractionDigits: market === 'kr' ? 0 : 2 }
    ).format(value);
    const displayTurnover = (value, market) => {
      const unit = market === 'kr' ? '원' : '달러';
      const divisor = market === 'kr' ? 100000000 : 1000000;
      const suffix = market === 'kr' ? '억' : '백만';
      return (value / divisor).toLocaleString('ko-KR', { maximumFractionDigits: 1 }) + suffix + unit;
    };

    async function showRegion(region) {
      const id = ++requestId;
      if (!list) return;
      if (region === '전체') {
        list.innerHTML = originalMarkup;
        if (title) title.textContent = '인기 TOP 20';
        if (metric) metric.textContent = '현재가';
        if (subtitle) subtitle.textContent = '/ 고정 예시 데이터';
        return;
      }
      if (region === '코인') {
        list.replaceChildren();
        list.textContent = '코인 거래대금 순위는 아직 연결되지 않았어.';
        if (title) title.textContent = '코인';
        if (metric) metric.textContent = '';
        return;
      }
      const market = region === '국내' ? 'kr' : 'us';
      if (title) title.textContent = region + ' 등록종목 거래대금 TOP 22 (추정)';
      if (metric) metric.textContent = '현재가';
      if (subtitle) subtitle.textContent = '/ 조회 시 갱신';
      list.replaceChildren();
      list.textContent = '거래대금 순위를 조회 중이야.';
      try {
        const response = await fetch(backendUrl + '/market/registered-turnover?market=' + market);
        if (!response.ok) throw new Error('ranking unavailable');
        const result = await response.json();
        if (id !== requestId) return;
        list.replaceChildren();
        if (!result.ok || !result.items?.length) {
          list.textContent = '조회 가능한 종목 데이터가 없어.';
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
          rank.textContent = String(index + 1).padStart(2, '0');
          const name = document.createElement('span');
          name.className = 'font-bold text-[13px] text-[#0f172a] gtp-dark-text truncate';
          name.textContent = item.name;
          const price = document.createElement('span');
          price.className = 'font-semibold text-[13px] text-[#0f172a] gtp-dark-text text-right';
          price.textContent = money(item.price, market) + (market === 'kr' ? '원' : '달러');
          top.append(rank, name, price);
          const bottom = document.createElement('div');
          bottom.className = 'flex justify-between pl-8 mt-1 text-[11px] text-[#64748b] dark:text-[#a1a1aa]';
          const turnover = document.createElement('span');
          turnover.textContent = '추정 거래대금 ' + displayTurnover(item.turnover_estimate, market);
          const change = document.createElement('span');
          const pct = item.change_pct;
          change.textContent = typeof pct === 'number' ? (pct > 0 ? '+' : '') + pct.toFixed(2) + '%' : '';
          change.className = pct > 0 ? 'text-rose-500' : pct < 0 ? 'text-sky-500' : '';
          bottom.append(turnover, change);
          button.append(top, bottom);
          list.appendChild(button);
        });
      } catch (_) {
        if (id === requestId) list.textContent = '거래대금 데이터를 가져오지 못했어. 다시 선택해 줘.';
      }
    }
    sidebar.querySelectorAll('[data-legacy-region]').forEach((button) => {
      button.addEventListener('click', () => { void showRegion(button.textContent.trim()); });
    });

    bindStaticSelection('[data-legacy-region]');
    bindStaticSelection('[data-info-tab-action]');
    sidebar.dataset.marketControlsBound = 'true';
  }

  document.addEventListener('DOMContentLoaded', bindMarketControls);

  window.toggleLeftSidebar = toggle;
  window.GaemiGTPMarketSidebar = { toggle, bindMarketControls };
}());
