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

  // Title shown in both the list and the existing detail view.
  function titleText(item) {
    if (item?.type === 'news') return item.news_headline;
    const move = moveText(item);
    return [item.name, withParticle(item.headline_keyword), move].filter(Boolean).join(' ');
  }

  // Shape a published analysis like any other news item for the existing widget views.
  function asNewsItem(item) {
    return {
      id: 'ai:' + item.symbol, category: '분석', title: titleText(item),
      summary: item.lines.join('\n'), body: item.lines.join('\n\n'),
      source: '개미지티피', published_at: item.generated_at || snapshot?.generated_at || '', time: '',
      url: '', tickers: ['$' + item.symbol], issues: item.keywords.map(k => '#' + k),
      industries: item.industry ? [item.industry] : [], ai: item
    };
  }

  function newsItems() {
    return (snapshot?.items || []).filter(item => item.status === 'ok').map(asNewsItem);
  }

  window.GaemiGTPUsNewsAi = { load, bySymbol, get: () => snapshot, moveText, withParticle, titleText, newsItems };
}());
