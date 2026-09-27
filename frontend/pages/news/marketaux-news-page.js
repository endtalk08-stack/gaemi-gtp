/* Marketaux news test page.
   It is mounted only inside the existing right-panel dashboard view. */
(function () {
  'use strict';

  const CATEGORIES = ['전체', '증시', '종목', '경제지표', '에너지', '연준', '일정', '투자의견', '실적발표'];
  let selectedCategory = '전체';
  let requestId = 0;
  let feeds = null;

  function makeElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function renderMessage(root, message) {
    const status = makeElement('div', 'marketaux-news__status', message);
    root.replaceChildren(status);
  }

  function openSourceArticle(url) {
    if (!url) return;
    window.open(url, '_blank', 'noopener,noreferrer');
  }

  function renderItems(root, items) {
    const list = makeElement('div', 'marketaux-news__list');
    if (!items.length) {
      list.appendChild(makeElement('div', 'marketaux-news__status', '표시할 뉴스가 없습니다.'));
    }

    items.forEach(item => {
      const article = makeElement('article', 'marketaux-news__item');
      const link = makeElement('button', 'marketaux-news__article');
      link.type = 'button';
      link.addEventListener('click', () => openSourceArticle(item.url));

      const meta = makeElement('div', 'marketaux-news__meta');
      meta.append(
        makeElement('span', 'marketaux-news__category', item.category || '증시'),
        makeElement('span', 'marketaux-news__source', item.source || 'Marketaux'),
        makeElement('span', 'marketaux-news__time', item.display_datetime || '')
      );

      link.append(
        meta,
        makeElement('div', 'marketaux-news__title', item.title || '제목 없는 기사')
      );

      if (item.description) {
        link.appendChild(makeElement('div', 'marketaux-news__description', item.description));
      }

      article.appendChild(link);
      list.appendChild(article);
    });
    root.replaceChildren(list);
  }

  function getItems(category) {
    if (!feeds) return [];
    if (category !== '전체') return feeds[category] || [];
    return CATEGORIES.slice(1).flatMap(feedCategory => feeds[feedCategory] || []);
  }

  async function load(root) {
    const currentRequest = ++requestId;
    renderMessage(root, '뉴스를 불러오는 중입니다.');

    try {
      const response = await fetch('/marketaux/news-feed', {
        headers: { Accept: 'application/json' },
      });
      const payload = await response.json();
      if (currentRequest !== requestId) return;

      if (!response.ok || !payload.ok) {
        const message = payload.error === 'marketaux_not_configured'
          ? 'Marketaux 연결을 준비 중입니다.'
          : '뉴스를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.';
        renderMessage(root, message);
        return;
      }
      feeds = payload.feeds && typeof payload.feeds === 'object' ? payload.feeds : {};
      renderItems(root, getItems(selectedCategory));
    } catch (_) {
      if (currentRequest === requestId) {
        renderMessage(root, '뉴스를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.');
      }
    }
  }

  function mount(root) {
    if (!root) return;
    root.replaceChildren();

    const page = makeElement('section', 'marketaux-news');
    const categories = makeElement('div', 'marketaux-news__categories');
    const results = makeElement('div', 'marketaux-news__results');

    CATEGORIES.forEach(category => {
      const button = makeElement('button', `marketaux-news__filter${category === selectedCategory ? ' is-active' : ''}`, category);
      button.type = 'button';
      button.addEventListener('click', () => {
        if (selectedCategory === category) return;
        selectedCategory = category;
        categories.querySelectorAll('.marketaux-news__filter').forEach(filter => {
          filter.classList.toggle('is-active', filter.textContent === selectedCategory);
        });
        if (feeds) renderItems(results, getItems(selectedCategory));
      });
      categories.appendChild(button);
    });

    page.append(categories, results);
    root.appendChild(page);
    load(results);
  }

  window.GaemiGTPMarketauxNews = { mount };
})();
