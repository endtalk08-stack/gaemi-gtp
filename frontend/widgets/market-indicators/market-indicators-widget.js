/* Five macro market indicator widgets. Data is relayed by the Pages Function. */
(function () {
  'use strict';

  const API = '/market/indicators';
  const POLL_MS = 60000;
  const IDS = ['us-2y', 'us-10y', 'dxy', 'vix', 'wti'];
  const state = new Map();
  let timer = null;
  let busy = false;

  function active() {
    return IDS.filter(id => window.GaemiGTPWidgetDock?.isActive?.(id));
  }

  function number(value, digits = 2) {
    return Number(value).toLocaleString('en-US', {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits
    });
  }

  function paint(item) {
    const card = document.querySelector('[data-market-indicator-widget="' + item.id + '"]');
    if (!card) return;
    const price = card.querySelector('[data-market-indicator-value]');
    const change = card.querySelector('[data-market-indicator-change]');
    const source = card.querySelector('[data-market-indicator-source]');
    const chart = card.querySelector('.central-widget-card__sparkline');
    const points = state.get(item.id)?.points || [];

    card.classList.toggle('central-widget-card--qqq-muted', !item.ok || item.fresh === false);
    if (price) {
      if (!item.ok) price.textContent = '—';
      else price.textContent = (item.id === 'wti' ? '
    }
    if (change) {
      if (!item.ok || !Number.isFinite(item.change)) {
        change.textContent = '—';
      } else if (item.change_unit === 'bp') {
        change.textContent = (item.change > 0 ? '+' : '') + number(item.change, 1) + 'bp';
      } else {
        change.textContent = (item.change > 0 ? '+' : '') + number(item.change, 2) + '%';
      }
      change.classList.toggle('central-widget-card__kospi-change--up', item.ok && item.change > 0);
      change.classList.toggle('central-widget-card__kospi-change--down', item.ok && item.change < 0);
    }
    if (source) {
      const asOf = item.as_of ? ' · ' + String(item.as_of).replace('T', ' ').replace('Z', ' UTC') : '';
      source.textContent = item.source + ' · ' + item.delay + asOf;
    }
    chart?.classList.toggle('central-widget-card__sparkline--up', item.ok && item.change > 0);
    chart?.classList.toggle('central-widget-card__sparkline--down', item.ok && item.change < 0);
    draw(chart, points);
  }

  function draw(chart, points) {
    const line = chart?.querySelector?.('[data-market-indicator-line]');
    const fill = chart?.querySelector?.('[data-market-indicator-fill]');
    if (!line || !fill) return;
    if (points.length < 2) {
      line.setAttribute('points', '');
      fill.setAttribute('points', '');
      return;
    }
    const low = Math.min(...points), high = Math.max(...points), span = high - low;
    const coords = points.map((value, index) => {
      const x = 1 + index / (points.length - 1) * 70;
      const y = span === 0 ? 14 : 25 - (value - low) / span * 22;
      return x.toFixed(1) + ',' + y.toFixed(1);
    }).join(' ');
    line.setAttribute('points', coords);
    fill.setAttribute('points', '1,27 ' + coords + ' 71,27');
  }

  async function refresh() {
    if (busy || document.hidden || !active().length) return;
    busy = true;
    try {
      const response = await fetch(API, { cache: 'no-store', signal: AbortSignal.timeout(12000) });
      if (!response.ok) throw new Error('Indicators HTTP ' + response.status);
      const payload = await response.json();
      if (!payload?.ok || !Array.isArray(payload.items)) throw new Error('Invalid indicators response');
      payload.items.forEach(item => {
        const previous = state.get(item.id);
        const points = previous?.points || [];
        if (item.ok && Number.isFinite(item.value)) {
          if (!points.length || points[points.length - 1] !== item.value) points.push(item.value);
          while (points.length > 60) points.shift();
        }
        state.set(item.id, { points, item });
        paint(item);
      });
    } catch (_) {
      IDS.forEach(id => {
        const previous = state.get(id);
        if (previous?.item) paint({ ...previous.item, ok: false });
      });
    } finally {
      busy = false;
    }
  }

  function mount() {
    if (!active().length) return;
    void refresh();
    if (!timer) timer = window.setInterval(refresh, POLL_MS);
  }

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) void refresh();
  });
  window.addEventListener('gaemi:widget-change', () => {
    if (active().length) mount();
  });
  window.GaemiGTPMarketIndicators = { mount, refresh };
}());
 : '') + number(item.value, item.id === 'us-2y' || item.id === 'us-10y' ? 3 : 2) +
        (item.id === 'us-2y' || item.id === 'us-10y' ? '%' : '');
    }
    if (change) {
      if (!item.ok || !Number.isFinite(item.change)) {
        change.textContent = '—';
      } else if (item.change_unit === 'bp') {
        change.textContent = (item.change > 0 ? '+' : '') + number(item.change, 1) + 'bp';
      } else {
        change.textContent = (item.change > 0 ? '+' : '') + number(item.change, 2) + '%';
      }
      change.classList.toggle('central-widget-card__kospi-change--up', item.ok && item.change > 0);
      change.classList.toggle('central-widget-card__kospi-change--down', item.ok && item.change < 0);
    }
    if (source) {
      const asOf = item.as_of ? ' · ' + String(item.as_of).replace('T', ' ').replace('Z', ' UTC') : '';
      source.textContent = item.source + ' · ' + item.delay + asOf;
    }
    chart?.classList.toggle('central-widget-card__sparkline--up', item.ok && item.change > 0);
    chart?.classList.toggle('central-widget-card__sparkline--down', item.ok && item.change < 0);
    draw(chart, points);
  }

  function draw(chart, points) {
    const line = chart?.querySelector?.('[data-market-indicator-line]');
    const fill = chart?.querySelector?.('[data-market-indicator-fill]');
    if (!line || !fill) return;
    if (points.length < 2) {
      line.setAttribute('points', '');
      fill.setAttribute('points', '');
      return;
    }
    const low = Math.min(...points), high = Math.max(...points), span = high - low;
    const coords = points.map((value, index) => {
      const x = 1 + index / (points.length - 1) * 70;
      const y = span === 0 ? 14 : 25 - (value - low) / span * 22;
      return x.toFixed(1) + ',' + y.toFixed(1);
    }).join(' ');
    line.setAttribute('points', coords);
    fill.setAttribute('points', '1,27 ' + coords + ' 71,27');
  }

  async function refresh() {
    if (busy || document.hidden || !active().length) return;
    busy = true;
    try {
      const response = await fetch(API, { cache: 'no-store', signal: AbortSignal.timeout(12000) });
      if (!response.ok) throw new Error('Indicators HTTP ' + response.status);
      const payload = await response.json();
      if (!payload?.ok || !Array.isArray(payload.items)) throw new Error('Invalid indicators response');
      payload.items.forEach(item => {
        const previous = state.get(item.id);
        const points = previous?.points || [];
        if (item.ok && Number.isFinite(item.value)) {
          if (!points.length || points[points.length - 1] !== item.value) points.push(item.value);
          while (points.length > 60) points.shift();
        }
        state.set(item.id, { points, item });
        paint(item);
      });
    } catch (_) {
      IDS.forEach(id => {
        const previous = state.get(id);
        if (previous?.item) paint({ ...previous.item, ok: false });
      });
    } finally {
      busy = false;
    }
  }

  function mount() {
    if (!active().length) return;
    void refresh();
    if (!timer) timer = window.setInterval(refresh, POLL_MS);
  }

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) void refresh();
  });
  window.addEventListener('gaemi:widget-change', () => {
    if (active().length) mount();
  });
  window.GaemiGTPMarketIndicators = { mount, refresh };
}());
