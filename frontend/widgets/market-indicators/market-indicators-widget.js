/* Live DXY and WTI widgets using the same BiQuote quote feed as gold/USD-KRW. */
(function () {
  'use strict';
  const API = 'https://biquote.io/api/';
  const POLL_MS = 5000;
  const IDS = ['dxy', 'wti'];
  const SYMBOLS = { dxy: 'DXY', wti: 'USOIL' };
  const LABELS = { dxy: '달러인덱스', wti: 'WTI 원유' };
  const state = {
    dxy: { points: [], record: null, historyLoaded: false },
    wti: { points: [], record: null, historyLoaded: false }
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
    const line = card.querySelector('[data-market-indicator-line]');
    const fill = card.querySelector('[data-market-indicator-fill]');
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
    const card = document.querySelector('[data-market-indicator-widget="' + id + '"]');
    const record = state[id].record;
    if (!card) return;
    const price = card.querySelector('[data-market-indicator-value]');
    const change = card.querySelector('[data-market-indicator-change]');
    const source = card.querySelector('[data-market-indicator-source]');
    const chart = card.querySelector('.central-widget-card__sparkline');
    card.classList.toggle('central-widget-card--qqq-muted', !record?.fresh);
    if (price) price.textContent = record
      ? (id === 'wti' ? '$' : '') + record.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
      : '—';
    if (change) {
      const pct = record?.changePct;
      change.textContent = record?.fresh && Number.isFinite(pct) ? (pct > 0 ? '+' : '') + pct.toFixed(2) + '%' : '—';
      change.classList.toggle('central-widget-card__kospi-change--up', record?.fresh && pct > 0);
      change.classList.toggle('central-widget-card__kospi-change--down', record?.fresh && pct < 0);
    }
    if (source) source.textContent = record?.fresh ? 'BiQuote · 실시간' :
      record ? (record.marketState === 'closed' ? '시장 종료 · 마지막 시세' : '시세 확인 필요') : '데이터 연결 중';
    chart?.classList.toggle('central-widget-card__sparkline--up', record?.fresh && record.changePct > 0);
    chart?.classList.toggle('central-widget-card__sparkline--down', record?.fresh && record.changePct < 0);
    draw(card, state[id].points);
  }
  async function json(url) {
    const response = await fetch(url, { cache: 'no-store', signal: AbortSignal.timeout(7000) });
    if (!response.ok) throw new Error('Quote HTTP ' + response.status);
    return response.json();
  }
  async function history(id) {
    if (state[id].historyLoaded) return;
    state[id].historyLoaded = true;
    try {
      const data = await json(API + SYMBOLS[id] + '/ohlc?interval=1m&limit=60');
      const bars = Array.isArray(data?.bars) ? data.bars.slice().reverse() : [];
      const points = bars.map(bar => {
        const close = num(bar?.close), time = timeMs(bar?.openTime);
        return close !== null && close > 0 && time ? { value: close, time } : null;
      }).filter(Boolean);
      const latest = state[id].points.at(-1);
      state[id].points = points;
      if (latest && latest.time > (points.at(-1)?.time || 0)) state[id].points.push(latest);
      state[id].points = state[id].points.slice(-120);
    } catch (_) { state[id].historyLoaded = false; }
  }
  async function refresh() {
    if (busy || document.hidden) return;
    const active = IDS.filter(id => window.GaemiGTPWidgetDock?.isActive?.(id));
    if (!active.length) return;
    busy = true;
    try {
      const query = active.map(id => 'symbols=' + encodeURIComponent(SYMBOLS[id])).join('&');
      const ticks = await json(API + 'latest?' + query);
      for (const id of active) {
        const tick = ticks?.[SYMBOLS[id]], price = num(tick?.mid);
        if (!tick || price === null || price <= 0) {
          if (state[id].record) state[id].record.fresh = false;
          paint(id);
          continue;
        }
        const record = {
          price, changePct: num(tick.dayDiffPercent),
          fresh: fresh(tick), marketState: tick.marketState || null
        };
        state[id].record = record;
        addPoint(id, price, tick.timestamp);
        paint(id);
      }
      await Promise.all(active.map(history));
      active.forEach(paint);
    } catch (_) {
      active.forEach(id => {
        if (state[id].record) state[id].record.fresh = false;
        paint(id);
      });
    } finally { busy = false; }
  }
  function mount() {
    if (!IDS.some(id => window.GaemiGTPWidgetDock?.isActive?.(id))) return;
    void refresh();
    if (!timer) timer = window.setInterval(() => { void refresh(); }, POLL_MS);
  }
  document.addEventListener('visibilitychange', () => { if (!document.hidden) void refresh(); });
  window.addEventListener('gaemi:widget-change', mount);
  window.GaemiGTPMarketIndicators = { mount, refresh };
}());
