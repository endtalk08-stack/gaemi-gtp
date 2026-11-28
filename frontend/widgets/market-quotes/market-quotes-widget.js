/* Gold and USD/KRW quote adapter; presentation is owned by the existing QQQ-style card. */
(function () {
  'use strict';
  const API = 'https://biquote.io/api/';
  const POLL_MS = 5000;
  const HISTORY_URL = symbol => API + symbol + '/ohlc?interval=1m&limit=60';
  const GRAMS_PER_TROY_OUNCE = 31.1034768;
  const state = {
    gold: { points: [], record: null, historyLoaded: false },
    usdkrw: { points: [], record: null, historyLoaded: false }
  };
  let timer = null, busy = false;
  const num = value => { const n = Number(value); return Number.isFinite(n) ? n : null; };
  function timeMs(value) {
    if (typeof value === 'number' && Number.isFinite(value)) return value < 1e12 ? value * 1000 : value;
    if (typeof value !== 'string') return 0;
    const n = Number(value);
    if (Number.isFinite(n) && n > 0) return n < 1e12 ? n * 1000 : n;
    const parsed = Date.parse(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  function fresh(tick) {
    const age = num(tick?.quoteAgeSeconds);
    const timestamp = timeMs(tick?.timestamp);
    const elapsed = timestamp ? (Date.now() - timestamp) / 1000 : null;
    return tick?.stale !== true && tick?.marketState !== 'closed'
      && (age === null ? elapsed !== null && elapsed >= -5 && elapsed <= 90 : age >= 0 && age <= 90);
  }
  function addPoint(id, price, at) {
    const points = state[id].points, time = timeMs(at) || Date.now();
    if (points.length && time <= points[points.length - 1].time) return;
    points.push({ value: price, time });
    if (points.length > 120) points.shift();
  }
  function draw(card, points) {
    const line = card.querySelector('[data-market-quote-line]');
    const fill = card.querySelector('[data-market-quote-fill]');
    if (!line || !fill) return;
    if (points.length < 2) { line.setAttribute('points', ''); fill.setAttribute('points', ''); return; }
    const values = points.map(p => p.value), low = Math.min(...values), high = Math.max(...values);
    const span = high - low;
    const coords = values.map((v, i) => {
      const x = 1 + i / (values.length - 1) * 70;
      const y = span === 0 ? 14 : 25 - (v - low) / span * 22;
      return x.toFixed(1) + ',' + y.toFixed(1);
    }).join(' ');
    line.setAttribute('points', coords); fill.setAttribute('points', '1,27 ' + coords + ' 71,27');
  }
  function paint(id) {
    const card = document.querySelector('[data-market-quote-widget="' + id + '"]');
    const record = state[id].record;
    if (!card) return;
    const price = card.querySelector('[data-market-quote-value]');
    const pct = card.querySelector('[data-market-quote-percent]');
    const chart = card.querySelector('.central-widget-card__sparkline');
    card.classList.toggle('central-widget-card--qqq-muted', !record?.fresh);
    if (price) price.textContent = record
      ? record.price.toLocaleString('ko-KR', { minimumFractionDigits: id === 'usdkrw' ? 2 : 0, maximumFractionDigits: id === 'usdkrw' ? 2 : 0 })
      : '—';
    if (pct) {
      const change = record?.changePct;
      pct.textContent = Number.isFinite(change) ? (change > 0 ? '+' : '') + change.toFixed(2) + '%' : '—';
      pct.classList.toggle('central-widget-card__kospi-change--up', Number.isFinite(change) && change > 0);
      pct.classList.toggle('central-widget-card__kospi-change--down', Number.isFinite(change) && change < 0);
    }
    chart?.classList.toggle('central-widget-card__sparkline--up', record?.fresh && record.changePct > 0);
    chart?.classList.toggle('central-widget-card__sparkline--down', record?.fresh && record.changePct < 0);
    draw(card, state[id].points);
  }
  async function json(url) {
    const response = await fetch(url, { cache: 'no-store', signal: AbortSignal.timeout(7000) });
    if (!response.ok) throw new Error('Quote HTTP ' + response.status);
    return response.json();
  }
  async function history(id, symbol, fx) {
    if (state[id].historyLoaded) return;
    state[id].historyLoaded = true;
    try {
      const data = await json(HISTORY_URL(symbol));
      const bars = Array.isArray(data?.bars) ? data.bars.slice().reverse() : [];
      const points = bars.map(bar => {
        const close = num(bar?.close), time = timeMs(bar?.openTime);
        if (close === null || close <= 0 || !time) return null;
        return { value: id === 'gold' ? close * fx / GRAMS_PER_TROY_OUNCE : close, time };
      }).filter(Boolean);
      const latest = state[id].points.at(-1);
      state[id].points = points;
      if (latest && latest.time > (points.at(-1)?.time || 0)) state[id].points.push(latest);
      state[id].points = state[id].points.slice(-120);
    } catch (_) { state[id].historyLoaded = false; }
  }
  async function refresh() {
    if (busy || document.hidden) return;
    const hasFx = Boolean(document.querySelector('[data-market-quote-widget="usdkrw"]'));
    const hasGold = Boolean(document.querySelector('[data-market-quote-widget="gold"]'));
    if (!hasFx && !hasGold) return;
    busy = true;
    try {
      const symbols = ['USDKRW', ...(hasGold ? ['XAUUSD'] : [])];
      const ticks = await json(API + 'latest?' + symbols.map(s => 'symbols=' + encodeURIComponent(s)).join('&'));
      const fxTick = ticks?.USDKRW, goldTick = ticks?.XAUUSD, fx = num(fxTick?.mid);
      if (fxTick && fx > 0) {
        const change = num(fxTick.dayDiffPercent);
        state.usdkrw.record = { price: fx, changePct: change, fresh: fresh(fxTick) };
        addPoint('usdkrw', fx, fxTick.timestamp);
        if (hasFx) paint('usdkrw');
      }
      const goldUsd = num(goldTick?.mid);
      if (hasGold && fx > 0 && goldUsd > 0) {
        const gc = num(goldTick.dayDiffPercent), fc = num(fxTick.dayDiffPercent);
        const change = gc === null || fc === null ? null : ((1 + gc / 100) * (1 + fc / 100) - 1) * 100;
        state.gold.record = { price: goldUsd * fx / GRAMS_PER_TROY_OUNCE, changePct: change, fresh: fresh(goldTick) && fresh(fxTick) };
        addPoint('gold', state.gold.record.price, goldTick.timestamp);
        paint('gold');
      }
      const jobs = [];
      if (hasFx && fx > 0) jobs.push(history('usdkrw', 'USDKRW', fx));
      if (hasGold && fx > 0) jobs.push(history('gold', 'XAUUSD', fx));
      await Promise.all(jobs);
      if (hasFx) paint('usdkrw');
      if (hasGold) paint('gold');
    } catch (_) {
      for (const id of ['gold', 'usdkrw']) {
        if (state[id].record) state[id].record.fresh = false;
        paint(id);
      }
    } finally { busy = false; }
  }
  function mount() {
    paint('gold'); paint('usdkrw'); void refresh();
    if (!timer) timer = window.setInterval(() => { void refresh(); }, POLL_MS);
  }
  document.addEventListener('visibilitychange', () => { if (!document.hidden) void refresh(); });
  window.GaemiGTPMarketQuoteWidgets = { mount, refresh };
}());
