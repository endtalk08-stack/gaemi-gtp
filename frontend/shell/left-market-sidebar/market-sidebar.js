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

    // KR and USA trading-value tabs use source-specific market-wide ranking results.
    // Other tabs retain their existing UI and do not start new collectors.
    const list = sidebar.querySelector('#marketRankingList');
    const title = sidebar.querySelector('#rightListTitle');
    const changeSortButton = sidebar.querySelector('#rightListMetric');
    const subtitle = sidebar.querySelector('.market-sidebar-subtitle');
    const initialMarkup = list?.innerHTML || '';
    const backendUrl = window.location.hostname.endsWith('github.io')
      ? 'https://gaemi-gtp.onrender.com' : window.location.origin;
    let region = '국내';
    let tab = 'popular';
    let requestId = 0;
    let changeSorted = false;
    const issueByStock = new Map();

    // Reuse the selected central analysis result. The sidebar fetches no extra news.
    const syncIssueToRow = () => {
      if (!list) return;
      const data = window.GaemiGTPAnalysisData?.get?.();
      const stock = String(data?.stockName || '').trim();
      const eventTitle = String(data?.issueBriefs?.[0]?.headline || '').trim();
      if (!stock || !eventTitle) return;
      const row = [...list.querySelectorAll(':scope > button[data-stock-name]')]
        .find(button => button.dataset.stockName === stock);
      if (!row) return;
      const rate = Number(row.dataset.changePct);
      const direction = Number.isFinite(rate) && rate > 0 ? '상승'
        : Number.isFinite(rate) && rate < 0 ? '하락' : '보합';
      // Show verified event plus observed movement, not an unproven causal claim.
      const display = `${eventTitle} · ${direction}`;
      issueByStock.set(`${region}:${stock}`, display);
      const label = row.querySelector('[data-stock-issue]');
      if (label) label.textContent = display;
    };

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

    const formatMoney = (value) => {
      if (typeof value !== 'number' || !Number.isFinite(value)) return null;
      if (value >= 1e12) return (value / 1e12).toLocaleString('ko-KR', { maximumFractionDigits: 2 }) + '조원';
      if (value >= 1e8) return (value / 1e8).toLocaleString('ko-KR', { maximumFractionDigits: 1 }) + '억원';
      return value.toLocaleString('ko-KR') + '원';
    };
    const formatUsd = (value) => {
      if (typeof value !== 'number' || !Number.isFinite(value)) return null;
      if (value >= 1e9) return '$' + (value / 1e9).toLocaleString('en-US', { maximumFractionDigits: 2 }) + 'B';
      if (value >= 1e6) return '$' + (value / 1e6).toLocaleString('en-US', { maximumFractionDigits: 2 }) + 'M';
      return '$' + value.toLocaleString('en-US', { maximumFractionDigits: 2 });
    };

    const showDomesticRanking = async () => {
      const id = ++requestId;
      if (!list) return;
      const market = region === '국내' ? 'kr' : region === '해외' ? 'us' : null;
      if ((tab !== 'value' && tab !== 'popular') || (tab === 'popular' && !market)) {
        list.innerHTML = initialMarkup;
        if (title) title.textContent = '인기 TOP 20';
        if (subtitle) subtitle.textContent = '/ 고정 예시 데이터';
        return;
      }
      if (title) title.textContent = tab === 'value' ? '거래대금 TOP 20' : '인기 TOP 20';
      if (!market) {
        list.replaceChildren();
        list.textContent = '국내 또는 해외를 선택하면 해당 순위를 볼 수 있어.';
        return;
      }

      if (subtitle) subtitle.textContent = market === 'us' ? '/ 네이버 미국 원천' : '/ 네이버 국내 원천';
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
          button.dataset.stockName = item.name;
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
            currency: market === 'us' ? 'USD' : 'KRW', source: 'naver'
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
            ? (market === 'us' ? '$' + item.price.toLocaleString('en-US', { maximumFractionDigits: 2 }) : item.price.toLocaleString('ko-KR') + '원') : '';
          top.append(rank, name, price);

          // Match popular ranking's second row; display turnover in the blank
          // cell beneath the stock name and leave the change at the right.
          const secondRow = document.createElement('div');
          secondRow.className = 'grid grid-cols-[24px_minmax(0,1fr)_auto] gap-2 mt-0.5';
          secondRow.appendChild(document.createElement('span'));
          const turnover = document.createElement('span');
          turnover.className = 'text-[11px] font-semibold text-[#64748b] dark:text-[#a1a1aa] truncate';
          const amount = (market === 'us' ? formatUsd(item.trading_value) : formatMoney(item.trading_value)) || item.trading_value_text;
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
          issue.className = 'text-[11px] font-semibold text-[#64748b] dark:text-[#a1a1aa] text-right truncate';
          issue.textContent = issueByStock.get(`${market}:${item.name}`) || '';
          thirdRow.append(
            document.createElement('span'),
            industry,
            issue
          );
          button.append(top, secondRow, thirdRow);
          list.appendChild(button);
        });
        applyChangeSort();
        syncIssueToRow();
      } catch (_) {
        if (id === requestId) list.textContent = '순위 원천 데이터를 가져오지 못했어.';
      }
    };

    changeSortButton?.addEventListener('click', () => {
      changeSorted = !changeSorted;
      applyChangeSort();
    });

    bindStaticSelection('[data-legacy-region]');
    bindStaticSelection('[data-info-tab-action]');
    sidebar.querySelectorAll('[data-legacy-region]').forEach((button) => {
      if (button.disabled) return;
      button.addEventListener('click', () => {
        region = button.textContent.trim();
        void showDomesticRanking();
      });
    });
    sidebar.querySelectorAll('[data-info-tab-action]').forEach((button) => {
      if (button.disabled) return;
      button.addEventListener('click', () => {
        tab = button.dataset.infoTabAction;
        void showDomesticRanking();
      });
    });
    window.addEventListener('gaemi-analysis-data-change', syncIssueToRow);
    sidebar.dataset.marketControlsBound = 'true';
    // Show the live KR popularity list on the first market sidebar view.
    void showDomesticRanking();
  }

  document.addEventListener('DOMContentLoaded', bindMarketControls);

  window.toggleLeftSidebar = toggle;
  window.GaemiGTPMarketSidebar = { toggle, bindMarketControls };
}());
