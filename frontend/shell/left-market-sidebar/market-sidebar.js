/* Left Market Sidebar — US-only rankings and shell controls. */
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

  function bindMarketControls() {
    const sidebar = document.getElementById('leftMarketSidebar');
    if (!sidebar || sidebar.dataset.marketControlsBound === 'true') return;

    function bindStaticSelection(selector, defaultIndex = 0) {
      const buttons = [...sidebar.querySelectorAll(selector)].filter((button) => !button.disabled);
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
      buttons.forEach((button, index) => button.setAttribute('aria-pressed', String(index === defaultIndex)));
    }

    // Only US market data is requested; static sample rows have been removed.
    const list = sidebar.querySelector('#marketRankingList');
    const title = sidebar.querySelector('#rightListTitle');
    const changeSortButton = sidebar.querySelector('#rightListMetric');
    const subtitle = sidebar.querySelector('.market-sidebar-subtitle');
    const backendUrl = window.location.hostname.endsWith('github.io')
      ? 'https://gaemi-gtp.onrender.com' : window.location.origin;
    const market = 'us';
    let tab = 'popular';
    let requestId = 0;
    let changeSorted = false;

    const applyChangeSort = () => {
      if (!list) return;
      const rows = [...list.querySelectorAll(':scope > button[data-original-index]')];
      rows.sort((a, b) => changeSorted
        ? (Number(b.dataset.changePct) - Number(a.dataset.changePct)) || (Number(a.dataset.originalIndex) - Number(b.dataset.originalIndex))
        : Number(a.dataset.originalIndex) - Number(b.dataset.originalIndex));
      rows.forEach((row, index) => {
        const rank = row.querySelector('[data-market-rank]');
        if (rank) rank.textContent = String(changeSorted ? index + 1 : row.dataset.originalRank).padStart(2, '0');
        list.appendChild(row);
      });
      changeSortButton?.setAttribute('aria-pressed', String(changeSorted));
    };

    const formatUsd = (value) => {
      if (typeof value !== 'number' || !Number.isFinite(value)) return null;
      if (value >= 1e9) return '$' + (value / 1e9).toLocaleString('en-US', { maximumFractionDigits: 2 }) + 'B';
      if (value >= 1e6) return '$' + (value / 1e6).toLocaleString('en-US', { maximumFractionDigits: 2 }) + 'M';
      return '$' + value.toLocaleString('en-US', { maximumFractionDigits: 2 });
    };

    const showUsRanking = async () => {
      const id = ++requestId;
      if (!list) return;
      if (tab !== 'popular' && tab !== 'value') return;
      if (title) title.textContent = tab === 'value' ? '거래대금 TOP 20' : '인기 TOP 20';
      if (subtitle) subtitle.textContent = '/ 네이버 미국 원천';
      list.replaceChildren();
      list.textContent = '순위를 불러오는 중이야.';
      try {
        const path = tab === 'value' ? '/market/trading-value' : '/market/popular';
        const response = await fetch(backendUrl + path + '?market=' + market);
        if (!response.ok) throw new Error('market ranking unavailable');
        const result = await response.json();
        if (id !== requestId) return;
        list.replaceChildren();
        if (result.ok !== true || !Array.isArray(result.items) || !result.items.length) {
          list.textContent = '조회 가능한 순위 원천 데이터가 없어.';
          return;
        }
        result.items.forEach((item, index) => {
          const button = document.createElement('button');
          button.dataset.stockName = String(item.name || '');
          button.dataset.stockSymbol = String(item.symbol || '');
          button.dataset.originalIndex = String(index);
          button.dataset.originalRank = String(item.rank || index + 1);
          button.dataset.changePct = typeof item.change_pct === 'number' && Number.isFinite(item.change_pct)
            ? String(item.change_pct) : '-Infinity';
          button.type = 'button';
          button.className = 'w-full py-3 text-left hover:bg-[#f1f5f9] dark:hover:bg-[#1b1c20] transition cursor-pointer';
          button.addEventListener('click', () => window.openStockInChat?.(item.name, {
            market, menu: tab, name: item.name, symbol: item.symbol,
            rank: item.rank || index + 1,
            display_rank: Number(rank.textContent) || item.rank || index + 1,
            sort: changeSorted ? 'change_pct' : 'source',
            industry: item.industry, price: item.price, change_pct: item.change_pct,
            trading_value: item.trading_value, trading_value_text: item.trading_value_text,
            currency: 'USD', source: 'naver'
          }));

          const top = document.createElement('div');
          top.className = 'grid grid-cols-[24px_minmax(0,1fr)_auto] gap-2 items-start';
          const rank = document.createElement('span');
          rank.className = 'text-[11px] font-bold text-[#64748b] dark:text-[#a1a1aa]';
          rank.dataset.marketRank = 'true';
          rank.textContent = String(item.rank || index + 1).padStart(2, '0');
          const name = document.createElement('span');
          name.className = 'font-bold text-[13px] text-[#0f172a] gtp-dark-text truncate';
          name.textContent = item.name;
          const price = document.createElement('span');
          price.className = 'font-black text-[13px] text-[#0f172a] gtp-dark-text text-right';
          price.textContent = typeof item.price === 'number' && Number.isFinite(item.price)
            ? '$' + item.price.toLocaleString('en-US', { maximumFractionDigits: 2 }) : '';
          top.append(rank, name, price);

          // Match popular ranking's second row; display turnover in the blank
          // cell beneath the stock name and leave the change at the right.
          const secondRow = document.createElement('div');
          secondRow.className = 'grid grid-cols-[24px_minmax(0,1fr)_auto] gap-2 mt-0.5';
          secondRow.appendChild(document.createElement('span'));
          const turnover = document.createElement('span');
          turnover.className = 'text-[11px] font-semibold text-[#64748b] dark:text-[#a1a1aa] truncate';
          const amount = formatUsd(item.trading_value) || item.trading_value_text;
          turnover.textContent = amount ? '거래대금 ' + amount : '';
          const change = document.createElement('span');
          const pct = item.change_pct;
          change.className = 'text-[11px] font-bold text-right' +
            (pct > 0 ? ' text-rose-500' : pct < 0 ? ' text-sky-500' : ' text-[#64748b] dark:text-[#a1a1aa]');
          change.textContent = typeof pct === 'number' && Number.isFinite(pct)
            ? (pct > 0 ? '+' : '') + pct.toFixed(2) + '%' : '';
          secondRow.append(turnover, change);

          // Reuse the industry name from the same ranking result only.
          // Keep the original third row and its blank slots when not provided.
          const thirdRow = document.createElement('div');
          thirdRow.className = 'grid grid-cols-[24px_minmax(0,0.7fr)_minmax(0,1.3fr)] gap-2 mt-1 items-center min-h-[16px]';
          const industry = document.createElement('span');
          industry.className = 'text-[11px] font-semibold text-sky-500 truncate';
          industry.textContent = typeof item.industry === 'string' ? item.industry : '';
          const issue = document.createElement('span');
          issue.dataset.stockIssue = 'true';
          issue.className = 'font-semibold text-[#64748b] dark:text-[#a1a1aa] text-right truncate';
          issue.style.fontSize = '13px';
          issue.textContent = typeof item.issue_headline === 'string' ? item.issue_headline : '';
          thirdRow.append(
            document.createElement('span'),
            industry,
            issue
          );
          button.append(top, secondRow, thirdRow);
          list.appendChild(button);
        });
        applyChangeSort();
      } catch (_) {
        if (id === requestId) list.textContent = '순위 원천 데이터를 가져오지 못했어.';
      }
    };

    // Only refresh the analyzed stock's existing DB-backed issue title.
    // Never recollect news, rerank stocks, or replace the displayed list.
    const refreshAnalyzedIssue = async (event) => {
      const detail = event.detail || {};
      const name = String(detail.name || '').trim();
      if (!name || (tab !== 'popular' && tab !== 'value')) return;
      if (detail.market && detail.market !== market) return;
      const button = [...list.querySelectorAll(':scope > button[data-original-index]')]
        .find((row) => row.dataset.stockName === name &&
          (!detail.symbol || row.dataset.stockSymbol === String(detail.symbol)));
      if (!button) return;
      const currentRequestId = requestId;
      try {
        const response = await fetch(backendUrl + '/market/issue-headlines', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ market, items: [{ name, symbol: button.dataset.stockSymbol }] })
        });
        if (!response.ok) return;
        const data = await response.json();
        if (currentRequestId !== requestId || !list.contains(button)) return;
        const updated = data.ok === true && Array.isArray(data.items) ? data.items[0] : null;
        if (!updated || updated.name !== name || updated.symbol !== button.dataset.stockSymbol) return;
        const issue = button.querySelector('[data-stock-issue]');
        if (issue) issue.textContent = typeof updated.headline === 'string' ? updated.headline : '';
      } catch (_) {
        // Keep the previous headline on transient read failures.
      }
    };
    window.addEventListener('gaemi:analysis-issues-ready', (event) => {
      void refreshAnalyzedIssue(event);
    });

    changeSortButton?.addEventListener('click', () => {
      changeSorted = !changeSorted;
      applyChangeSort();
    });

    bindStaticSelection('[data-info-tab-action]');
    sidebar.querySelectorAll('[data-info-tab-action]').forEach((button) => {
      if (button.disabled) return;
      button.addEventListener('click', () => {
        tab = button.dataset.infoTabAction;
        void showUsRanking();
      });
    });
    sidebar.dataset.marketControlsBound = 'true';
    // Load US popularity ranking on first open, without demo rows.
    void showUsRanking();
  }

  document.addEventListener('DOMContentLoaded', bindMarketControls);

  window.toggleLeftSidebar = toggle;
  window.GaemiGTPMarketSidebar = { toggle, bindMarketControls };
}());
