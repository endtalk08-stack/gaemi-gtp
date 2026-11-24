/* News is a center-surface only. Feed data can be supplied later without coupling to live quotes. */
(function () {
  'use strict';
  const main = document.getElementById('mainContent');
  const feed = document.getElementById('gaemiCenterNewsFeed');
  const list = document.getElementById('gaemiCenterNewsList');
  if (!main || !feed || !list) return;

  function updateTabs(newsMode) {
    document.querySelectorAll('[data-center-mode]').forEach(function (button) {
      const active = button.dataset.centerMode === (newsMode ? 'news' : 'chat');
      if (active) button.setAttribute('aria-current', 'page');
      else button.removeAttribute('aria-current');
    });
  }

  function showNews() {
    document.getElementById('mainHeroView')?.classList.add('hidden');
    document.body.classList.add('analysis-mode');
    main.classList.add('is-news-view');
    feed.hidden = false;
    updateTabs(true);
  }

  function showChat() {
    main.classList.remove('is-news-view');
    feed.hidden = true;
    updateTabs(false);
    if (typeof window.resetToHome === 'function') window.resetToHome();
  }

  function safeTime(value) {
    if (typeof value === 'string' && /^\d{2}:\d{2}$/.test(value)) return value;
    const date = new Date(value);
    return Number.isFinite(date.getTime()) ?
      new Intl.DateTimeFormat('ko-KR', {hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Seoul'}).format(date) : '';
  }

  function setItems(items) {
    const nearTop = feed.scrollTop < 64;
    const rows = Array.isArray(items) ? items.slice() : [];
    rows.sort(function (a, b) {
      const ta = Date.parse(a?.published_at || a?.publishedAt || '') || 0;
      const tb = Date.parse(b?.published_at || b?.publishedAt || '') || 0;
      return tb - ta;
    });
    list.replaceChildren();
    rows.forEach(function (entry) {
      if (!entry || typeof entry.title !== 'string' || !entry.title.trim()) return;
      const row = document.createElement('article');
      row.className = 'gaemi-center-news-item';
      const time = document.createElement('time');
      time.className = 'gaemi-center-news-time';
      time.textContent = safeTime(entry.published_at || entry.publishedAt || entry.time);
      const copy = document.createElement('div');
      copy.className = 'gaemi-center-news-copy';
      const title = document.createElement('h3');
      title.className = 'gaemi-center-news-title';
      title.textContent = entry.title.trim();
      copy.append(title);
      const bodyText = typeof entry.summary === 'string' ? entry.summary : typeof entry.body === 'string' ? entry.body : '';
      if (bodyText.trim()) {
        const description = document.createElement('p');
        description.className = 'gaemi-center-news-description';
        description.textContent = bodyText.trim();
        copy.append(description);
      }
      row.append(time, copy);
      list.append(row);
    });
    document.getElementById('gaemiCenterNewsEmpty').hidden = list.childElementCount > 0;
    if (nearTop) feed.scrollTop = 0;
  }

  window.GaemiCenterNews = { showNews: showNews, showChat: showChat, setItems: setItems };
}());
