/* Live USD/KRW and XAUUSD ticks, rendered in the existing compact market-widget layout. */
(function () {
  'use strict';

  const API = 'https://biquote.io/api/';
  const POLL_MS = 5000;
  const HISTORY_URL = (symbol) => API + symbol + '/ohlc?interval=1m&limit=60';
  const GRAMS_PER_TROY_OUNCE = 31.1034768;
  const state = {
    usdkrw: { points: [], record: null, historyLoaded: false },
    gold: { points: [], record: null, historyLoaded: false }
  };
  let timer = null;
  let busy = false;

  function number(value) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function timeMs(value) {
    if (typeof value === 'number' && Number.isFinite(value)) return value < 1e12 ? value * 1000 : value;
    if (typeof value === 'string') {
      const numeric = Number(value);
      if (Number.isFinite(numeric) && numeric > 0) return numeric < 1e12 ? numeric * 1000 : numeric;
      const parsed = Date.parse(value);
      return Number.isFinite(parsed) ? parsed : 0;
    }
    return 0;
  }

  function format(value, digits) {
    return value.toLocaleString('ko-KR', { minimumFractionDigits: digits, maximumFractionDigits: digits });
  }

  function formatTime(value) {
    const ms = timeMs(value);
    if (!ms) return '';
    return new Intl.DateTimeFormat('ko-KR', {
      timeZone: 'Asia/Seoul', hour: '2-digit', minute: '2-digit', second: '2-digit'
    }).format(new Date(ms));
  }

  function isFresh(tick) {
    const age = number(tick?.quoteAgeSeconds);
    const timestamp = timeMs(tick?.timestamp);
    const timestampAge = timestamp ? (Date.now() - timestamp) / 1000 : null;
    return tick?.stale !== true
      && tick?.marketState !== 'closed'
      && (age === null ? timestampAge !== null && timestampAge >= -5 && timestampAge <= 90 : age <= 90);
  }

  function appendPoint(id, value, at) {
    const points = state[id].points;
    const timestamp = timeMs(at) || Date.now();
    const last = points[points.length - 1];
    if (last && timestamp <= last.time) return;
    points.push({ value, time: timestamp });
    while (points.length > 120) points.shift();
  }

  function draw(card, points) {
    const line = card.querySelector('[data-market-quote-line]');
    const fill = card.querySelector('[data-market-quote-fill]');
    if (!line || !fill) return;
    if (points.length < 2) {
      line.setAttribute('points', '');
      fill.setAttribute('points', '');
      return;
    }
    const values = points.map(point => point.value);
    const low = Math.min(...values);
    const high = Math.max(...values);
    const span = high - low;
    const coords = values.map((value, index) => {
      const x = 1 + index / (values.length - 1) * 70;
      const y = span === 0 ? 14 : 25 - (value - low) / span * 22;
      return x.toFixed(1) + ',' + y.toFixed(1);
    }).join(' ');
    line.setAttribute('points', coords);
    fill.setAttribute('points', '1,27 ' + coords + ' 71,27');
  }

  function paint(id) {
    const card = document.querySelector('[data-market-quote-widget="' + id + '"]');
    const record = state[id].record;
    if (!card) return;
    const priceNode = card.querySelector('[data-market-quote-value]');
    const percentNode = card.querySelector('[data-market-quote-percent]');
    const chart = card.querySelector('.central-widget-card__sparkline');
    const fresh = Boolean(record?.fresh);
    card.classList.toggle('central-widget-card--qqq-muted', !fresh);
    if (priceNode) priceNode.textContent = record
      ? format(record.price, id === 'usdkrw' ? 2 : 0)
      : '—';
    if (percentNode) {
      const change = record?.changePct;
      if (percentNode) {
        percentNode.textContent = Number.isFinite(change)
          ? (change > 0 ? '+' : '') + change.toFixed(2) + '%'
          : '—';
        percentNode.classList.toggle('central-widget-card__kospi-change--up', fresh && change > 0);
        percentNode.classList.toggle('central-widget-card__kospi-change--down', fresh && change < 0);
      }
    }
    chart?.classList.toggle('central-widget-card__sparkline--up', fresh && record?.changePct > 0);
    chart?.classList.toggle('central-widget-card__sparkline--down', fresh && record?.changePct < 0);
    draw(card, state[id].points);
  }

  async function getJson(url) {
    const response = await fetch(url, { cache: 'no-store', signal: AbortSignal.timeout(7000) });
    if (!response.ok) throw new Error('Market quote HTTP ' + response.status);
    return response.json();
  }

  async function loadHistory(id, symbol, fxRate = null) {
    if (state[id].historyLoaded) return;
    state[id].historyLoaded = true;
    try {
      const data = await getJson(HISTORY_URL(symbol));
      const bars = Array.isArray(data?.bars) ? data.bars.slice().reverse() : [];
      const historical = [];
      for (const bar of bars) {
        const close = number(bar?.close);
        const timestamp = timeMs(bar?.openTime);
        if (close === null || close <= 0 || !timestamp) continue;
        const price = id === 'gold' && fxRate ? close * fxRate / GRAMS_PER_TROY_OUNCE : close;
        historical.push({ value: price, time: timestamp });
      }
      const latest = state[id].points[state[id].points.length - 1];
      const lastHistoryTime = historical[historical.length - 1]?.time || 0;
      state[id].points = historical;
      if (latest && latest.time > lastHistoryTime) state[id].points.push(latest);
      while (state[id].points.length > 120) state[id].points.shift();
    } catch (_) {
      state[id].historyLoaded = false;
    }
  }

  function makeRecord(tick, price, changePct, id) {
    const changeAmount = Number.isFinite(changePct) && changePct > -100
      ? price - price / (1 + changePct / 100) : null;
    return {
      price,
      changePct,
      changeAmount,
      time: tick.timestamp,
      fresh: isFresh(tick),
      marketState: tick.marketState || 'unknown',
      source: 'biquote'
    };
  }

  async function refresh() {
    if (busy || document.hidden) return;
    const hasFx = Boolean(document.querySelector('[data-market-quote-widget="usdkrw"]'));
    const hasGold = Boolean(document.querySelector('[data-market-quote-widget="gold"]'));
    if (!hasFx && !hasGold) return;
    busy = true;
    try {
      const symbols = ['USDKRW'];
      if (hasGold) symbols.push('XAUUSD');
      const query = symbols.map(symbol => 'symbols=' + encodeURIComponent(symbol)).join('&');
      const ticks = await getJson(API + 'latest?' + query);
      const fxTick = ticks?.USDKRW;
      const goldTick = ticks?.XAUUSD;
      if (!fxTick) throw new Error('USDKRW tick unavailable');
      const fxRate = number(fxTick?.mid);
      const goldUsd = number(goldTick?.mid);
      if (fxRate !== null && fxRate > 0) {
        const fxChange = number(fxTick?.dayDiffPercent);
        const fxRecord = makeRecord(fxTick, fxRate, fxChange, 'usdkrw');
        state.usdkrw.record = fxRecord;
        appendPoint('usdkrw', fxRate, fxTick.timestamp);
        if (hasFx) paint('usdkrw');
      }
      if (hasGold && fxRate !== null && fxRate > 0 && goldUsd !== null && goldUsd > 0) {
        const goldChange = number(goldTick?.dayDiffPercent);
        const fxChange = number(fxTick?.dayDiffPercent);
        const combinedChange = goldChange === null || fxChange === null
          ? null : ((1 + goldChange / 100) * (1 + fxChange / 100) - 1) * 100;
        const goldPrice = goldUsd * fxRate / GRAMS_PER_TROY_OUNCE;
        const fresh = isFresh(goldTick) && isFresh(fxTick);
        state.gold.record = { ...makeRecord(goldTick, goldPrice, combinedChange, 'gold'), fresh };
        appendPoint('gold', goldPrice, goldTick.timestamp);
        paint('gold');
      }
      if (hasFx || hasGold) {
        const historyJobs = [];
        if (hasFx) historyJobs.push(loadHistory('usdkrw', 'USDKRW'));
        if (hasGold) historyJobs.push(loadHistory('gold', 'XAUUSD', fxRate));
        await Promise.all(historyJobs);
        if (hasFx) paint('usdkrw');
        if (hasGold) paint('gold');
      }
    } catch (_) {
      for (const id of ['usdkrw', 'gold']) {
        if (document.querySelector('[data-market-quote-widget="' + id + '"]')) {
          const record = state[id].record;
          if (record) record.fresh = false;
          paint(id);
        }
      }
    } finally {
      busy = false;
    }
  }

  function mount() {
    paint('usdkrw');
    paint('gold');
    void refresh();
    if (!timer) timer = window.setInterval(() => { void refresh(); }, POLL_MS);
  }

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) void refresh();
  });
  window.GaemiGTPMarketQuoteWidgets = { mount, refresh };
}());
