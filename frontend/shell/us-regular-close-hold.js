/* Retain public, last-confirmed US regular-session quotes for the 16:00-16:30 ET transition.
 * No trading data, credentials, or guessed closing prices are stored.
 * Values are last verified regular-session ticks, NOT official closing auction data. */
(function () {
  'use strict';
  const STORAGE_KEY = 'gaemiGTP_public_us_close_transition_v1';
  const CAPTURE_START = 15 * 60 + 40;
  const REGULAR_END = 16 * 60;
  const HOLD_END = 16 * 60 + 30;
  const MAX_ENTRIES = 110;
  const MAX_QUOTE_AGE_MS = 90000;
  const MARKET_SYMBOL = /^[A-Z0-9.\-]{1,20}$/;
  const easternClock = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit',
    weekday: 'short', hour: '2-digit', minute: '2-digit', hourCycle: 'h23'
  });

  function eastern(ms) {
    if (!Number.isFinite(ms)) return null;
    const parts = Object.fromEntries(easternClock.formatToParts(new Date(ms))
      .filter(p => p.type !== 'literal').map(p => [p.type, p.value]));
    return {
      day: [parts.year, parts.month, parts.day].join('-'),
      weekday: parts.weekday,
      minute: Number(parts.hour) * 60 + Number(parts.minute)
    };
  }
  function isWeekday(p) { return p && !['Sat', 'Sun'].includes(p.weekday); }
  function isCapturing(p) {
    return isWeekday(p) && p.minute >= CAPTURE_START && p.minute < REGULAR_END;
  }
  function isHolding(p) {
    return isWeekday(p) && p.minute >= REGULAR_END && p.minute < HOLD_END;
  }
  function validQuote(quote) {
    return quote && quote.stale !== true
      && typeof quote.symbol === 'string' && MARKET_SYMBOL.test(quote.symbol)
      && Number.isFinite(quote.price) && quote.price > 0
      && Number.isFinite(quote.change_pct)
      && quote.change_pct > -100 && quote.change_pct < 10000
      && Number.isFinite(quote.received_at_ms);
  }
  let state = { day: '', entries: {} };
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
    if (stored && typeof stored.day === 'string'
        && stored.entries && typeof stored.entries === 'object'
        && !Array.isArray(stored.entries)) state = stored;
  } catch (_) {}
  let lastSavedMs = 0;

  function remember(quote) {
    const now = Date.now();
    const p = eastern(now);
    if (!isCapturing(p) || !validQuote(quote)) return false;
    const observed = eastern(quote.received_at_ms);
    if (!observed || observed.day !== p.day || !isCapturing(observed)
        || now - quote.received_at_ms < -5000
        || now - quote.received_at_ms > MAX_QUOTE_AGE_MS) return false;
    if (state.day !== p.day) state = { day: p.day, entries: {} };
    const prior = state.entries[quote.symbol];
    if (prior && Number.isFinite(prior.received_at_ms)
        && prior.received_at_ms > quote.received_at_ms) return false;
    state.entries[quote.symbol] = {
      symbol: quote.symbol, price: quote.price, change_pct: quote.change_pct,
      received_at_ms: quote.received_at_ms,
      reference_close_date: typeof quote.reference_close_date === 'string'
        ? quote.reference_close_date : null
    };
    if (Object.keys(state.entries).length > MAX_ENTRIES) {
      const toRemove = Object.keys(state.entries).sort(
        (a, b) => state.entries[a].received_at_ms - state.entries[b].received_at_ms
      )[0];
      delete state.entries[toRemove];
    }
    // One small, bounded public market snapshot; persistence survives a reload
    // during the 30-minute transition and is ignored outside that interval.
    if (!prior || now - lastSavedMs >= 5000) {
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); lastSavedMs = now; } catch (_) {}
    }
    return true;
  }

  function held(symbol) {
    const p = eastern(Date.now());
    if (!isHolding(p) || !MARKET_SYMBOL.test(String(symbol || ''))
        || state.day !== p.day) return null;
    const q = state.entries[symbol];
    if (!q || !validQuote(q)) return null;
    const observed = eastern(q.received_at_ms);
    return observed?.day === p.day && isCapturing(observed) ? { ...q } : null;
  }

  function resolve(symbol, incoming) {
    const prior = held(symbol);
    if (!prior) return incoming || null;
    // Preserve the entire verified pair, never combine the old percentage
    // with a new-session trade price from 16:00-16:30.
    return {
      ...prior, source: 'regular-session-last-verified', stale: true,
      market_session: 'last_regular_tick'
    };
  }

  function rate(symbol, incoming) {
    const prior = held(symbol);
    return prior ? prior.change_pct : incoming;
  }

  window.GaemiGTPRegularCloseHold = { remember, held, resolve, rate };
}());