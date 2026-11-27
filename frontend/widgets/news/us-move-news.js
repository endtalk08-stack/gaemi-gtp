/* Loader for US TOP20 price-move headlines ("엔비디아가 상승률 5%를 돌파했어요"), shown under 종목 and 전체. */
(function () {
  'use strict';
  const ENDPOINT = '/news/moves/us';
  const TTL = 30000;
  let rows = [];
  let fetchedAt = 0;
  let pending = null;
  function load() {
    if (fetchedAt && Date.now() - fetchedAt < TTL) return Promise.resolve(rows);
    if (pending) return pending;
    pending = fetch(ENDPOINT, { cache: 'no-store' })
      .then(response => (response.ok ? response.json() : null))
      .then(data => { if (data?.ok === true && Array.isArray(data.items)) { rows = data.items; fetchedAt = Date.now(); } return rows; })
      .catch(() => rows)
      .finally(() => { pending = null; });
    return pending;
  }
  function newsItems() {
    return rows.map(row => ({
      id: row.id, category: '종목', title: row.title, summary: '', body: '',
      source: '개미지티피', published_at: row.published_at, time: '', url: '',
      tickers: ['$' + row.symbol], issues: [], industries: []
    }));
  }
  window.GaemiGTPUsMoveNews = { load, newsItems };
}());
