/* Independent market quote widgets: USD/KRW reference rate and XAU/KRW spot reference. */
(function () {
  'use strict';

  const FX_URL = 'https://api.frankfurter.dev/v1/latest?base=USD&symbols=KRW';
  const GOLD_URL = 'https://xaus.com/api/v1/spot?currency=KRW&unit=gram&compact=1';
  const FX_REFRESH_MS = 6 * 60 * 60 * 1000;
  const GOLD_REFRESH_MS = 60 * 1000;
  const RETRY_MS = 5 * 60 * 1000;
  let fx = null;
  let gold = null;
  let fxAttemptAt = 0;
  let goldAttemptAt = 0;
  let timer = null;

  function formatNumber(value, digits) {
    return Number(value).toLocaleString('ko-KR', {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits
    });
  }

  function formatDate(value) {
    if (!value) return '';
    const date = new Date(value);
    if (!Number.isFinite(date.getTime())) return '';
    return new Intl.DateTimeFormat('ko-KR', {
      timeZone: 'Asia/Seoul', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit'
    }).format(date);
  }

  function paint(id, record, kind) {
    const root = document.querySelector('[data-market-quote-widget="' + id + '"]');
    if (!root) return;
    const valueNode = root.querySelector('[data-market-quote-value]');
    const metaNode = root.querySelector('[data-market-quote-meta]');
    const stateNode = root.querySelector('[data-market-quote-state]');
    if (!record) {
      if (valueNode) valueNode.textContent = '—';
      if (metaNode) metaNode.textContent = '시세 연결 확인 필요';
      if (stateNode) stateNode.textContent = '조회 불가';
      root.classList.add('is-market-quote-stale');
      return;
    }
    if (valueNode) valueNode.textContent = kind === 'fx'
      ? formatNumber(record.value, 2)
      : formatNumber(record.value, 0);
    if (metaNode) metaNode.textContent = record.meta;
    if (stateNode) stateNode.textContent = record.state || '참고 시세';
    root.classList.toggle('is-market-quote-stale', Boolean(record.stale));
  }

  async function fetchFx() {
    fxAttemptAt = Date.now();
    try {
      const response = await fetch(FX_URL, { cache: 'default', signal: AbortSignal.timeout(8000) });
      if (!response.ok) throw new Error('FX HTTP ' + response.status);
      const data = await response.json();
      const value = Number(data?.rates?.KRW);
      if (!Number.isFinite(value) || value <= 0 || !data?.date) throw new Error('Invalid FX payload');
      fx = {
        value,
        meta: '일간 기준환율 · ' + data.date,
        state: 'Frankfurter',
        stale: false
      };
    } catch (_) {
      if (fx) fx = { ...fx, stale: true, state: '마지막 정상값' };
    }
    paint('usdkrw', fx, 'fx');
  }

  async function fetchGold() {
    goldAttemptAt = Date.now();
    try {
      const response = await fetch(GOLD_URL, { cache: 'default', signal: AbortSignal.timeout(8000) });
      if (!response.ok) throw new Error('Gold HTTP ' + response.status);
      const data = await response.json();
      const value = Number(data?.xau?.price);
      const status = data?.data_state?.status;
      if (!Number.isFinite(value) || value <= 0 || data?.xau?.currency !== 'KRW'
          || data?.xau?.unit !== 'gram' || status === 'unavailable') {
        throw new Error('Invalid gold payload');
      }
      const stale = Boolean(data.stale || status === 'stale' || data.fx_stale);
      const observedAt = data.price_as_of || data.data_state?.as_of || data.updated_at;
      const parts = ['국제 현물 · 원화/g'];
      if (observedAt) parts.push(formatDate(observedAt));
      if (data.fx_stale) parts.push('환율 환산 갱신 지연');
      gold = {
        value,
        meta: parts.join(' · '),
        state: stale ? '이전 관측값' : 'XAUS 참고 시세',
        stale
      };
    } catch (_) {
      if (gold) gold = { ...gold, stale: true, state: '마지막 정상값' };
    }
    paint('gold', gold, 'gold');
  }

  async function refresh(force = false) {
    const hasFx = Boolean(document.querySelector('[data-market-quote-widget="usdkrw"]'));
    const hasGold = Boolean(document.querySelector('[data-market-quote-widget="gold"]'));
    if (document.hidden || (!hasFx && !hasGold)) return;
    const now = Date.now();
    const jobs = [];
    const fxDue = !fx ? (!fxAttemptAt || now - fxAttemptAt >= RETRY_MS) : now - fxAttemptAt >= FX_REFRESH_MS;
    const goldDue = !gold ? (!goldAttemptAt || now - goldAttemptAt >= RETRY_MS) : now - goldAttemptAt >= GOLD_REFRESH_MS;
    if (hasFx && (force || fxDue)) jobs.push(fetchFx());
    if (hasGold && (force || goldDue)) jobs.push(fetchGold());
    await Promise.all(jobs);
  }

  function mount() {
    paint('usdkrw', fx, 'fx');
    paint('gold', gold, 'gold');
    void refresh();
    if (!timer) timer = window.setInterval(() => { void refresh(); }, GOLD_REFRESH_MS);
  }

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) void refresh();
  });
  window.GaemiGTPMarketQuoteWidgets = { mount, refresh };
}());
