/* Left Market Sidebar — US-only rankings and shell controls. */
(function () {
  'use strict';

  // Logos are bundled locally when possible; fallback favicons never hide the ticker mark.
  const STOCK_DOMAINS = {
    NVDA: 'nvidia.com', SPCX: 'spacex.com', TSLA: 'tesla.com',
    META: 'meta.com', AAPL: 'apple.com', MSFT: 'microsoft.com',
    GOOGL: 'google.com', GOOG: 'google.com', AMZN: 'amazon.com',
    AMD: 'amd.com', INTC: 'intel.com', TSM: 'tsmc.com',
    AVGO: 'broadcom.com', PLTR: 'palantir.com', MU: 'micron.com',
    ORCL: 'oracle.com', QCOM: 'qualcomm.com', ASML: 'asml.com',
    NFLX: 'netflix.com', CRM: 'salesforce.com', IBM: 'ibm.com',
    LLY: 'lilly.com', SKHY: 'skhynix.com', SNDK: 'sandisk.com',
    SMCI: 'supermicro.com', QQQ: 'invesco.com', SPY: 'ssga.com',
    SOXX: 'ishares.com', GLD: 'ssga.com', SLV: 'ishares.com'
  };

  // Bundled SVG images: theSVG (CC0), https://github.com/glincker/thesvg
  const STOCK_LOCAL_LOGOS = { SKHY: 'sk-hynix.svg', MU: 'micron.svg', SNDK: 'sandisk.svg' };

  function stockMark(item) {
    const ticker = String(item.symbol || '').trim().toUpperCase()
      .replace(/^US:/, '').replace(/\.(?:O|N|K)$/, '');
    const mark = document.createElement('span');
    mark.className = 'market-stock-logo';
    const fallback = document.createElement('span');
    fallback.className = 'market-stock-logo-fallback';
    fallback.textContent = (ticker || String(item.name || '?')).slice(0, 2);
    mark.appendChild(fallback);

    const icon = window.GaemiGTPStockMarks?.[ticker];
    if (icon && icon.path && icon.color) {
      const ns = 'http://www.w3.org/2000/svg';
      const svg = document.createElementNS(ns, 'svg');
      svg.setAttribute('class', 'market-stock-logo-image');
      svg.setAttribute('viewBox', icon.viewBox || '0 0 24 24');
      svg.setAttribute('aria-hidden', 'true');
      const path = document.createElementNS(ns, 'path');
      path.setAttribute('d', icon.path);
      path.setAttribute('fill', '#' + icon.color);
      svg.appendChild(path);
      mark.replaceChildren(svg);
    } else if (STOCK_LOCAL_LOGOS[ticker] || STOCK_DOMAINS[ticker]) {
      const img = document.createElement('img');
      img.className = 'market-stock-logo-image';
      img.alt = '';
      img.loading = 'lazy';
      img.decoding = 'async';
      img.src = STOCK_LOCAL_LOGOS[ticker]
        ? 'shell/left-market-sidebar/logos/' + STOCK_LOCAL_LOGOS[ticker]
        : 'https://www.google.com/s2/favicons?domain='
          + encodeURIComponent(STOCK_DOMAINS[ticker]) + '&sz=64';
      img.addEventListener('load', () => { fallback.hidden = true; });
      img.addEventListener('error', () => { img.hidden = true; fallback.hidden = false; });
      mark.appendChild(img);
    }
    return mark;
  }

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
    const backendUrl = window.location.hostname.endsWith('github.io')
      ? 'https://gaemi-gtp.onrender.com' : window.location.origin;
    const market = 'us';
    let tab = 'popular';
    let requestId = 0;
    let changeSorted = false;
    let draggedRow = null;
    const orderKey = () => 'gaemiGTP_market_sidebar_order_us_' + tab + '_v1';
    const readOrder = () => {
      try {
        const value = JSON.parse(localStorage.getItem(orderKey()) || '[]');
        return Array.isArray(value) ? value.filter((item) => typeof item === 'string').slice(0, 100) : [];
      } catch (_) { return []; }
    };
    let customOrder = readOrder();
    const saveOrder = () => {
      customOrder = [...list.querySelectorAll(':scope > button[data-original-index]')]
        .map((row) => row.dataset.rowId);
      try { localStorage.setItem(orderKey(), JSON.stringify(customOrder)); } catch (_) { /* local storage unavailable */ }
    };
    const applyChangeSort = () => {
      if (!list) return;
      const rows = [...list.querySelectorAll(':scope > button[data-original-index]')];
      const positions = new Map(customOrder.map((key, index) => [key, index]));
      const sourceIndex = (row) => Number(row.dataset.originalIndex);
      rows.sort((a, b) => {
        if (changeSorted) {
          return (Number(b.dataset.changePct) - Number(a.dataset.changePct)) || (sourceIndex(a) - sourceIndex(b));
        }
        if (customOrder.length) {
          const ai = positions.has(a.dataset.rowId) ? positions.get(a.dataset.rowId) : Infinity;
          const bi = positions.has(b.dataset.rowId) ? positions.get(b.dataset.rowId) : Infinity;
          return (ai - bi) || (sourceIndex(a) - sourceIndex(b));
        }
        return sourceIndex(a) - sourceIndex(b);
      });
      rows.forEach((row, index) => {
        const rank = row.querySelector('[data-market-rank]');
        // A manually arranged list still shows the original market rank.
        if (rank) rank.textContent = String(changeSorted ? index + 1 : row.dataset.originalRank).padStart(2, '0');
        list.appendChild(row);
      });
      changeSortButton?.setAttribute('aria-pressed', String(changeSorted));
    };
    const finishReorder = () => {
      changeSorted = false;
      saveOrder();
      applyChangeSort();
    };
    // Native drag and drop: the grip is the only draggable element.
    list?.addEventListener('dragover', (event) => {
      if (!draggedRow) return;
      const target = event.target.closest('button[data-original-index]');
      if (!target || target === draggedRow) return;
      event.preventDefault();
      if (event.dataTransfer) event.dataTransfer.dropEffect = 'move';
    });
    list?.addEventListener('drop', (event) => {
      if (!draggedRow) return;
      const target = event.target.closest('button[data-original-index]');
      if (!target || target === draggedRow) return;
      event.preventDefault();
      const bounds = target.getBoundingClientRect();
      const after = event.clientY > bounds.top + bounds.height / 2;
      list.insertBefore(draggedRow, after ? target.nextSibling : target);
      finishReorder();
    });
    list?.addEventListener('dragend', () => {
      draggedRow?.classList.remove('market-stock-dragging');
      draggedRow = null;
    });

    const showUsRanking = async () => {
      const id = ++requestId;
      if (!list) return;
      if (tab !== 'popular' && tab !== 'value') return;
      if (title) title.textContent = tab === 'value' ? '거래대금 TOP 20' : '인기 TOP 20';
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
          button.dataset.rowId = String(item.symbol || item.name || index);
          button.dataset.originalRank = String(item.rank || index + 1);
          button.dataset.changePct = typeof item.change_pct === 'number' && Number.isFinite(item.change_pct)
            ? String(item.change_pct) : '-Infinity';
          button.type = 'button';
          button.className = 'market-stock-row';
          button.setAttribute('aria-label', String(item.name || '') + ' 종목 열기. Alt + 위아래 방향키로 순서 변경');
          button.addEventListener('keydown', (event) => {
            if (!event.altKey || !['ArrowUp', 'ArrowDown'].includes(event.key)) return;
            const rows = [...list.querySelectorAll(':scope > button[data-original-index]')];
            const position = rows.indexOf(button);
            const next = rows[position + (event.key === 'ArrowUp' ? -1 : 1)];
            if (!next) return;
            event.preventDefault();
            list.insertBefore(button, event.key === 'ArrowUp' ? next : next.nextSibling);
            finishReorder();
            button.focus();
          });
          const grip = document.createElement('span');
          grip.className = 'market-stock-grip';
          grip.draggable = true;
          grip.title = '끌어서 종목 순서 이동';
          grip.textContent = '⠿';
          grip.setAttribute('aria-hidden', 'true');
          grip.addEventListener('dragstart', (event) => {
            draggedRow = button;
            button.classList.add('market-stock-dragging');
            if (event.dataTransfer) {
              event.dataTransfer.effectAllowed = 'move';
              event.dataTransfer.setData('text/plain', button.dataset.rowId);
            }
          });
          grip.addEventListener('dragend', () => {
            button.classList.remove('market-stock-dragging');
            draggedRow = null;
          });
          button.addEventListener('click', () => window.openStockInChat?.(item.name, {
            market, menu: tab, name: item.name, symbol: item.symbol,
            rank: item.rank || index + 1,
            display_rank: Number(rank.textContent) || item.rank || index + 1,
            sort: changeSorted ? 'change_pct' : 'source',
            industry: item.industry, price: item.price, change_pct: item.change_pct,
            trading_value: item.trading_value, trading_value_text: item.trading_value_text,
            currency: 'USD', source: 'naver'
          }));

          const content = document.createElement('div');
          content.className = 'market-stock-content';
          const top = document.createElement('div');
          top.className = 'market-stock-top';
          const rank = document.createElement('span');
          rank.className = 'market-stock-rank';
          rank.dataset.marketRank = 'true';
          rank.textContent = String(item.rank || index + 1).padStart(2, '0');
          const name = document.createElement('span');
          name.className = 'market-stock-name';
          name.textContent = item.name;
          const price = document.createElement('span');
          price.className = 'market-stock-price';
          price.textContent = typeof item.price === 'number' && Number.isFinite(item.price)
            ? '$' + item.price.toLocaleString('en-US', { maximumFractionDigits: 2 }) : '';
          const nameGroup = document.createElement('span');
          nameGroup.className = 'market-stock-name-group';
          nameGroup.append(rank, name);
          top.append(nameGroup, price);

          // Show industry in the former turnover slot; keep price change at right.
          const secondRow = document.createElement('div');
          secondRow.className = 'market-stock-second';
          const industry = document.createElement('span');
          industry.className = 'market-stock-industry';
          const watchStar = document.createElement('span');
          watchStar.className = 'market-stock-watch-star';
          watchStar.textContent = '☆';
          watchStar.title = '관심종목 (연결 전)';
          watchStar.setAttribute('role', 'button');
          watchStar.setAttribute('aria-label', '관심종목 기능 연결 예정');
          watchStar.tabIndex = 0;
          // Interactive placeholder only: no watchlist registration or persistence.
          watchStar.addEventListener('click', (event) => {
            event.stopPropagation();
            watchStar.focus();
          });
          watchStar.addEventListener('keydown', (event) => {
            if (event.key !== 'Enter' && event.key !== ' ') return;
            event.preventDefault();
            event.stopPropagation();
            watchStar.focus();
          });
          const industryLabel = document.createElement('span');
          industryLabel.className = 'market-stock-industry-label';
          industryLabel.textContent = typeof item.industry === 'string' ? item.industry : '';
          industry.append(watchStar, industryLabel);
          const change = document.createElement('span');
          const pct = item.change_pct;
          change.className = 'market-stock-change' +
            (pct > 0 ? ' text-rose-500' : pct < 0 ? ' text-sky-500' : ' text-[#64748b] dark:text-[#a1a1aa]');
          change.textContent = typeof pct === 'number' && Number.isFinite(pct)
            ? (pct > 0 ? '+' : '') + pct.toFixed(2) + '%' : '';
          secondRow.append(industry, change);

          // Dedicate the full third row to a single-line AI issue headline.
          const thirdRow = document.createElement('div');
          thirdRow.className = 'market-stock-third';
          const issue = document.createElement('span');
          issue.dataset.stockIssue = 'true';
          issue.className = 'font-semibold text-[#64748b] dark:text-[#a1a1aa] text-right truncate';
          issue.style.fontSize = '13px';
          issue.textContent = typeof item.issue_headline === 'string' ? item.issue_headline : '';
          thirdRow.append(issue);
          content.append(top, secondRow, thirdRow);
          button.append(grip, stockMark(item), content);
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
        customOrder = readOrder();
        changeSorted = false;
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
