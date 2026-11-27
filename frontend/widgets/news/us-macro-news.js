/* Loader for US macro headlines (Fed, White House, BEA) translated to Korean (Pages Function -> R2). */
(function () {
  'use strict';
  const ENDPOINT = '/news/macro/us';
  const TTL = 60000;
  let rows = [];
  let fetchedAt = 0;
  let pending = null;

  function load() {
    if (fetchedAt && Date.now() - fetchedAt < TTL) return Promise.resolve(rows);
    if (pending) return pending;
    pending = fetch(ENDPOINT, { cache: 'no-store' })
      .then(response => (response.ok ? response.json() : null))
      .then(data => {
        if (data?.ok === true && Array.isArray(data.items)) {
          rows = data.items;
          fetchedAt = Date.now();
        }
        return rows;
      })
      .catch(() => rows)
      .finally(() => { pending = null; });
    return pending;
  }

  // Shaped like any other news item: the translated headline and the translated first
  // paragraph of the official release in the list (nothing else, so it can be read aloud);
  // the original English title and the official link only in the detail view.
  function newsItems() {
    return rows.map(row => {
      const original = row.title_en ? '원문: ' + row.title_en : '';
      const summary = String(row.summary || '').trim();
      return {
      id: row.id, category: row.category, title: row.title,
      summary: summary ? summary.split(/\n\s*\n/)[0] : '',
      body: [summary, original].filter(Boolean).join('\n\n'),
      source: row.source, published_at: row.published_at, time: '', url: row.url,
      tickers: [], issues: [], industries: []
      };
    });
  }

  window.GaemiGTPUsMacroNews = { load, newsItems };
}());
