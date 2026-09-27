/* Marketaux news test page.
   It is mounted only inside the existing right-panel dashboard view. */
(function () {
  'use strict';

  const CATEGORIES = ['전체', '증시', '종목', '경제지표', '에너지', '연준', '일정', '투자의견', '실적발표'];
  const BACKEND_URL = window.location.hostname.endsWith('github.io')
    ? 'https://gaemi-gtp.onrender.com'
    : '';
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

  function closeArticleModal() {
    const modal = document.querySelector('.news-article-modal');
    if (modal) modal.remove();
    document.body.classList.remove('news-modal-open');
  }

  function openArticleModal(item) {
    closeArticleModal();

    const overlay = makeElement('div', 'news-article-modal');
    const dialog = makeElement('section', 'news-article-modal__dialog');
    dialog.setAttribute('role', 'dialog');
    dialog.setAttribute('aria-modal', 'true');
    dialog.setAttribute('aria-label', item.title || '뉴스 기사');

    const close = makeElement('button', 'news-article-modal__close', '×');
    close.type = 'button';
    close.setAttribute('aria-label', '닫기');
    close.addEventListener('click', closeArticleModal);

    const title = makeElement('h2', 'news-article-modal__title', item.title || '제목 없는 기사');
    const meta = makeElement('div', 'news-article-modal__meta');
    meta.append(
      makeElement('span', '', item.source || 'Marketaux'),
      makeElement('span', '', item.display_datetime || '')
    );

    const body = makeElement('div', 'news-article-modal__body');
    if (item.description) {
      body.appendChild(makeElement('p', '', item.description));
    } else {
      body.appendChild(makeElement('p', 'news-article-modal__empty', '기사 요약 정보가 없습니다. 원문에서 전체 내용을 확인할 수 있습니다.'));
    }

    const actions = makeElement('div', 'news-article-modal__actions');
    const original = makeElement('a', 'news-article-modal__original', '원문 기사 보기');
    original.href = item.url || '#';
    original.target = '_blank';
    original.rel = 'noopener noreferrer';
    actions.appendChild(original);

    dialog.append(close, title, meta, body, actions);
    overlay.appendChild(dialog);
    overlay.addEventListener('click', event => {
      if (event.target === overlay) closeArticleModal();
    });
    document.addEventListener('keydown', function onKeydown(event) {
      if (event.key === 'Escape') {
        closeArticleModal();
        document.removeEventListener('keydown', onKeydown);
      }
    });

    document.body.appendChild(overlay);
    document.body.classList.add('news-modal-open');
    close.focus();
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
      link.addEventListener('click', () => openArticleModal(item));

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
      const response = await fetch(`${BACKEND_URL}/marketaux/news-feed`, {
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
