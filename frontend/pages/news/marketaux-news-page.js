/* Shared NAVER news view for the right panel. */
(function () {
  'use strict';

  const BACKEND_URL = window.location.hostname.endsWith('github.io')
    ? 'https://gaemi-gtp.onrender.com'
    : '';
  const MARKET_FILTERS = ['전체', '국내', '미국'];
  let requestId = 0;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function renderMessage(root, message) {
    root.replaceChildren(el('div', 'marketaux-news__status', message));
  }

  function closeArticleModal() {
    document.querySelector('.news-article-modal')?.remove();
    document.body.classList.remove('news-modal-open');
  }

  function unique(values) {
    return [...new Set(values.filter(Boolean))];
  }

  function fallbackIntelligence(item) {
    const text = `${item.title || ''} ${item.description || ''}`.toLowerCase();
    const rules = {
      issues: [
        ['금리·통화정책', ['금리', '연준', 'fomc', '파월']],
        ['물가·경제지표', ['cpi', 'pce', '물가', 'gdp', '고용']],
        ['실적발표', ['실적', '영업이익', '매출', 'earnings']],
        ['반도체 업황', ['반도체', 'hbm', '메모리', 'dram']],
        ['AI 투자', ['ai', '인공지능']],
        ['유가·에너지', ['유가', '원유', '천연가스', '에너지']],
        ['환율', ['환율', '달러', '원화']],
        ['정책·규제', ['정부', '정책', '규제', '법안']],
      ],
      stocks: [
        ['삼성전자', ['삼성전자']], ['SK하이닉스', ['sk하이닉스', '하이닉스']],
        ['NAVER', ['naver', '네이버']], ['현대차', ['현대차', '현대자동차']],
        ['기아', ['기아']], ['엔비디아', ['엔비디아', 'nvidia']],
        ['테슬라', ['테슬라', 'tesla']], ['애플', ['애플', 'apple']],
      ],
      themes: [
        ['반도체', ['반도체', 'hbm', 'dram', '메모리']], ['AI·소프트웨어', ['ai', '인공지능', '소프트웨어']],
        ['자동차·모빌리티', ['자동차', '현대차', '기아', '전기차']], ['2차전지', ['2차전지', '배터리']],
        ['에너지', ['유가', '원유', '에너지', '천연가스']], ['금융', ['은행', '증권', '보험', '금융']],
        ['바이오·헬스케어', ['바이오', '제약', '의료', '헬스케어']], ['인터넷·플랫폼', ['네이버', '카카오', '플랫폼']],
        ['방산', ['방산', '무기', '국방']], ['조선', ['조선', '선박']],
      ],
    };
    return Object.fromEntries(Object.entries(rules).map(([key, labels]) => [
      key, unique(labels.filter(([, words]) => words.some((word) => text.includes(word))).map(([label]) => label)),
    ]));
  }

  function intelligence(item) {
    const fallback = fallbackIntelligence(item);
    return {
      issues: Array.isArray(item.issues) ? item.issues : fallback.issues,
      stocks: Array.isArray(item.related_stocks) ? item.related_stocks : fallback.stocks,
      themes: Array.isArray(item.themes) ? item.themes : fallback.themes,
    };
  }

  function addIntelSection(parent, title, values, emptyText) {
    const section = el('section', 'news-article-modal__intel');
    section.appendChild(el('h3', 'news-article-modal__section-title', title));
    if (values.length) {
      const chips = el('div', 'news-article-modal__chips');
      values.forEach((value) => chips.appendChild(el('span', 'news-article-modal__chip', value)));
      section.appendChild(chips);
    } else {
      section.appendChild(el('p', 'news-article-modal__section-empty', emptyText));
    }
    parent.appendChild(section);
  }

  function openArticleModal(item) {
    closeArticleModal();
    const intel = intelligence(item);
    const overlay = el('div', 'news-article-modal');
    const dialog = el('section', 'news-article-modal__dialog');
    dialog.setAttribute('role', 'dialog');
    dialog.setAttribute('aria-modal', 'true');

    const close = el('button', 'news-article-modal__close', '×');
    close.type = 'button';
    close.addEventListener('click', closeArticleModal);

    const meta = el('div', 'news-article-modal__meta');
    meta.append(el('span', '', item.source || '뉴스'), el('span', '', item.display_datetime || ''));
    const content = el('section', 'news-article-modal__content');
    content.append(
      el('h3', 'news-article-modal__section-title', '내용 설명'),
      el('p', item.description ? 'news-article-modal__summary' : 'news-article-modal__section-empty', item.description || '제공된 기사 설명이 없습니다.'),
    );
    dialog.append(close, el('h2', 'news-article-modal__title', item.title || '제목 없는 기사'), meta, content);
    addIntelSection(dialog, '관련 이슈', intel.issues, '기사 제목과 설명에서 직접 연결되는 이슈를 찾지 못했습니다.');
    addIntelSection(dialog, '관련 종목', intel.stocks, '기사에서 직접 언급된 주요 종목이 없습니다.');
    addIntelSection(dialog, '관련 산업·테마', intel.themes, '기사에서 직접 연결되는 산업·테마를 찾지 못했습니다.');

    const actions = el('div', 'news-article-modal__actions');
    const original = el('a', 'news-article-modal__original', '원문 기사 보기');
    original.href = item.original_link || item.link || '#';
    original.target = '_blank';
    original.rel = 'noopener noreferrer';
    actions.appendChild(original);
    dialog.appendChild(actions);
    overlay.appendChild(dialog);
    overlay.addEventListener('click', (event) => { if (event.target === overlay) closeArticleModal(); });
    document.body.appendChild(overlay);
    document.body.classList.add('news-modal-open');
    close.focus();
  }

  function renderItems(root, items) {
    const list = el('div', 'marketaux-news__list');
    if (!items.length) list.appendChild(el('div', 'marketaux-news__status', '표시할 뉴스가 없습니다.'));
    items.forEach((item) => {
      const article = el('article', 'marketaux-news__item');
      const button = el('button', 'marketaux-news__article');
      button.type = 'button';
      button.addEventListener('click', () => openArticleModal(item));
      button.appendChild(el('div', 'marketaux-news__title', item.title || '제목 없는 기사'));
      if (item.description) button.appendChild(el('div', 'marketaux-news__description', item.description));
      const meta = el('div', 'marketaux-news__meta');
      meta.append(el('span', 'marketaux-news__source', item.source || item.provider || '뉴스'), el('span', 'marketaux-news__time', item.display_datetime || ''));
      button.appendChild(meta);
      article.appendChild(button);
      list.appendChild(article);
    });
    root.replaceChildren(list);
  }

  async function load(root, market) {
    const current = ++requestId;
    renderMessage(root, '뉴스를 불러오는 중입니다.');
    try {
      const params = new URLSearchParams({ category: '전체', market, limit: '20' });
      const response = await fetch(`${BACKEND_URL}/news?${params}`, { headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error('News request failed');
      const data = await response.json();
      if (current !== requestId) return;
      renderItems(root, Array.isArray(data.items) ? data.items : []);
    } catch (_) {
      if (current === requestId) renderMessage(root, '뉴스를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.');
    }
  }

  function mount(root) {
    if (!root) return;
    root.replaceChildren();
    let selectedMarket = '전체';
    const page = el('section', 'marketaux-news');
    const filters = el('div', 'marketaux-news__categories');
    const results = el('div', 'marketaux-news__results');
    const buttons = MARKET_FILTERS.map((market) => {
      const button = el('button', 'marketaux-news__filter', market);
      button.type = 'button';
      button.classList.toggle('is-active', market === selectedMarket);
      button.addEventListener('click', () => {
        if (selectedMarket === market) return;
        selectedMarket = market;
        buttons.forEach((candidate) => candidate.classList.toggle('is-active', candidate.textContent === market));
        load(results, selectedMarket);
      });
      filters.appendChild(button);
      return button;
    });
    page.append(filters, results);
    root.appendChild(page);
    load(results, selectedMarket);
  }

  window.GaemiGTPMarketauxNews = { mount };
}());
