/* Shared loader for the daily US TOP20 AI move analysis (Pages Function -> R2). */
(function () {
  'use strict';
  const ENDPOINT = '/news/ai/us/top20';
  const TTL = 60000;   // a new article arrives every 5 minutes
  let snapshot = null;
  let fetchedAt = 0;
  let pending = null;

  function load() {
    if (snapshot && Date.now() - fetchedAt < TTL) return Promise.resolve(snapshot);
    if (pending) return pending;
    pending = fetch(ENDPOINT, { cache: 'no-store' })
      .then(response => (response.ok ? response.json() : null))
      .then(data => {
        if (data?.ok === true && Array.isArray(data.items)) {
          snapshot = data;
          fetchedAt = Date.now();
          window.dispatchEvent(new CustomEvent('gaemi:us-news-ai', { detail: data }));
        }
        return snapshot;
      })
      .catch(() => snapshot)
      .finally(() => { pending = null; });
    return pending;
  }

  // One-sentence company intros (관련 종목 in news details), shared by every news item.
  const INTRO_ENDPOINT = '/news/ai/us/profiles';
  const INTRO_TTL = 600000;
  let intros = new Map();
  let introsAt = 0;
  let introsPending = null;
  function loadIntros() {
    if (introsAt && Date.now() - introsAt < INTRO_TTL) return Promise.resolve(intros);
    if (introsPending) return introsPending;
    introsPending = fetch(INTRO_ENDPOINT, { cache: 'no-store' })
      .then(response => (response.ok ? response.json() : null))
      .then(data => {
        if (data?.ok === true && data.items && typeof data.items === 'object') {
          intros = new Map(Object.entries(data.items).filter(([, text]) => typeof text === 'string' && text));
          introsAt = Date.now();
          window.dispatchEvent(new CustomEvent('gaemi:us-company-intros'));
        }
        return intros;
      })
      .catch(() => intros)
      .finally(() => { introsPending = null; });
    return introsPending;
  }
  // "$NVDA" or "NVDA" -> saved intro; an article's own third line covers runs before the file existed.
  function introFor(ticker) {
    const symbol = String(ticker || '').trim().replace(/^\$/, '').toUpperCase();
    if (!symbol) return '';
    if (intros.has(symbol)) return intros.get(symbol);
    const item = (snapshot?.items || []).find(x => x.symbol === symbol && x.status === 'ok');
    return item?.lines?.[2] || '';
  }

  function bySymbol() {
    return new Map((snapshot?.items || []).map(item => [item.symbol, item]));
  }

  // "장기 공급계약 확대로 6.26% 상승" — the keyword is AI, the number is Kiwoom.
  function moveText(item) {
    const pct = item?.change_pct;
    if (typeof pct !== 'number' || !Number.isFinite(pct)) return '';
    if (Math.abs(pct) < 0.005) return '보합';
    return Math.abs(pct).toFixed(2) + '% ' + (pct > 0 ? '상승' : '하락');
  }

  function withParticle(keyword) {
    // 으로 after a final consonant (except ㄹ), 로 otherwise.
    const last = String(keyword || '').trim().slice(-1);
    const code = last.charCodeAt(0) - 0xac00;
    if (code < 0 || code > 11171) return keyword + '로';
    const jong = code % 28;
    return keyword + (jong === 0 || jong === 8 ? '로' : '으로');
  }

  // Title shown in both the list and the existing detail view: "브로드컴 UBS 상승 가능성".
  // No change rate: the price at analysis time is not the price when the news broke.
  function titleText(item) {
    if (item?.headline) return item.headline;
    return [item.name, item.headline_keyword].filter(Boolean).join(' ');
  }

  // Shape a published analysis like any other news item for the existing widget views.
  // The third line (company intro) is shown under 관련 종목 instead, as for every news item.
  function asNewsItem(item) {
    const story = item.lines.slice(0, 2);
    return {
      id: 'ai:' + item.symbol, category: '분석', title: titleText(item),
      summary: story.join('\n'), body: story.join('\n\n'),
      source: '개미지티피', published_at: item.generated_at || snapshot?.generated_at || '', time: '',
      url: '', tickers: ['$' + item.symbol], issues: item.keywords.map(k => '#' + k),
      industries: item.industry ? [item.industry] : [], ai: item
    };
  }

  function newsItems() {
    return (snapshot?.items || []).filter(item => item.status === 'ok').map(asNewsItem);
  }

  window.GaemiGTPUsNewsAi = { load, bySymbol, get: () => snapshot, moveText, withParticle, titleText, newsItems,
    loadIntros, introFor };
}());
