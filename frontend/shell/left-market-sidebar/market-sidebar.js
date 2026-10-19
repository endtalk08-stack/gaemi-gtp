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

    // Existing Neon names and AI headlines only. No quote or ranking requests.
    let savedUsRows = null;
    let savedUsError = false;
    let savedUsPending = null;

    function loadUsCapRows() {
      if (savedUsRows || savedUsPending || savedUsError) return;
      savedUsPending = fetch('/api/market/us-cap-headlines', { credentials: 'same-origin' })
        .then((response) => {
          if (!response.ok) throw new Error('us_cap_read_unavailable');
          return response.json();
        })
        .then((payload) => {
          if (!payload?.ok || !Array.isArray(payload.items) || payload.items.length !== 20) {
            throw new Error('us_cap_rows_invalid');
          }
          savedUsRows = payload.items.map((item) => ({
            name: typeof item.name === 'string' ? item.name : '',
            headlines: Array.isArray(item.headlines)
              ? item.headlines.filter((title) => typeof title === 'string' && title.trim()).slice(0, 3)
              : []
          }));
        })
        .catch(() => { savedUsError = true; })
        .finally(() => {
          savedUsPending = null;
          if (region === '해외' && tab === 'cap') showEmptyList();
        });
    }

    function showUsCapRows() {
      if (region !== '해외' || tab !== 'cap' || !list) return false;
      list.replaceChildren();
      if (!savedUsRows) {
        loadUsCapRows();
        const info = document.createElement('p');
        info.className = 'py-6 text-center text-[12px] text-[#64748b] dark:text-[#a1a1aa]';
        info.textContent = savedUsError ? '저장된 종목 목록을 읽지 못했습니다.' : '종목을 불러오는 중입니다.';
        list.appendChild(info);
        return true;
      }
      savedUsRows.forEach((row) => {
        const item = document.createElement('div');
        item.className = 'border-b border-[#e2e8f0] px-2 py-2 dark:border-[#3f3f46]';
        const name = document.createElement('p');
        name.className = 'text-[13px] font-semibold text-[#334155] dark:text-[#e4e4e7]';
        name.textContent = row.name;
        item.appendChild(name);
        row.headlines.forEach((headline) => {
          const title = document.createElement('p');
          title.className = 'mt-1 text-[12px] leading-5 text-[#64748b] dark:text-[#a1a1aa]';
          title.textContent = headline;
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
      if (showUsCapRows()) return;
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
    sidebar.dataset.marketControlsBound = 'true';
  }

  document.addEventListener('DOMContentLoaded', bindMarketControls);

  window.toggleLeftSidebar = toggle;
  window.GaemiGTPMarketSidebar = { toggle, bindMarketControls };
}());
