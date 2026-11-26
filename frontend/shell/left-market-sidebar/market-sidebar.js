/* Left Market Sidebar — US-only rankings and shell controls. */
(function () {
  'use strict';

  // The ranking API already registers source ticker/name pairs into Neon.
  // Key the mark only by the returned ticker, never by a handwritten name map.
  function canonicalMarkTicker(symbol) {
    const ticker = String(symbol || '').trim().toUpperCase()
      .replace(/^US:/, '').replace(/\.(?:O|N|K)$/, '');
    return /^[A-Z0-9]+(?:\.[A-Z])?$/.test(ticker) ? ticker : '';
  }

  function stockMark(item) {
    const ticker = canonicalMarkTicker(item.symbol);
    const mark = document.createElement('span');
    mark.className = 'market-stock-logo';
    mark.title = ticker ? ticker + ' 종목 마크' : '종목 마크';
    const fallback = document.createElement('span');
    fallback.className = 'market-stock-logo-fallback';
    fallback.textContent = ticker ? (ticker.length <= 6 ? ticker : ticker.slice(0, 6) + '…')
      : String(item.name || '?').slice(0, 2);
    if (ticker.length > 4) fallback.style.fontSize = '8px';
    mark.appendChild(fallback);

    // Previously bundled vector artwork is reused automatically by ticker.
    // Every other registered or newly observed ticker gets its own badge,
    // instead of accidentally displaying another company's logo.
    const verified = item.identity_status === 'verified'
      && canonicalMarkTicker(item.mark_ticker) === ticker
      && Boolean(ticker);
    const icon = verified && window.GaemiGTPStockMarks?.[ticker];
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
    }

    // Logo lookup is separate from verified *news* matching. The API provides
    // a source-symbol logo candidate even for a newly listed, still-pending
    // company, but never for a conflicting known ticker/name combination.
    // The returned candidate must match the row's own normalized symbol.
    const logoTicker = canonicalMarkTicker(item.logo_lookup_ticker);
    const canLookupLogo = verified || (
      item.identity_status === 'pending' && Boolean(ticker) && logoTicker === ticker
    );
    // Keep the bundled vector or ticker badge while the request is in flight.
    if (canLookupLogo) {
      const logo = document.createElement('img');
      logo.className = 'market-stock-logo-image';
      logo.alt = '';
      logo.decoding = 'async';
      // Detached lazy images may never load. Only active ranking rows create one.
      logo.loading = 'eager';
      logo.referrerPolicy = 'no-referrer';
      logo.addEventListener('load', () => {
        if (logo.naturalWidth > 0) mark.replaceChildren(logo);
      });
      // A 404, rate limit, or network failure leaves the local/ticker mark.
      logo.addEventListener('error', () => {});
      logo.src = 'https://img.anylogo.dev/ticker/'
        + encodeURIComponent(ticker) + '?size=64&variant=icon';
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
    // A newly opened panel must show the latest quote immediately.
    if (!isOpen) window.GaemiGTPMarketSidebar?.refreshLiveQuotes?.();
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
    // Ranking rows and the portable industry map are separate; only the map node moves between panels.
    const industryMapElement = sidebar.querySelector('#marketIndustryMap');
    const industrySlot = sidebar.querySelector('#marketIndustryWidgetSlot');
    const rankingSection = list?.parentElement;
    const title = sidebar.querySelector('#rightListTitle');
    const asOfBadge = sidebar.querySelector('#rightListAsOf');
    const changeSortButton = sidebar.querySelector('#rightListMetric');
    const backendUrl = window.location.hostname.endsWith('github.io')
      || window.location.hostname === 'gaemigtp-main.pages.dev'
      ? 'https://gaemi-gtp.onrender.com' : window.location.origin;
    const market = 'us';
    let tab = 'value';
    const syncIndustryTabLayout = () => {
      const mapInLeftSlot = Boolean(industrySlot && industryMapElement
        && industrySlot.contains(industryMapElement));
      if (industrySlot) industrySlot.hidden = tab !== 'industry' || !mapInLeftSlot;
      if (rankingSection) {
        rankingSection.hidden = tab === 'industry';
        rankingSection.style.display = tab === 'industry' ? 'none' : '';
      }
    };
    const industryViewActive = () => document.visibilityState === 'visible'
      && Boolean(industryMapElement?.isConnected && industryMapElement.getClientRects().length);
    let requestId = 0;
    let changeSorted = false;
    let draggedRow = null;
    let lastRankingSignature = '';
    let cachedRankingRows = [];
    let cachedRankingAsOf = '';
    let marketQqqQuote = null;
    // 'YYYY-MM-DD' -> '11월 25일 종가 기준'. Never throws on an odd/missing date.
    const asOfLabel = (dateStr) => {
      if (typeof dateStr !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) return '';
      const [, month, day] = dateStr.split('-');
      return `${Number(month)}월 ${Number(day)}일 종가 기준`;
    };
    // Most-common reference_close_date among a batch of quote/row objects --
    // a handful of symbols can lag one session behind the rest.
    const mostCommonCloseDate = (rows) => {
      const counts = new Map();
      for (const row of rows || []) {
        const date = row?.reference_close_date;
        if (typeof date !== 'string' || !date) continue;
        counts.set(date, (counts.get(date) || 0) + 1);
      }
      let best = '';
      let bestCount = 0;
      for (const [date, count] of counts) {
        if (count > bestCount) { best = date; bestCount = count; }
      }
      return best;
    };
    const industryBySymbol = new Map();
    const rankingIndustryBySymbol = new Map();
    let industryPromise = null;
    let nextIndustryReadAt = 0;
    const industryFor = (symbol, exchange, fallback = '') => {
      const suffix = exchange === 'ND' ? '.O' : exchange === 'NY' ? '.K' : '';
      return industryBySymbol.get(symbol)
        || (suffix && !symbol.includes('.') && industryBySymbol.get(symbol + suffix))
        || fallback || rankingIndustryBySymbol.get(symbol) || '';
    };
    const applyIndustryLabels = () => {
      list?.querySelectorAll(':scope > button[data-original-index]')?.forEach((button) => {
        const label = button.querySelector('[data-market-industry]');
        if (!label) return;
        const industry = industryFor(button.dataset.stockSymbol, button.dataset.stockExchange, label.textContent);
        if (industry) label.textContent = industry;
      });
    };
    const loadIndustryLabels = () => {
      if (industryPromise || Date.now() < nextIndustryReadAt) return industryPromise;
      nextIndustryReadAt = Date.now() + 300000;
      industryPromise = fetch('/stocks/us/instruments.json', { cache: 'default' })
        .then((response) => {
          if (!response.ok) throw new Error('industry R2 unavailable');
          return response.json();
        })
        .then((data) => {
          if (!Array.isArray(data?.items)) throw new Error('invalid industry metadata');
          for (const item of data.items) {
            if (typeof item?.symbol === 'string' && typeof item?.industry === 'string' && item.industry.trim()) {
              industryBySymbol.set(item.symbol, item.industry.trim());
            }
          }
          applyIndustryLabels();
        })
        .catch(() => { nextIndustryReadAt = Date.now() + 60000; })
        .finally(() => { industryPromise = null; });
      return industryPromise;
    };
    const quoteApiBase = 'https://quotes.gaemigtp.com';
    const mapCacheTtl = 60000;
    let industryMapData = null;
    let industryMapFetchedAt = 0;
    let industryMapPromise = null;
    let industryWarmupRetryScheduled = false;
    let industryLiveQuotes = [];
    let industryRestQuotes = [];
    const industryLastVerifiedQuotes = new Map();
    const industryEtfSymbols = new Set([
      'XLK', 'XLV', 'XLF', 'XLY', 'XLC', 'XLI', 'XLP',
      'XLE', 'XLU', 'XLRE', 'XLB', 'SOXX', 'XBI', 'IBIT'
    ]);
    // Last displayed change-% text per sector/stock, so a re-render can tell
    // whether the printed number actually moved and flash the badge only then
    // (not on every 20s/websocket re-render when nothing changed).
    const industryFlashSectorPrev = new Map();
    const industryFlashStockPrev = new Map();
    const flashClassFor = (tone) => tone === 'is-up' ? 'flash-up' : tone === 'is-down' ? 'flash-down' : 'flash-flat';
    const industrySymbol = (symbol) => String(symbol || '').trim().toUpperCase().replace(/\.(?:O|N|K)$/, '');
    // Keep one last valid quote per ETF, including quiet/stale WebSocket
    // snapshots. A subscribed ticker may have no new trade for hours.
    const rememberIndustryEtfQuotes = (items, source) => {
      if (!Array.isArray(items)) return;
      const now = Date.now();
      items.forEach((quote) => {
        const symbol = industrySymbol(quote?.symbol);
        // A stale-only first packet is not a verified last-good value.
        // If a prior value exists, leave it untouched when the feed marks it stale.
        if (quote?.stale === true) return;
        if (!industryEtfSymbols.has(symbol)
            || !Number.isFinite(quote?.price) || quote.price <= 0
            || !Number.isFinite(quote?.change_pct)
            || !Number.isFinite(quote?.received_at_ms)
            || quote.received_at_ms > now + 5000
            || now - quote.received_at_ms > 72 * 60 * 60 * 1000) return;
        const previous = industryLastVerifiedQuotes.get(symbol);
        const fromWebSocket = source === 'websocket';
        // A fresh REST snapshot must not override a confirmed live FE rate.
        // After a day, allow a newer REST close to replace an older session.
        if (previous?.fromWebSocket && !fromWebSocket
            && now - previous.received_at_ms < 24 * 60 * 60 * 1000) return;
        if (previous?.fromWebSocket === fromWebSocket
            && previous.received_at_ms > quote.received_at_ms) return;
        industryLastVerifiedQuotes.set(symbol, { ...quote, fromWebSocket });
      });
    };
    const industryQuoteFor = (symbol) => {
      const now = Date.now();
      const key = industrySymbol(symbol);
      const live = industryLiveQuotes.find((quote) =>
        industrySymbol(quote.symbol) === key && freshQuote(quote, now)
        && Number.isFinite(quote.change_pct));
      if (live) return live;
      // A quiet ETF/stock keeps its last verified return for the rest of this
      // close session -- no 30-minute expiry. The Kiwoom feed is genuinely
      // subscribed (confirmed: all 14 sector ETFs register successfully on
      // startup); a thin pre-market sector just not trading again for a
      // while doesn't mean its last known move stopped being true. Only a
      // new tick (live, above) or a new session (reference_close_date
      // changing) should replace it -- never just the clock running out.
      const retained = industryLastVerifiedQuotes.get(key);
      const referenceDate = marketQqqQuote?.reference_close_date;
      if (retained && (!referenceDate || !retained.reference_close_date || retained.reference_close_date === referenceDate)) return retained;
      return industryRestQuotes.find((quote) =>
        industrySymbol(quote.symbol) === key
        && Number.isFinite(quote.change_pct)
        && Number.isFinite(quote.received_at_ms)
        && quote.received_at_ms <= now + 5000
        && now - quote.received_at_ms <= 72 * 60 * 60 * 1000);
    };
    // Refresh ETF percentages without reloading the slow stock/industry membership map.
    let nextEtfRateRefreshAt = 0;
    let etfRateRefreshInFlight = false;
    const refreshIndustryEtfRates = async () => {
      if (!industryViewActive()
          || etfRateRefreshInFlight || Date.now() < nextEtfRateRefreshAt) return;
      nextEtfRateRefreshAt = Date.now() + 20000;
      etfRateRefreshInFlight = true;
      try {
        const response = await fetch(quoteApiBase + '/market/us-industry-etf-quotes', {
          cache: 'no-store'
        });
        if (!response.ok) throw new Error('industry_etf_rates_unavailable');
        const data = await response.json();
        const etfItems = Array.isArray(data?.items)
          ? data.items.filter((quote) => industryEtfSymbols.has(industrySymbol(quote?.symbol))) : [];
        if (data?.ok !== true || !etfItems.length) throw new Error('invalid_industry_etf_rates');
        // Partial responses update only valid ETFs. Keep the last rate for absent ETFs.
        if (!industryViewActive()) return;
        rememberIndustryEtfQuotes(etfItems, 'rest');
        industryRestQuotes = etfItems;
        if (industryMapData) {
          industryMapData = { ...industryMapData, etf_quotes: etfItems };
          renderIndustryMap(industryMapData);
        }
      } catch (_) {
        nextEtfRateRefreshAt = Date.now() + 10000;
      } finally {
        etfRateRefreshInFlight = false;
      }
    };
    const formatChange = (value) => Number.isFinite(value)
      ? (value > 0 ? '+' : '') + value.toFixed(2) + '%' : '—';
    // One fixed shade per direction -- not scaled by how big the move is --
    // so every up tile matches every other up tile, every down tile matches
    // every other down tile, and the only other difference is the sector
    // boost applied separately below.
    const mapTileColor = (value) => {
      // Match the trading-value list: the tile surface stays charcoal;
      // only the percentage text carries direction color.
      if (!Number.isFinite(value) || Math.abs(value) < 0.005) return { tone: 'is-flat' };
      return value > 0 ? { tone: 'is-up' } : { tone: 'is-down' };
    };
    const renderIndustryMapFor = (data, list) => {
      const items = Array.isArray(data?.items) ? data.items : [];
      // A real DOM child here would shift every :nth-child row-sizing rule
      // below, so the label is a CSS-rendered attribute, not an extra row.
      const mapAsOf = asOfLabel(mostCommonCloseDate(data?.etf_quotes));
      if (mapAsOf) list.dataset.asOf = mapAsOf;
      else delete list.dataset.asOf;
      if (Array.isArray(data?.etf_quotes) && data.etf_quotes.length) {
        rememberIndustryEtfQuotes(data.etf_quotes, 'rest');
        industryRestQuotes = data.etf_quotes;
      }
      // Select companies by market cap first; order only the selected three by return.
      const orderSelectedStocks = (stocks) => [...stocks].sort((a, b) => {
        const rise = (stock) => {
          const live = industryQuoteFor(stock.symbol);
          return Number.isFinite(live?.change_pct) ? live.change_pct
            : Number.isFinite(stock.change_pct) ? stock.change_pct : -Infinity;
        };
        return rise(b) - rise(a) || (b.market_cap_usd || 0) - (a.market_cap_usd || 0);
      });
      const sectorEtfs = {
        information_technology: 'XLK', healthcare: 'XLV', finance: 'XLF',
        consumer_discretionary: 'XLY', communication_services: 'XLC',
        industrials: 'XLI', consumer_staples: 'XLP', energy: 'XLE',
        utilities: 'XLU', real_estate: 'XLRE', materials: 'XLB',
        theme_semiconductors: 'SOXX', theme_biotech: 'XBI', theme_bitcoin: 'IBIT'
      };
      list.classList?.add?.('industry-map-list');
      list.replaceChildren();
      // Present the agreed 11 GICS sectors. Merge existing Kiwoom subgroups
      // into Information Technology and Communication Services without changing the API.
      const expectedIndustries = [
        { key: 'information_technology', name: '정보기술', sourceKeys: ['software', 'it_hardware', 'semiconductors'] },
        { key: 'healthcare', name: '헬스케어', sourceKeys: ['healthcare', 'biotech'] },
        { key: 'finance', name: '금융', sourceKeys: ['finance'] },
        { key: 'consumer_discretionary', name: '경기소비재', sourceKeys: ['consumer_discretionary'] },
        { key: 'communication_services', name: '커뮤니케이션', sourceKeys: ['communication', 'internet_platforms'] },
        { key: 'industrials', name: '산업재', sourceKeys: ['industrials'] },
        { key: 'consumer_staples', name: '필수소비재', sourceKeys: ['consumer_staples'] },
        { key: 'energy', name: '에너지', sourceKeys: ['energy'] },
        { key: 'utilities', name: '유틸리티', sourceKeys: ['utilities'], themeTone: 'utilities' },
        { key: 'real_estate', name: '부동산', sourceKeys: ['real_estate'], themeTone: 'realestate' },
        { key: 'materials', name: '소재', sourceKeys: ['materials'], themeTone: 'materials' }
      ];
      const byIndustry = new Map(items
        .filter((sector) => sector && typeof sector.key === 'string')
        .map((sector) => [sector.key, sector]));
      const visibleSectors = expectedIndustries.map(({ key, name, sourceKeys, themeTone }) => {
        const sources = sourceKeys.map((sourceKey) => byIndustry.get(sourceKey)).filter(Boolean);
        const sourceStocks = sources.flatMap((source) =>
          Array.isArray(source.stocks) ? source.stocks : []);
        const seenIssuers = new Set();
        const candidates = sourceStocks.sort((a, b) => (b.market_cap_usd || 0) - (a.market_cap_usd || 0)).filter((stock) => {
          if (!stock || typeof stock.name !== 'string' || !stock.name.trim()) return false;
          const symbolKey = String(stock.symbol || stock.name).trim().toUpperCase().replace(/\.(?:O|N|K)$/, '');
          const issuerKey = stock.issuer_key || (['GOOG', 'GOOGL'].includes(symbolKey) ? 'US:ALPHABET'
            : ['BRK.A', 'BRK.B'].includes(symbolKey) ? 'US:BERKSHIRE' : symbolKey);
          if (key === 'information_technology' && symbolKey === 'NVDA') return false;
          if (seenIssuers.has(issuerKey)) return false;
          seenIssuers.add(issuerKey);
          return true;
        });
        const stocks = candidates.slice(0, 3);
        if (key === 'information_technology') {
          const anthropic = candidates.find((stock) => industrySymbol(stock.symbol) === 'ANT');
          if (anthropic && !stocks.includes(anthropic)) stocks.splice(2, 1, anthropic);
        }
        const changes = sources.map((source) => source.change_pct).filter(Number.isFinite);
        const changePct = changes.length
          ? changes.reduce((total, value) => total + value, 0) / changes.length : null;
        return {
          sector: {
            key, name, change_pct: changePct,
            hideChange: changes.length === 0,
            ...(themeTone ? { themeTone } : {})
          },
          stocks: orderSelectedStocks(stocks)
        };
      });
      const supplementalThemes = [
        {
          sector: { key: 'theme_semiconductors', name: '반도체', themeTone: 'semiconductor', hideChange: true },
          stocks: orderSelectedStocks([...(byIndustry.get('semiconductors')?.stocks || [])]
            .sort((a, b) => (b.market_cap_usd || 0) - (a.market_cap_usd || 0)).slice(0, 3))
        },
        {
          sector: { key: 'theme_biotech', name: '바이오', themeTone: 'biotech', hideChange: true },
          stocks: orderSelectedStocks([...(byIndustry.get('biotech')?.stocks || [])]
            .filter((stock) => industrySymbol(stock.symbol) !== 'ABBV')
            .sort((a, b) => (b.market_cap_usd || 0) - (a.market_cap_usd || 0)).slice(0, 3))
        },
        {
          sector: { key: 'theme_bitcoin', name: '비트코인', themeTone: 'bitcoin', hideChange: true },
          stocks: orderSelectedStocks([...(byIndustry.get('bitcoin_related')?.stocks || [])]
            .sort((a, b) => (b.market_cap_usd || 0) - (a.market_cap_usd || 0)).slice(0, 3))
        }
      ];
      const etfChange = ({ sector }) => {
        const quote = industryQuoteFor(sectorEtfs[sector.key]);
        return Number.isFinite(quote?.change_pct) ? quote.change_pct : -Infinity;
      };
      [...visibleSectors, ...supplementalThemes].sort((a, b) => {
        const left = etfChange(a);
        const right = etfChange(b);
        return left === right ? 0 : right - left;
      }).forEach(({ sector, stocks: ranked }, index) => {
        const etf = sectorEtfs[sector.key];
        const etfQuote = industryQuoteFor(etf);
        const sectorPct = etfQuote && Number.isFinite(etfQuote.change_pct) ? etfQuote.change_pct : null;
        // Sector and stock tiles share the trading-value charcoal surface.
        // Direction is shown by the percentage text; only actual changes flash.
        const sectorColor = mapTileColor(sectorPct);
        const row = document.createElement('div');
        row.className = 'industry-map-row';
        const heading = document.createElement('div');
        heading.className = 'industry-map-sector ' + sectorColor.tone
          + (sector.themeTone ? ' industry-map-sector-theme' : '');
        if (index === 0) {
          heading.dataset.widgetDragHandle = 'industry';
          heading.setAttribute('aria-label', `${sector.name} 박스를 끌어 위젯 이동`);
        }
        const label = document.createElement('span');
        label.className = 'industry-map-sector-name';
        label.textContent = String(sector.name || '업종');
        label.title = label.textContent;
        const change = document.createElement('span');
        change.className = 'industry-map-sector-change';
        const sectorChangeText = formatChange(sectorPct);
        change.textContent = sectorChangeText;
        const prevSectorChangeText = industryFlashSectorPrev.get(sector.key);
        if (prevSectorChangeText !== undefined && sectorChangeText !== '—'
            && sectorChangeText !== prevSectorChangeText) {
          // Briefly flash the tile in the direction color, then return to charcoal.
          heading.classList.add(flashClassFor(sectorColor.tone));
        }
        industryFlashSectorPrev.set(sector.key, sectorChangeText);
        heading.append(label, change);
        const stocks = document.createElement('div');
        stocks.className = 'industry-map-stocks';
        if (!ranked.length) {
          const empty = document.createElement('div');
          empty.className = 'industry-map-empty';
          empty.textContent = '상위 종목 데이터 없음';
          stocks.appendChild(empty);
        }
        ranked.forEach((stock) => {
          const live = industryQuoteFor(stock.symbol);
          const pct = live && Number.isFinite(live.change_pct) ? live.change_pct
            : stock.hideChange ? null : Number.isFinite(stock.change_pct) ? stock.change_pct : null;
          const color = mapTileColor(pct);
          const stockTile = document.createElement('button');
          stockTile.type = 'button';
          stockTile.className = 'industry-map-stock ' + color.tone
            + (stock.themeTone ? ' industry-map-stock-theme' : '');
          stockTile.title = stock.name + (stock.hideChange ? '' : ' ' + formatChange(pct));
          stockTile.dataset.industrySymbol = industrySymbol(stock.symbol);
          const name = document.createElement('span');
          name.className = 'industry-map-stock-name';
          name.textContent = stock.name;
          stockTile.append(name);
          if (stock.hideChange !== true || live) {
            const stockChange = document.createElement('span');
            stockChange.className = 'industry-map-stock-change';
            const stockChangeText = formatChange(pct);
            stockChange.textContent = stockChangeText;
            const stockFlashKey = industrySymbol(stock.symbol);
            const prevStockChangeText = industryFlashStockPrev.get(stockFlashKey);
            if (prevStockChangeText !== undefined && stockChangeText !== '—'
                && stockChangeText !== prevStockChangeText) {
              // Briefly flash the tile in the direction color, then return to charcoal.
              stockTile.classList.add(flashClassFor(color.tone));
            }
            industryFlashStockPrev.set(stockFlashKey, stockChangeText);
            stockTile.append(stockChange);
          }
          stockTile.addEventListener('click', () => {
            window.openStockInChat?.(stock.name, {
              market: 'us',
              menu: 'industry',
              name: stock.name,
              symbol: stock.symbol,
              rank: stock.rank,
              industry: sector.name,
              change_pct: pct,
              currency: 'USD',
              source: 'kiwoom'
            });
          });
          stocks.appendChild(stockTile);
        });
        row.append(heading, stocks);
        list.appendChild(row);
      });
    };
    const renderIndustryMap = (data) => {
      if (industryMapElement) renderIndustryMapFor(data, industryMapElement);
      syncIndustryTabLayout();
    };
    const loadIndustryMap = async (id) => {
      if (industryMapData && id === requestId) renderIndustryMap(industryMapData);
      if (industryMapData && Date.now() - industryMapFetchedAt < mapCacheTtl) return;
      if (industryMapPromise) {
        try {
          const data = await industryMapPromise;
          if (id === requestId && data) renderIndustryMap(data);
        } catch (_) {}
        return;
      }
      if (industryMapElement) industryMapElement.classList?.add?.('industry-map-list');
      industryMapPromise = (async () => {
        // Industry membership and market-cap ranking come from the existing
        // DigitalOcean Kiwoom industry endpoint. Never derive this map from TOP20.
        const response = await fetch(quoteApiBase + '/market/us-industries?include_stocks=1&view=heatmap', {
          cache: 'no-store'
        });
        if (!response.ok) throw new Error('us_industries_http_' + response.status);
        const data = await response.json();
        if (data?.ok !== true || !Array.isArray(data.items)) {
          throw new Error('invalid_us_industry_marketcap');
        }
        industryMapData = data;
        industryMapFetchedAt = Date.now();
        return data;
      })();
      try {
        const data = await industryMapPromise;
        if (id === requestId) renderIndustryMap(data);
        // The Kiwoom prices arrive with the map; only the once-a-day close
        // lookups may still be finishing. Reuse the same map endpoint once.
        if (!industryWarmupRetryScheduled && data?.items?.some(sector =>
            sector?.stocks?.some(stock => !Number.isFinite(stock?.change_pct)))) {
          industryWarmupRetryScheduled = true;
          window.setTimeout(() => {
            if (!industryViewActive()) return;
            industryMapFetchedAt = 0;
            void loadIndustryMap(requestId);
          }, 10000);
        }
      } catch (_) {
        // Keep the sidebar free of transient loading/error copy.
      } finally {
        industryMapPromise = null;
      }
    };
    let nextRankingReadAt = 0;
    let rankingRequestInFlight = false;
    let rankingFailureCount = 0;
    const sidebarActive = () => document.visibilityState === 'visible'
      && (document.body.classList.contains('left-market-open')
        || (document.body.classList.contains('left-home-open')
          && sidebar.parentElement?.id === 'leftSidebarHomeSectionContent'))
      && !(window.innerWidth < 1024 && document.body.classList.contains('right-panel-open'));
    const orderKey = () => 'gaemiGTP_market_sidebar_order_us_' + tab + '_v1';
    const readOrder = () => {
      try {
        const value = JSON.parse(localStorage.getItem(orderKey()) || '[]');
        return Array.isArray(value) ? value.filter((item) => typeof item === 'string').slice(0, 100) : [];
      } catch (_) { return []; }
    };
    let customOrder = []; // Trading-value ranking starts in current source order.
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

    const sidebarIssueTitle = (value) =>
      typeof value === 'string' ? value.split(/…|\.{3,}/, 1)[0].trim() : '';

    const showUsRanking = async () => {
      if (!sidebarActive()) return;
      if (!list) return;
      const id = ++requestId;
      const titles = {
        realtime: '',
        industry: '',
        value: '거래대금 TOP 20',
      };
      if (!Object.prototype.hasOwnProperty.call(titles, tab)) return;
      const headerRow = sidebar.querySelector('#rightListHeaderRow');
      if (headerRow) {
        const showListHeading = tab === 'value';
        headerRow.hidden = !showListHeading;
        headerRow.style.display = showListHeading ? '' : 'none';
      }
      if (title) title.textContent = titles[tab];
      if (changeSortButton) changeSortButton.hidden = tab !== 'value';
      if (tab !== 'value') {
        const displayedRows = [...list.querySelectorAll(':scope > button[data-original-index]')];
        if (displayedRows.length) cachedRankingRows = displayedRows;
        list.replaceChildren();
      } else if (!list.querySelectorAll(':scope > button[data-original-index]').length && cachedRankingRows.length) {
        // Restore last verified TOP20 immediately without an extra Neon read.
        list.replaceChildren(...cachedRankingRows);
        applyChangeSort();
        if (asOfBadge) {
          asOfBadge.textContent = cachedRankingAsOf;
          asOfBadge.hidden = !cachedRankingAsOf;
        }
      }
      syncIndustryTabLayout();
      if (tab === 'realtime') {
        // QQQ is a plugin-only live quote card, not a duplicate market-row.
        list.replaceChildren();
        return;
      }
      if (tab === 'industry') {
        syncQqqSocket();
        await loadIndustryMap(id);
        void refreshIndustryEtfRates();
        return;
      }
      if (tab !== 'value') return;
      if (rankingRequestInFlight || Date.now() < nextRankingReadAt) return;
      rankingRequestInFlight = true;
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), 10000);
      nextRankingReadAt = Date.now() + 15000;
      try {
        const response = await fetch('https://quotes.gaemigtp.com/market/trading-value?market=us', { cache: 'no-store', signal: controller.signal });
        if (!response.ok) throw new Error(`TOP20 HTTP ${response.status}`);
        const result = await response.json();
        if (id !== requestId) return;
        if (result.ok !== true || !Array.isArray(result.items) || !result.items.length)
          throw new Error('empty market ranking');
        rankingFailureCount = 0;
        nextRankingReadAt = Date.now() + 60000;
        customOrder = []; // A refreshed ranking supersedes a manually saved layout.
        if (title) title.textContent = titles[tab];
        const signature = JSON.stringify(result.items.map((row) => [
          row.symbol, row.name, row.exchange, row.rank, row.price, row.change_pct, row.trading_value, row.trading_value_text, row.industry, row.issue_headline
        ]));
        if (signature === lastRankingSignature &&
            list.querySelector('button[data-original-index]')) {
          applyChangeSort();
          void loadIndustryLabels();
          paintLiveQuotes();
          return;
        }
        lastRankingSignature = signature;
        cachedRankingAsOf = asOfLabel(mostCommonCloseDate(result.items));
        if (asOfBadge) {
          asOfBadge.textContent = cachedRankingAsOf;
          asOfBadge.hidden = !cachedRankingAsOf;
        }
        list.replaceChildren();
        result.items.forEach((item, index) => {
          const button = document.createElement('button');
          button.dataset.stockName = String(item.name || '');
          button.dataset.stockSymbol = String(item.symbol || '');
          button.dataset.stockExchange = String(item.exchange || '');
          button.dataset.originalIndex = String(index);
          button.dataset.rowId = String(item.symbol || item.name || index);
          button.dataset.originalRank = String(item.rank || index + 1);
          button.dataset.changePct = typeof item.change_pct === 'number' && Number.isFinite(item.change_pct)
            ? String(item.change_pct) : '-Infinity';
          button.dataset.currentPrice = typeof item.price === 'number' ? String(item.price) : '';
          button.dataset.currentChangePct = typeof item.change_pct === 'number' ? String(item.change_pct) : '';
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
          button.addEventListener('click', () => {
            if (market === 'us' && tab === 'value') window.GaemiGTPWidgetDock?.setChartSelection?.(String(item.symbol || ''));
            window.openStockInChat?.(item.name, {
            market, menu: tab, name: item.name, symbol: item.symbol,
            rank: item.rank || index + 1,
            display_rank: Number(rank.textContent) || item.rank || index + 1,
            sort: changeSorted ? 'change_pct' : 'source',
            industry: item.industry,
            price: button.dataset.currentPrice !== '' ? Number(button.dataset.currentPrice) : item.price,
            change_pct: button.dataset.currentChangePct !== ''
              ? Number(button.dataset.currentChangePct) : item.change_pct,
            trading_value: item.trading_value, trading_value_text: item.trading_value_text,
            currency: 'USD', source: result.source === 'kiwoom' ? 'kiwoom' : 'unknown'
          });
          });

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
          price.dataset.marketPrice = 'true';
          price.textContent = typeof item.price === 'number' && Number.isFinite(item.price)
            ? '$' + item.price.toLocaleString('en-US', { maximumFractionDigits: 2 }) : '';
          const nameGroup = document.createElement('span');
          nameGroup.className = 'market-stock-name-group';
          nameGroup.append(rank, name);
          top.append(nameGroup, price);

          // Keep industry and turnover in the existing second row.
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
          industryLabel.dataset.marketIndustry = 'true';
          // Turnover still determines ranking; show only verified industry metadata.
          const rankingIndustry = typeof item.industry === 'string' ? item.industry.trim() : '';
          if (rankingIndustry) rankingIndustryBySymbol.set(button.dataset.stockSymbol, rankingIndustry);
          industryLabel.textContent = industryFor(button.dataset.stockSymbol, button.dataset.stockExchange);
          industry.append(watchStar, industryLabel);
          const change = document.createElement('span');
          const pct = item.change_pct;
          change.dataset.marketChange = 'true';
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
          issue.textContent = sidebarIssueTitle(item.issue_headline);
          thirdRow.append(issue);
          content.append(top, secondRow, thirdRow);
          button.append(grip, stockMark(item), content);
          list.appendChild(button);
        });
        applyChangeSort();
        void loadIndustryLabels();
        paintLiveQuotes();
        syncQqqSocket();
      } catch (error) {
        console.warn('TOP20 request failed:', error);
        rankingFailureCount += 1;
        nextRankingReadAt = Date.now() + Math.min(300000, 15000 * 2 ** (rankingFailureCount - 1));
        // Keep the sidebar free of transient loading/error copy.
      } finally {
        window.clearTimeout(timeout);
        rankingRequestInFlight = false;
      }
    };

    // Share one DigitalOcean socket between QQQ, the visible ranking, and the chart.
    const qqqWidgetActive = () => window.GaemiGTPWidgetDock?.isActive?.('qqq') === true;
    const marketEtfWidgetActive = () => ['spy', 'dia'].some(id => window.GaemiGTPWidgetDock?.isActive?.(id) === true);
    const quoteConsumersActive = () =>
      window.GaemiGTPWidgetDock?.isInlineChartActive?.() === true;
    let qqqSocket = null;
    let qqqSocketGeneration = 0;
    let qqqReconnectTimer = null;
    let qqqReconnectDelay = 1000;
    const qqqSocketWanted = () =>
      document.visibilityState === 'visible'
      && (qqqWidgetActive() || marketEtfWidgetActive() || industryViewActive() || (sidebarActive() && (tab === 'value' || tab === 'industry')) || quoteConsumersActive());
    const dispatchQqqQuote = (quote) => {
      if (quote?.symbol === 'QQQ') {
        marketQqqQuote = quote;
      } else if (!marketQqqQuote || Date.now() - marketQqqQuote.received_at_ms > 180000) {
        marketQqqQuote = null;
      }
      window.dispatchEvent(new CustomEvent('gaemi:qqq-quote', {
        detail: { quote: marketQqqQuote || null }
      }));
    };
    const stopQqqSocket = () => {
      qqqSocketGeneration += 1;
      if (qqqReconnectTimer !== null) {
        window.clearTimeout(qqqReconnectTimer);
        qqqReconnectTimer = null;
      }
      const socket = qqqSocket;
      qqqSocket = null;
      if (socket && socket.readyState < window.WebSocket.CLOSING) {
        try { socket.close(1000, 'QQQ widget inactive'); } catch (_) {}
      }
      dispatchQqqQuote(null);
      publishLiveQuotes([]);
      publishIndustryQuotes([]);
      publishMarketEtfQuotes([]);
    };
    const scheduleQqqReconnect = (generation) => {
      if (!qqqSocketWanted() || generation !== qqqSocketGeneration || qqqReconnectTimer !== null) return;
      const delay = qqqReconnectDelay;
      qqqReconnectDelay = Math.min(30000, qqqReconnectDelay * 2);
      qqqReconnectTimer = window.setTimeout(() => {
        qqqReconnectTimer = null;
        if (generation === qqqSocketGeneration) openQqqSocket();
      }, delay);
    };
    const openQqqSocket = () => {
      if (!qqqSocketWanted() || !window.WebSocket) return;
      if (qqqSocket && qqqSocket.readyState < window.WebSocket.CLOSING) return;
      const generation = ++qqqSocketGeneration;
      let socket;
      try {
        socket = new window.WebSocket('wss://quotes.gaemigtp.com/ws/us-live-quotes');
      } catch (_) {
        scheduleQqqReconnect(generation);
        return;
      }
      qqqSocket = socket;
      socket.onopen = () => {
        if (generation !== qqqSocketGeneration || !qqqSocketWanted()) {
          try { socket.close(1000, 'QQQ widget inactive'); } catch (_) {}
          return;
        }
        qqqReconnectDelay = 1000;
      };
      socket.onmessage = (event) => {
        if (generation !== qqqSocketGeneration) return;
        try {
          const message = JSON.parse(event.data);
          if (message?.type === 'quote') dispatchQqqQuote(message.quote || null);
          if (message?.type === 'quotes' && Array.isArray(message.items)) publishLiveQuotes(message.items);
          if (message?.type === 'industry-quotes' && Array.isArray(message.items)) publishIndustryQuotes(message.items);
          if (message?.type === 'market-etf-quotes' && Array.isArray(message.items)) publishMarketEtfQuotes(message.items);
        } catch (_) {
          // Ignore malformed frames; the next valid quote will refresh the card.
        }
      };
      socket.onerror = () => {
        try { socket.close(); } catch (_) {}
      };
      socket.onclose = () => {
        if (qqqSocket === socket) qqqSocket = null;
        if (generation !== qqqSocketGeneration) return;
        dispatchQqqQuote(null);
        publishLiveQuotes([]);
        publishIndustryQuotes([]);
        publishMarketEtfQuotes([]);
        scheduleQqqReconnect(generation);
      };
    };
    const syncQqqSocket = () => {
      if (qqqSocketWanted()) {
        if (!qqqSocket && qqqReconnectTimer === null) openQqqSocket();
      } else if (qqqSocket || qqqReconnectTimer !== null) {
        stopQqqSocket();
      }
    };
    window.setTimeout(syncQqqSocket, 50);
    let liveQuotes = [];
    const freshQuote = (quote, now) => quote && quote.stale === false
      && typeof quote.symbol === 'string' && Number.isFinite(quote.price) && quote.price > 0
      && Number.isFinite(quote.received_at_ms) && quote.received_at_ms <= now + 5000
      && now - quote.received_at_ms <= 25000;
    const paintLiveQuotes = () => {
      if (!sidebarActive() || tab !== 'value' || !list) return;
      const now = Date.now();
      const bySymbol = new Map([...list.querySelectorAll(':scope > button[data-original-index]')]
        .map((button) => [button.dataset.stockSymbol, button]));
      let updated = 0;
      liveQuotes.forEach((quote) => {
        if (!freshQuote(quote, now)) return;
        const button = bySymbol.get(String(quote.symbol || ''));
        if (!button) return;
        const price = button.querySelector('[data-market-price]');
        if (price) price.textContent = '$' + quote.price.toLocaleString('en-US', { maximumFractionDigits: 2 });
        button.dataset.currentPrice = String(quote.price);
        if (typeof quote.change_pct === 'number' && Number.isFinite(quote.change_pct)) {
          const change = button.querySelector('[data-market-change]');
          if (change) {
            change.textContent = (quote.change_pct > 0 ? '+' : '') + quote.change_pct.toFixed(2) + '%';
            change.className = 'market-stock-change' +
              (quote.change_pct > 0 ? ' text-rose-500' : quote.change_pct < 0
                ? ' text-sky-500' : ' text-[#64748b] dark:text-[#a1a1aa]');
          }
          button.dataset.changePct = String(quote.change_pct);
          button.dataset.currentChangePct = String(quote.change_pct);
          if (quote.reference_close_date) button.dataset.referenceCloseDate = quote.reference_close_date;
        } else if (button.dataset.referenceCloseDate && marketQqqQuote?.reference_close_date
                   && button.dataset.referenceCloseDate !== marketQqqQuote.reference_close_date) {
          // Only clear a rate when the reference closing session really changed.
          const change = button.querySelector('[data-market-change]');
          if (change) change.textContent = '—';
          button.dataset.changePct = '-Infinity';
          button.dataset.currentChangePct = '';
          button.dataset.referenceCloseDate = '';
        }
        updated++;
      });
      if (updated && changeSorted && !draggedRow) applyChangeSort();
    };
    const publishLiveQuotes = items => {
      const now = Date.now();
      liveQuotes = items.filter(quote => freshQuote(quote, now));
      window.dispatchEvent(new CustomEvent('gaemi:us-live-quotes', {
        detail: { items: liveQuotes }
      }));
      paintLiveQuotes();
    };
    const publishIndustryQuotes = items => {
      const now = Date.now();
      industryLiveQuotes = items.filter(quote => freshQuote(quote, now));
      rememberIndustryEtfQuotes(items, 'websocket');
      // A confirmed close-based percentage is still useful when an individual
      // stock has not traded again in the past 25 seconds.
      items.forEach(quote => {
        if (industryEtfSymbols.has(industrySymbol(quote?.symbol))) return;
        if (Number.isFinite(quote?.change_pct) && quote.reference_close_date
            && Number.isFinite(quote.received_at_ms)
            && quote.received_at_ms <= now + 5000
            && now - quote.received_at_ms <= 30 * 60 * 1000) {
          industryLastVerifiedQuotes.set(industrySymbol(quote.symbol), quote);
        }
      });
      if (industryViewActive() && industryMapData) {
        renderIndustryMap(industryMapData);
        void refreshIndustryEtfRates();
      }
    };
    const publishMarketEtfQuotes = items => {
      const now = Date.now();
      window.dispatchEvent(new CustomEvent('gaemi:market-etf-quotes', {
        detail: { items: items.filter(quote => freshQuote(quote, now) &&
          (quote.symbol === 'SPY' || quote.symbol === 'DIA')) }
      }));
    };

    // Also refresh when the user returns to this tab after it was backgrounded.
    // Keep background reads off to avoid unnecessary database usage.
    const refreshOnReturn = () => {
      syncQqqSocket();
      if (document.visibilityState !== 'visible') return;
      if (sidebarActive() && ['value', 'realtime', 'industry'].includes(tab)) void showUsRanking();
      paintLiveQuotes();
    };
    window.addEventListener('gaemi:qqq-placement', syncQqqSocket);
    window.addEventListener('gaemi:market-widget-placement', syncQqqSocket);
    document.addEventListener('visibilitychange', refreshOnReturn);
    window.addEventListener('focus', refreshOnReturn);

    // Only refresh the analyzed stock's existing DB-backed issue title.
    // Never recollect news, rerank stocks, or replace the displayed list.
    const refreshAnalyzedIssue = async (event) => {
      const detail = event.detail || {};
      const name = String(detail.name || '').trim();
      if (!name || tab !== 'value') return;
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
        if (issue) issue.textContent = sidebarIssueTitle(updated.headline);
      } catch (_) {
        // Keep the previous headline on transient read failures.
      }
    };
    window.addEventListener('gaemi:analysis-issues-ready', (event) => {
      void refreshAnalyzedIssue(event);
    });

    changeSortButton?.addEventListener('click', () => {
      if (tab !== 'value') return;
      changeSorted = !changeSorted;
      applyChangeSort();
    });

    bindStaticSelection('[data-info-tab-action]', 2);
    sidebar.querySelectorAll('[data-info-tab-action]').forEach((button) => {
      if (button.disabled) return;
      button.addEventListener('click', () => {
        const nextTab = button.dataset.infoTabAction;
        tab = nextTab;
        customOrder = readOrder();
        changeSorted = false;
        syncIndustryTabLayout();
        void showUsRanking();
        syncQqqSocket();
      });
    });
    sidebar.dataset.marketControlsBound = 'true';
    window.GaemiGTPMarketSidebar.refreshLiveQuotes = refreshOnReturn;
    window.GaemiGTPMarketSidebar.syncIndustryLayout = syncIndustryTabLayout;
    window.GaemiGTPMarketSidebar.selectIndustryTab = () => {
      const button = sidebar.querySelector('[data-info-tab-action="industry"]');
      if (button && tab !== 'industry') button.click();
      else syncIndustryTabLayout();
    };
    window.addEventListener('gaemi:widget-placement', syncIndustryTabLayout);
    window.addEventListener('gaemi:widget-change', syncIndustryTabLayout);
    syncIndustryTabLayout();
    // Closed panels and background tabs consume no ranking or quote reads.
    if (sidebarActive()) void showUsRanking();
    window.setInterval(() => {
      if (document.visibilityState !== 'visible') return;
      syncQqqSocket();
      if (industryViewActive()) {
        void loadIndustryMap(requestId);
        void refreshIndustryEtfRates();
      }
      if (draggedRow) return;
      if (sidebarActive() && tab === 'value') void showUsRanking();
    }, 3000);
  }

  document.addEventListener('DOMContentLoaded', bindMarketControls);

  window.toggleLeftSidebar = toggle;
  window.GaemiGTPMarketSidebar = { toggle, bindMarketControls };
}());
