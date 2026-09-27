/* gaemiGTP right-panel news page — Naver + Google general news engine. */
(function () {
  'use strict';

  const CATEGORIES = ['전체', '증시', '종목', '경제지표', '에너지', '연준', '일정', '투자의견', '실적발표'];
  const BACKEND_URL = window.location.hostname.endsWith('github.io') ? 'https://gaemi-gtp.onrender.com' : '';
  let selectedCategory = '전체';
  let requestId = 0;

  function makeElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function renderMessage(root, message) { root.replaceChildren(makeElement('div', 'marketaux-news__status', message)); }
  function closeArticleModal() { document.querySelector('.news-article-modal')?.remove(); document.body.classList.remove('news-modal-open'); }

  function openArticleModal(item) {
    closeArticleModal();
    const overlay = makeElement('div', 'news-article-modal');
    const dialog = makeElement('section', 'news-article-modal__dialog');
    dialog.setAttribute('role', 'dialog'); dialog.setAttribute('aria-modal', 'true'); dialog.setAttribute('aria-label', item.title || '뉴스 기사');
    const close = makeElement('button', 'news-article-modal__close', '×');
    close.type = 'button'; close.setAttribute('aria-label', '닫기'); close.addEventListener('click', closeArticleModal);
    const title = makeElement('h2', 'news-article-modal__title', item.title || '제목 없는 기사');
    const meta = makeElement('div', 'news-article-modal__meta');
    meta.append(makeElement('span', '', item.source || '뉴스'), makeElement('span', '', item.display_datetime || ''));
    const body = makeElement('div', 'news-article-modal__body');
    body.appendChild(makeElement('p', item.description ? '' : 'news-article-modal__empty', item.description || '원문 기사로 이동해 전체 내용을 확인할 수 있습니다.'));
    const actions = makeElement('div', 'news-article-modal__actions');
    const original = makeElement('a', 'news-article-modal__original', '원문 기사 보기');
    original.href = item.original_link || item.link || '#'; original.target = '_blank'; original.rel = 'noopener noreferrer'; actions.appendChild(original);
    dialog.append(close, title, meta, body, actions); overlay.appendChild(dialog);
    overlay.addEventListener('click', event => { if (event.target === overlay) closeArticleModal(); });
    const onKeydown = event => { if (event.key === 'Escape') { closeArticleModal(); document.removeEventListener('keydown', onKeydown); } };
    document.addEventListener('keydown', onKeydown); document.body.appendChild(overlay); document.body.classList.add('news-modal-open'); close.focus();
  }

  function renderItems(root, items) {
    const list = makeElement('div', 'marketaux-news__list');
    if (!items.length) list.appendChild(makeElement('div', 'marketaux-news__status', '표시할 뉴스가 없습니다.'));
    items.forEach(item => {
      const article = makeElement('article', 'marketaux-news__item');
      const button = makeElement('button', 'marketaux-news__article'); button.type = 'button'; button.addEventListener('click', () => openArticleModal(item));
      const meta = makeElement('div', 'marketaux-news__meta');
      meta.append(makeElement('span', 'marketaux-news__category', item.category || selectedCategory), makeElement('span', 'marketaux-news__source', item.source || item.provider || '뉴스'), makeElement('span', 'marketaux-news__time', item.display_datetime || ''));
      button.append(meta, makeElement('div', 'marketaux-news__title', item.title || '제목 없는 기사'));
      if (item.description) button.appendChild(makeElement('div', 'marketaux-news__description', item.description));
      article.appendChild(button); list.appendChild(article);
    });
    root.replaceChildren(list);
  }

  async function load(root) {
    const currentRequest = ++requestId; renderMessage(root, '뉴스를 불러오는 중입니다.');
    try {
      const params = new URLSearchParams({ category: selectedCategory, limit: '20' });
      const response = await fetch(`${BACKEND_URL}/news?${params.toString()}`, { headers: { Accept: 'application/json' } });
      const payload = await response.json();
      if (currentRequest !== requestId) return;
      if (!response.ok || !Array.isArray(payload.items)) { renderMessage(root, '뉴스를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.'); return; }
      renderItems(root, payload.items);
    } catch (_) { if (currentRequest === requestId) renderMessage(root, '뉴스를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.'); }
  }

  function mount(root) {
    if (!root) return;
    root.replaceChildren();
    const page = makeElement('section', 'marketaux-news'); const categories = makeElement('div', 'marketaux-news__categories'); const results = makeElement('div', 'marketaux-news__results');
    CATEGORIES.forEach(category => {
      const button = makeElement('button', `marketaux-news__filter${category === selectedCategory ? ' is-active' : ''}`, category); button.type = 'button';
      button.addEventListener('click', () => { if (selectedCategory === category) return; selectedCategory = category; categories.querySelectorAll('.marketaux-news__filter').forEach(filter => filter.classList.toggle('is-active', filter.textContent === selectedCategory)); load(results); });
      categories.appendChild(button);
    });
    page.append(categories, results); root.appendChild(page); load(results);
  }

  window.GaemiGTPMarketauxNews = { mount };
})();
