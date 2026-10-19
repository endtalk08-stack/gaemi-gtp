/* Fixed 40-company watchlist: names + already-stored AI issue titles only.
   Never fetch quotes, prices, rankings or start news/AI/disclosure collectors. */
(function () {
  'use strict';

  const endpoint = (location.hostname.endsWith('github.io')
    ? 'https://gaemi-gtp.onrender.com' : location.origin) + '/api/fixed-stocks';
  let stocks = [];
  let inFlight = null;

  function element(tag, text, className) {
    const el = document.createElement(tag);
    if (text !== undefined && text !== null) el.textContent = String(text);
    if (className) el.className = className;
    return el;
  }

  function issuesFor(row) {
    return Array.isArray(row.issues) ? row.issues.filter((item) =>
      item && typeof item.headline === 'string' && typeof item.summary === 'string'
    ).slice(0, 3) : [];
  }

  function openIssueBody(row, issueIndex = -1) {
    const chat = document.getElementById('chatArea');
    if (!chat) return;
    window.GaemiGTPCenterChatSearch?.enterChatWorkspace?.();
    let panel = document.getElementById('fixedStockIssuePanel');
    if (!panel) {
      panel = element('section', null, 'mx-auto my-5 max-w-3xl space-y-5 rounded-xl border border-[#cbd5e1] p-5 dark:border-[#3f3f46]');
      panel.id = 'fixedStockIssuePanel';
      chat.insertAdjacentElement('beforebegin', panel);
    }
    panel.replaceChildren();
    chat.style.display = 'none';
    const close = element('button', '← 대화로 돌아가기', 'text-sm text-[#64748b] dark:text-[#a1a1aa]');
    close.type = 'button';
    close.addEventListener('click', () => {
      panel.hidden = true;
      chat.style.display = '';
    });
    panel.appendChild(close);
    panel.appendChild(element('h2', row.name + ' · AI 뉴스 이슈',
      'text-lg font-semibold text-[#0f172a] dark:text-white'));
    const saved = issuesFor(row);
    const selected = issueIndex >= 0 ? saved.slice(issueIndex, issueIndex + 1) : saved;
    if (!selected.length) {
      panel.appendChild(element('p', '저장된 AI 뉴스 이슈가 없습니다.',
        'text-sm text-[#64748b] dark:text-[#a1a1aa]'));
    }
    selected.forEach((issue) => {
      const block = element('article', null, 'space-y-2 border-t border-[#e2e8f0] py-3 dark:border-[#3f3f46]');
      block.appendChild(element('h3', issue.headline,
        'font-semibold text-[#0f172a] dark:text-white'));
      block.appendChild(element('p', issue.summary,
        'whitespace-pre-wrap text-[14px] leading-7 text-[#334155] dark:text-[#d4d4d8]'));
      panel.appendChild(block);
    });
    panel.hidden = false;
    panel.scrollIntoView({ block: 'start', behavior: 'smooth' });
  }

  function renderList(root, { heading = true } = {}) {
    if (!root) return;
    root.replaceChildren();
    if (heading) root.appendChild(element('h2', '관심종목 · 시가총액 기준 40개',
      'px-2 py-2 text-[13px] font-bold text-[#334155] dark:text-[#d4d4d8]'));
    if (!stocks.length) {
      root.appendChild(element('p', '등록 종목을 불러오는 중',
        'px-2 py-4 text-[12px] text-[#64748b]'));
      return;
    }
    [['KR', '국내 20종목'], ['US', '미국 20종목']].forEach(([market, title]) => {
      root.appendChild(element('h3', title, 'px-2 pt-4 pb-2 text-[12px] font-semibold text-[#64748b] dark:text-[#a1a1aa]'));
      stocks.filter((row) => row.market === market).forEach((row) => {
        const entry = element('div', null, 'px-2 py-2 text-[13px] text-[#475569] dark:text-[#d4d4d8]');
        const stock = element('button', row.name, 'block w-full truncate text-left font-semibold');
        stock.type = 'button';
        stock.addEventListener('click', () => openIssueBody(row));
        entry.appendChild(stock);
        issuesFor(row).forEach((issue, index) => {
          const news = element('button', issue.headline,
            'mt-1 block w-full truncate text-left text-[12px] text-[#64748b] dark:text-[#a1a1aa]');
          news.type = 'button';
          news.title = issue.headline;
          news.addEventListener('click', () => openIssueBody(row, index));
          entry.appendChild(news);
        });
        root.appendChild(entry);
      });
    });
  }

  function refreshDisplay() {
    renderList(document.getElementById('leftContextContent'));
    renderList(document.getElementById('leftSidebarStocksBody'), { heading: false });
  }

  function initialize() {
    refreshDisplay();
    if (inFlight) return inFlight;
    inFlight = fetch(endpoint, { method: 'GET', credentials: 'same-origin' })
      .then((res) => {
        if (!res.ok) throw new Error('stocks_unavailable');
        return res.json();
      })
      .then((json) => {
        if (!json.ok || !Array.isArray(json.items) || json.items.length !== 40) {
          throw new Error('fixed_universe_incomplete');
        }
        const keys = new Set(json.items.map(r => r.market + ':' + r.symbol));
        if (keys.size !== 40) throw new Error('duplicate_universe_identity');
        stocks = json.items.map((r) => ({
          market: r.market, symbol: r.symbol, name: r.name, issues: r.issues
        }));
        refreshDisplay();
        window.dispatchEvent(new Event('gaemi:fixed-stocks-ready'));
        window.GaemiGTPSidebarHome?.renderRecent?.();
      })
      .catch(() => {
        for (const id of ['leftContextContent', 'leftSidebarStocksBody']) {
          const root = document.getElementById(id);
          if (root) root.replaceChildren(element('p', '관심종목 데이터를 불러오지 못했습니다.',
            'px-2 py-3 text-sm text-[#64748b]'));
        }
      })
      .finally(() => { inFlight = null; });
    return inFlight;
  }

  window.GaemiGTPWatchlist = {
    initialize, refresh: initialize, mount: initialize,
    getStocks: () => stocks.map(({ market, symbol, name }) => ({ market, symbol, name })),
    getDisplayRows: (market) => stocks.filter(row => row.market === market)
      .map(row => ({ market: row.market, symbol: row.symbol, name: row.name,
        issues: issuesFor(row).map(issue => ({ headline: issue.headline })) })),
    openSavedIssues: (market, symbol, issueIndex = -1) => {
      const row = stocks.find(item => item.market === market && item.symbol === symbol);
      if (row) openIssueBody(row, issueIndex);
    }
  };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize, { once: true });
  } else initialize();
}());
