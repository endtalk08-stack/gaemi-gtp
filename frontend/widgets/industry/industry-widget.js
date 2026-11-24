/* Portable industry widget. Existing market sidebar API, sorting and streaming are untouched. */
(function () {
  'use strict';

  const PLACEMENT_KEY = 'gaemiGTP_industry_widget_placement_v1';
  const MAP_URL = 'https://quotes.gaemigtp.com/market/us-industries?include_stocks=1&view=heatmap';
  const ETF_URL = 'https://quotes.gaemigtp.com/market/us-industry-etf-quotes';
  const REFRESH_MS = 20000;
  const MAP_TTL_MS = 60000;

  const SECTORS = [
    { key: 'information_technology', name: '정보기술', etf: 'XLK', sources: ['software', 'it_hardware', 'semiconductors'] },
    { key: 'healthcare', name: '헬스케어', etf: 'XLV', sources: ['healthcare', 'biotech'] },
    { key: 'finance', name: '금융', etf: 'XLF', sources: ['finance'] },
    { key: 'consumer_discretionary', name: '경기소비재', etf: 'XLY', sources: ['consumer_discretionary'] },
    { key: 'communication_services', name: '커뮤니케이션', etf: 'XLC', sources: ['communication', 'internet_platforms'] },
    { key: 'industrials', name: '산업재', etf: 'XLI', sources: ['industrials'] },
    { key: 'consumer_staples', name: '필수소비재', etf: 'XLP', sources: ['consumer_staples'] },
    { key: 'energy', name: '에너지', etf: 'XLE', sources: ['energy'] },
    { key: 'utilities', name: '유틸리티', etf: 'XLU', sources: ['utilities'] },
    { key: 'real_estate', name: '부동산', etf: 'XLRE', sources: ['real_estate'] },
    { key: 'materials', name: '소재', etf: 'XLB', sources: ['materials'] },
    { key: 'theme_semiconductors', name: '반도체', etf: 'SOXX', sources: ['semiconductors'] },
    { key: 'theme_biotech', name: '바이오', etf: 'XBI', sources: ['biotech'] },
    { key: 'theme_bitcoin', name: '비트코인', etf: 'IBIT', sources: ['bitcoin_related'] }
  ];

  const locations = ['left', 'center', 'right'];
  function savedPlacement() {
    try {
      const value = localStorage.getItem(PLACEMENT_KEY);
      return locations.includes(value) ? value : 'center';
    } catch (_) { return 'center'; }
  }

  let placement = savedPlacement();
  let widget = null;
  let rowsNode = null;
  let stateNode = null;
  let leftSlot = null;
  let originalMarketList = null;
  let leftTabObserver = null;
  let timer = null;
  let mapData = null;
  let mapFetchedAt = 0;
  let mapInFlight = null;
  let etfInFlight = null;
  let etfFetchedAt = 0;
  let fetchError = false;
  const etfRates = new Map();

  function installed() {
    return window.GaemiGTPWidgetDock?.isActive?.('industry') === true;
  }

  function normalizeSymbol(value) {
    return String(value || '').trim().toUpperCase().replace(/\.(?:O|N|K)$/, '');
  }

  function validPercent(value) {
    return typeof value === 'number' && Number.isFinite(value);
  }

  function percentage(value) {
    return validPercent(value) ? (value > 0 ? '+' : '') + value.toFixed(2) + '%' : '—';
  }

  function colorClass(value) {
    return !validPercent(value) ? 'giw-flat' : value > 0 ? 'giw-up' : value < 0 ? 'giw-down' : 'giw-flat';
  }

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function ensureWidget() {
    if (widget) return widget;
    widget = node('section', 'giw-widget');
    widget.setAttribute('aria-label', '미국 업종 ETF 위젯');
    const top = node('div', 'giw-header');
    const heading = node('div', 'giw-heading');
    heading.append(node('strong', '', '업종'), node('span', '', 'ETF 등락률 기준'));
    const moveControls = node('div', 'giw-move-controls');
    const names = { left: '왼쪽', center: '중앙', right: '오른쪽' };
    locations.forEach((where) => {
      const button = node('button', 'giw-move-button', names[where]);
      button.type = 'button';
      button.dataset.industryMove = where;
      button.title = names[where] + ' 패널로 이동';
      button.setAttribute('aria-label', names[where] + ' 패널로 이동');
      moveControls.append(button);
    });
    moveControls.addEventListener('click', (event) => {
      const button = event.target.closest('[data-industry-move]');
      if (button) move(button.dataset.industryMove);
    });
    top.append(heading, moveControls);
    stateNode = node('p', 'giw-state', '업종 데이터를 불러오는 중입니다');
    rowsNode = node('div', 'giw-rows');
    widget.append(top, stateNode, rowsNode);
    updateMoveButtons();
    return widget;
  }

  function updateMoveButtons() {
    if (!widget) return;
    widget.querySelectorAll('[data-industry-move]').forEach((button) => {
      const selected = button.dataset.industryMove === placement;
      button.setAttribute('aria-pressed', String(selected));
      button.disabled = selected;
    });
    widget.dataset.placement = placement;
  }

  function leftTabActive() {
    return document.querySelector('#leftMarketSidebar [data-info-tab-action="industry"]')
      ?.getAttribute('aria-pressed') === 'true';
  }

  function updateLeftVisibility() {
    if (!leftSlot || !originalMarketList) return;
    const show = installed() && placement === 'left' && leftTabActive();
    leftSlot.hidden = !show;
    originalMarketList.hidden = show;
  }

  function ensureLeftSlot() {
    if (leftSlot?.isConnected) return leftSlot;
    const originalList = document.getElementById('marketRankingList');
    if (!originalList || !originalList.parentElement) return null;
    originalMarketList = originalList.parentElement;
    leftSlot = node('div', 'giw-left-slot');
    leftSlot.id = 'industryWidgetLeftSlot';
    leftSlot.hidden = true;
    originalMarketList.before(leftSlot);
    const tabs = document.querySelectorAll('#leftMarketSidebar [data-info-tab-action]');
    if (!leftTabObserver && typeof MutationObserver === 'function') {
      leftTabObserver = new MutationObserver(updateLeftVisibility);
      tabs.forEach((button) => leftTabObserver.observe(button, {
        attributes: true, attributeFilter: ['aria-pressed']
      }));
    }
    tabs.forEach((button) => button.addEventListener('click', updateLeftVisibility));
    return leftSlot;
  }

  function centerTarget() {
    return document.querySelector('[data-industry-widget-target="center"]');
  }

  function centerCard() {
    return document.querySelector('[data-central-widget-id="industry"]');
  }

  function rightTarget() {
    return document.querySelector('[data-industry-widget-target="right"]');
  }

  function isVisible() {
    if (!installed() || document.hidden) return false;
    if (placement === 'left') return Boolean(leftSlot && !leftSlot.hidden && document.body.classList.contains('left-market-open'));
    if (placement === 'right') return Boolean(rightTarget() && document.body.classList.contains('right-panel-open'));
    return Boolean(centerCard() && !centerCard().hidden && widget?.isConnected);
  }

  function mountInChosenLocation() {
    const active = installed();
    const card = centerCard();
    if (card) card.hidden = !active || placement !== 'center';

    if (!active) {
      updateLeftVisibility();
      widget?.remove();
      if (timer) { clearInterval(timer); timer = null; }
      return;
    }

    ensureWidget();
    ensureLeftSlot();
    if (placement === 'left') {
      leftSlot?.appendChild(widget);
    } else if (placement === 'center') {
      centerTarget()?.appendChild(widget);
    } else if (rightTarget()) {
      rightTarget().appendChild(widget);
    }
    updateLeftVisibility();
    updateMoveButtons();
    if (!timer) timer = setInterval(() => { if (isVisible()) void refresh(); }, REFRESH_MS);
    if (isVisible()) void refresh();
  }

  function openLeftForWidget() {
    if (!document.body.classList.contains('left-market-open')) {
      window.GaemiGTPMarketSidebar?.toggle?.();
    }
    document.querySelector('#leftMarketSidebar [data-info-tab-action="industry"]')?.click();
    updateLeftVisibility();
  }

  function openRightForWidget() {
    document.body.classList.add('right-panel-open');
    window.GaemiGTPWorkspaceShellState?.apply?.();
    window.GaemiGTPRightPanelTabs?.selectPanelWorkspaceView?.('industry');
  }

  function move(where) {
    if (!locations.includes(where) || !installed() || where === placement) return;
    const fromRightVisible = Boolean(widget?.closest('#rightPanel'));
    placement = where;
    try { localStorage.setItem(PLACEMENT_KEY, placement); } catch (_) {}
    if (where === 'left') openLeftForWidget();
    if (where === 'right') openRightForWidget();
    mountInChosenLocation();
    if (fromRightVisible && where !== 'right') {
      window.GaemiGTPRightPanelTabs?.selectPanelWorkspaceView?.('panel-workspace');
    }
  }

  function mountRight(target) {
    if (!target) return;
    if (!installed()) {
      target.replaceChildren(node('p', 'giw-state', '플러그인에서 업종 위젯을 추가하면 이곳에 배치할 수 있습니다.'));
      return;
    }
    if (placement === 'right') {
      target.replaceChildren(ensureWidget());
      updateMoveButtons();
      if (isVisible()) void refresh();
    } else {
      target.replaceChildren(node('p', 'giw-state', '업종 위젯은 현재 다른 위치에 있습니다.'));
    }
  }

  function sortedStocks(sources, sectorKey) {
    const rows = sources.flatMap((source) => Array.isArray(source?.stocks) ? source.stocks : []);
    const unique = new Set();
    const candidates = rows
      .filter((stock) => stock && typeof stock.name === 'string' && stock.name.trim())
      .sort((a, b) => (Number(b.market_cap_usd) || 0) - (Number(a.market_cap_usd) || 0))
      .filter((stock) => {
        const ticker = normalizeSymbol(stock.symbol);
        const key = stock.issuer_key || (ticker === 'GOOG' || ticker === 'GOOGL'
          ? 'US:ALPHABET' : ticker === 'BRK.A' || ticker === 'BRK.B' ? 'US:BERKSHIRE' : ticker);
        if (!key || unique.has(key)) return false;
        if (sectorKey === 'information_technology' && ticker === 'NVDA') return false;
        if (sectorKey === 'theme_biotech' && ticker === 'ABBV') return false;
        unique.add(key);
        return true;
      });
    return candidates.slice(0, 3).sort((a, b) =>
      (validPercent(b.change_pct) ? b.change_pct : -Infinity)
      - (validPercent(a.change_pct) ? a.change_pct : -Infinity));
  }

  function render() {
    if (!rowsNode || !stateNode) return;
    if (!Array.isArray(mapData?.items)) {
      stateNode.textContent = fetchError ? '업종 데이터 연결을 확인하고 있습니다' : '업종 데이터를 불러오는 중입니다';
      rowsNode.replaceChildren();
      return;
    }
    const byKey = new Map(mapData.items.filter((row) => row && typeof row.key === 'string')
      .map((row) => [row.key, row]));
    const rows = SECTORS.map((definition) => {
      const sources = definition.sources.map((key) => byKey.get(key)).filter(Boolean);
      const rate = etfRates.get(definition.etf);
      return {
        ...definition,
        change: rate && validPercent(rate.change_pct) ? rate.change_pct : null,
        stocks: sortedStocks(sources, definition.key)
      };
    }).sort((a, b) =>
      (validPercent(b.change) ? b.change : -Infinity) -
      (validPercent(a.change) ? a.change : -Infinity));

    const fragment = document.createDocumentFragment();
    rows.forEach((row) => {
      const line = node('div', 'giw-row');
      const sector = node('div', 'giw-sector ' + colorClass(row.change));
      const title = node('span', 'giw-sector-name', row.name);
      const ticker = node('span', 'giw-sector-ticker', row.etf);
      const change = node('span', 'giw-change', percentage(row.change));
      sector.append(title, ticker, change);
      line.append(sector);
      const stocks = node('div', 'giw-stocks');
      if (!row.stocks.length) {
        stocks.append(node('div', 'giw-empty', '상위 종목 데이터 없음'));
      } else {
        row.stocks.forEach((stock) => {
          const pct = validPercent(stock.change_pct) ? stock.change_pct : null;
          const button = node('button', 'giw-stock ' + colorClass(pct));
          button.type = 'button';
          button.append(node('span', 'giw-stock-name', stock.name),
            node('span', 'giw-stock-change', percentage(pct)));
          button.addEventListener('click', () => {
            window.openStockInChat?.(stock.name, {
              market: 'us', menu: 'industry', name: stock.name, symbol: stock.symbol,
              rank: stock.rank, industry: row.name, change_pct: pct,
              currency: 'USD', source: 'kiwoom'
            });
          });
          stocks.append(button);
        });
      }
      line.append(stocks);
      fragment.append(line);
    });
    rowsNode.replaceChildren(fragment);
    stateNode.textContent = fetchError
      ? '일부 데이터 연결 지연 · 마지막으로 확인된 값 표시'
      : '미국 업종 11개 · 보조 업종 3개';
  }

  async function refreshMap() {
    if (mapInFlight || mapData && Date.now() - mapFetchedAt < MAP_TTL_MS) return;
    mapInFlight = (async () => {
      const response = await fetch(MAP_URL, { cache: 'no-store', signal: AbortSignal.timeout(10000) });
      if (!response.ok) throw new Error('industry_map_http_' + response.status);
      const data = await response.json();
      if (data?.ok !== true || !Array.isArray(data.items)) throw new Error('invalid_industry_map');
      mapData = data;
      mapFetchedAt = Date.now();
      render();
    })();
    try {
      await mapInFlight;
    } catch (_) { fetchError = true; render(); }
    finally { mapInFlight = null; }
  }

  async function refreshEtfs() {
    if (etfInFlight || Date.now() - etfFetchedAt < REFRESH_MS) return;
    etfInFlight = (async () => {
      const response = await fetch(ETF_URL, { cache: 'no-store', signal: AbortSignal.timeout(10000) });
      if (!response.ok) throw new Error('industry_etf_http_' + response.status);
      const data = await response.json();
      if (data?.ok !== true || !Array.isArray(data.items)) throw new Error('invalid_industry_etf');
      for (const quote of data.items) {
        const symbol = normalizeSymbol(quote?.symbol);
        if (!symbol || quote.stale === true || !validPercent(quote.change_pct)) continue;
        const prior = etfRates.get(symbol);
        if (Number.isFinite(prior?.received_at_ms) && Number.isFinite(quote.received_at_ms)
          && quote.received_at_ms < prior.received_at_ms) continue;
        etfRates.set(symbol, quote);
      }
      etfFetchedAt = Date.now();
      render();
    })();
    try {
      await etfInFlight;
    } catch (_) { fetchError = true; render(); }
    finally { etfInFlight = null; }
  }

  async function refresh() {
    if (!isVisible()) return;
    fetchError = false;
    await Promise.all([refreshMap(), refreshEtfs()]);
    render();
  }

  function mount() {
    mountInChosenLocation();
    if (installed() && placement === 'right' && !rightTarget()) {
      window.GaemiGTPRightPanelTabs?.selectPanelWorkspaceView?.('industry');
    }
    if (installed() && placement === 'right' && rightTarget()) {
      mountRight(rightTarget());
    }
  }

  window.GaemiGTPIndustryWidget = {
    mount, mountRight, move,
    getPlacement: () => placement
  };
}());
