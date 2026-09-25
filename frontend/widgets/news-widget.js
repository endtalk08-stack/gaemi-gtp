/* gaemiGTP News Widget — live / direct DOM
   - 독립 뉴스 탭 없음
   - iframe 없음: 오른쪽 패널 리사이즈를 방해하지 않음
   - 본문 기존 뉴스/재료와 분리
   - /news 데이터만 사용
   - "뉴스를 불러오는 중..." 문구 없음
*/
(function () {
  'use strict';

  const INIT = 5;
  const MAX_VISIBLE = 10;
  const HEADLINE_PER_PAGE = 3;
  const CATEGORIES = ['전체', '증시', '종목', '경제지표', '에너지', '연준', '일정', '투자의견', '실적발표'];
  const CACHE_TTL = 120000;

  const memoryCache = new Map();
  const pending = new Map();
  const stateByRoot = new WeakMap();

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (m) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;',
    }[m]));
  }

  function ensureStyle() {
    if (document.getElementById('gaemiNewsWidgetStyle')) return;

    const style = document.createElement('style');
    style.id = 'gaemiNewsWidgetStyle';
    style.textContent = `
      .gnw{--gnw-card:#1e1f20;--gnw-hover:#282a2c;--gnw-text:#f2f2f2;--gnw-sub:#8e918f;--gnw-faint:#71717a;--gnw-active:#2b3a5a;--gnw-active-text:#8ab4f8;width:100%;min-width:0;height:100%;min-height:0;color:var(--gnw-text);display:flex;flex-direction:column;overflow:hidden}
      .gnw *{box-sizing:border-box}
      .gnw button,.gnw input{font:inherit}
      .gnw-main,.gnw-detail{width:100%;min-width:0;height:100%;min-height:0;overflow:auto;padding:8px 2px 4px}
      .gnw-detail[hidden],.gnw-main[hidden]{display:none!important}
      .gnw-search{height:38px;display:flex;align-items:center;gap:8px;background:var(--gnw-card);border-radius:9px;padding:0 11px;margin-bottom:10px}
      .gnw-search svg{width:15px;height:15px;stroke:var(--gnw-sub);fill:none;stroke-width:2;flex:0 0 auto}
      .gnw-search input{flex:1;min-width:0;background:transparent;border:0!important;outline:0!important;color:var(--gnw-sub);font-size:11px}
      .gnw-cats{display:flex;gap:5px;overflow-x:auto;scrollbar-width:none;margin-bottom:12px}
      .gnw-cats::-webkit-scrollbar{display:none}
      .gnw-cat{flex:0 0 auto;border:0!important;outline:0!important;background:var(--gnw-card);color:var(--gnw-sub);padding:5px 9px;border-radius:7px;font-size:9px;font-weight:800;cursor:pointer}
      .gnw-cat.is-active{background:var(--gnw-active);color:var(--gnw-active-text)}
      .gnw-section-head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:7px}
      .gnw-section-title{font-size:11px;font-weight:800;color:#d4d4d4}
      .gnw-counter{font-size:9px;color:var(--gnw-faint)}
      .gnw-headline-wrap{display:grid;grid-template-columns:22px minmax(0,1fr) 22px;gap:5px;align-items:center}
      .gnw-arrow{width:22px;height:22px;border:0!important;border-radius:50%;background:transparent;color:var(--gnw-sub);cursor:pointer;display:flex;align-items:center;justify-content:center;padding:0}
      .gnw-arrow:disabled{opacity:.18;cursor:default}
      .gnw-arrow svg{width:13px;height:13px;stroke:currentColor;fill:none;stroke-width:2.4}
      .gnw-track{display:grid;grid-template-columns:1fr;gap:5px;min-width:0}
      .gnw-headline{min-height:44px;background:var(--gnw-card);border:0;border-radius:8px;padding:8px 10px;display:flex;align-items:center;text-align:left;cursor:pointer;min-width:0;width:100%}
      .gnw-headline:hover,.gnw-item:hover,.gnw-more:hover{background:var(--gnw-hover)}
      .gnw-headline-title{min-width:0;color:var(--gnw-sub);font-size:10px;font-weight:800;line-height:1.35;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
      .gnw-dots{display:flex;justify-content:center;gap:4px;margin:7px 0 11px}
      .gnw-dot{width:4px;height:4px;border-radius:50%;background:#3a3a3a}
      .gnw-dot.is-active{width:13px;border-radius:3px;background:#8ab4f8}
      .gnw-list-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:6px}
      .gnw-list-title{font-size:11px;font-weight:800;color:#d4d4d4}
      .gnw-list{display:flex;flex-direction:column}
      .gnw-item{height:58px;width:100%;background:var(--gnw-card);border:0;border-radius:8px;padding:7px 9px;margin-bottom:5px;display:grid;grid-template-columns:minmax(0,1fr) auto;grid-template-rows:auto auto;column-gap:8px;row-gap:5px;align-items:center;overflow:hidden;text-align:left;cursor:pointer;color:inherit}
      .gnw-meta-left{grid-column:1;grid-row:1;min-width:0;font-size:9px;color:var(--gnw-sub)}
      .gnw-tag{display:inline-block;background:#282a2c;color:#a0a0a0;padding:2px 5px;border-radius:4px;font-weight:800}
      .gnw-meta-right{grid-column:2;grid-row:1;font-size:9px;color:var(--gnw-sub);white-space:nowrap;text-align:right;max-width:150px;overflow:hidden;text-overflow:ellipsis}
      .gnw-title{grid-column:1/3;grid-row:2;min-width:0;color:var(--gnw-sub);font-size:10px;font-weight:800;line-height:1.35;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .gnw-more{width:100%;height:34px;border:0!important;border-radius:8px;background:var(--gnw-card);color:#c8c8c8;font-size:10px;font-weight:800;cursor:pointer;margin-top:1px}
      .gnw-empty{padding:24px 10px;text-align:center;color:var(--gnw-faint);font-size:10px}
      .gnw-detail-back{border:0;background:transparent;color:var(--gnw-sub);padding:4px 0 10px;cursor:pointer;font-size:10px;font-weight:800}
      .gnw-detail-meta{font-size:9px;color:var(--gnw-sub);margin-bottom:8px}
      .gnw-detail-title{font-size:14px;line-height:1.45;font-weight:800;color:#d7d7d7;margin-bottom:10px}
      .gnw-detail-source{font-size:10px;color:var(--gnw-sub);margin-bottom:16px}
      .gnw-original{width:100%;height:38px;border:0;border-radius:8px;background:var(--gnw-card);color:#d4d4d4;font-size:10px;font-weight:800;cursor:pointer}
      .gnw-original:hover{background:var(--gnw-hover)}
      @container (max-width:420px){
        .gnw-main,.gnw-detail{padding-top:4px}
        .gnw-meta-right{max-width:110px}
        .gnw-headline-wrap{grid-template-columns:18px minmax(0,1fr) 18px}
        .gnw-arrow{width:18px;height:18px}
      }
    `;
    document.head.appendChild(style);
  }

  function cacheKey(category, query) {
    return `${category}::${String(query || '').trim().toLowerCase()}`;
  }

  function readSessionCache(key) {
    try {
      const raw = sessionStorage.getItem(`gaemi.news.${key}`);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (!parsed || !Array.isArray(parsed.items)) return null;
      return parsed;
    } catch (_) {
      return null;
    }
  }

  function writeSessionCache(key, items) {
    try {
      sessionStorage.setItem(`gaemi.news.${key}`, JSON.stringify({ at: Date.now(), items }));
    } catch (_) {}
  }

  async function requestNews(category, query) {
    const key = cacheKey(category, query);
    const now = Date.now();
    const cached = memoryCache.get(key);

    if (cached && now - cached.at < CACHE_TTL) return cached.items;
    if (pending.has(key)) return pending.get(key);

    const task = (async () => {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 3500);
      try {
        const url = `/news?category=${encodeURIComponent(category)}&q=${encodeURIComponent(query || '')}&limit=${MAX_VISIBLE}`;
        const response = await fetch(url, {
          headers: { 'Accept': 'application/json' },
          signal: controller.signal,
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const payload = await response.json();
        const items = Array.isArray(payload.items) ? payload.items : [];
        memoryCache.set(key, { at: Date.now(), items });
        writeSessionCache(key, items);
        return items;
      } finally {
        clearTimeout(timer);
        pending.delete(key);
      }
    })();

    pending.set(key, task);
    return task;
  }

  function buildShell(root) {
    root.innerHTML = `
      <section class="gnw" data-gnw>
        <div class="gnw-main" data-gnw-main>
          <div class="gnw-search">
            <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
            <input type="search" data-gnw-search placeholder="뉴스 검색">
          </div>

          <div class="gnw-cats" data-gnw-cats>
            ${CATEGORIES.map((cat, index) => `<button type="button" class="gnw-cat${index === 0 ? ' is-active' : ''}" data-category="${cat}">${cat}</button>`).join('')}
          </div>

          <div class="gnw-section-head">
            <div class="gnw-section-title">주요뉴스</div>
            <div class="gnw-counter" data-gnw-counter></div>
          </div>

          <div class="gnw-headline-wrap">
            <button type="button" class="gnw-arrow" data-gnw-prev aria-label="이전 주요뉴스">
              <svg viewBox="0 0 24 24"><polyline points="15 18 9 12 15 6"></polyline></svg>
            </button>
            <div class="gnw-track" data-gnw-track></div>
            <button type="button" class="gnw-arrow" data-gnw-next aria-label="다음 주요뉴스">
              <svg viewBox="0 0 24 24"><polyline points="9 18 15 12 9 6"></polyline></svg>
            </button>
          </div>
          <div class="gnw-dots" data-gnw-dots></div>

          <div class="gnw-list-head">
            <div class="gnw-list-title">뉴스</div>
          </div>
          <div class="gnw-list" data-gnw-list></div>
          <button type="button" class="gnw-more" data-gnw-more hidden>더보기</button>
        </div>

        <div class="gnw-detail" data-gnw-detail hidden></div>
      </section>
    `;
  }

  function renderHeadlines(state) {
    const { root, items } = state;
    const headlineItems = items.slice(0, MAX_VISIBLE);
    const total = Math.max(1, Math.ceil(headlineItems.length / HEADLINE_PER_PAGE));

    if (state.page >= total) state.page = 0;

    const start = state.page * HEADLINE_PER_PAGE;
    const slice = headlineItems.slice(start, start + HEADLINE_PER_PAGE);

    const track = root.querySelector('[data-gnw-track]');
    const counter = root.querySelector('[data-gnw-counter]');
    const dots = root.querySelector('[data-gnw-dots]');
    const prev = root.querySelector('[data-gnw-prev]');
    const next = root.querySelector('[data-gnw-next]');

    counter.textContent = headlineItems.length ? `${state.page + 1} / ${total}` : '';
    prev.disabled = state.page === 0 || !headlineItems.length;
    next.disabled = state.page >= total - 1 || !headlineItems.length;

    track.innerHTML = slice.map((item, index) => `
      <button type="button" class="gnw-headline" data-headline-index="${start + index}">
        <span class="gnw-headline-title">${escapeHtml(item.title)}</span>
      </button>
    `).join('');

    dots.innerHTML = headlineItems.length
      ? Array.from({ length: total }, (_, index) => `<span class="gnw-dot${index === state.page ? ' is-active' : ''}"></span>`).join('')
      : '';

    track.querySelectorAll('[data-headline-index]').forEach((button) => {
      button.addEventListener('click', () => {
        const item = headlineItems[Number(button.dataset.headlineIndex)];
        if (item) showDetail(state, item);
      });
    });
  }

  function renderList(state) {
    const list = state.root.querySelector('[data-gnw-list]');
    const more = state.root.querySelector('[data-gnw-more]');

    if (!state.items.length) {
      list.innerHTML = state.failed ? '<div class="gnw-empty">뉴스를 가져오지 못했습니다.</div>' : '';
      more.hidden = true;
      return;
    }

    const visibleItems = state.items.slice(0, state.visible);
    list.innerHTML = visibleItems.map((item, index) => `
      <button type="button" class="gnw-item" data-news-index="${index}">
        <span class="gnw-meta-left"><span class="gnw-tag">${escapeHtml(item.category || '증시')}</span></span>
        <span class="gnw-meta-right">${escapeHtml(item.source || '출처 확인')}${item.display_datetime ? ` · ${escapeHtml(item.display_datetime)}` : ''}</span>
        <span class="gnw-title">${escapeHtml(item.title)}</span>
      </button>
    `).join('');

    list.querySelectorAll('[data-news-index]').forEach((button) => {
      button.addEventListener('click', () => {
        const item = visibleItems[Number(button.dataset.newsIndex)];
        if (item) showDetail(state, item);
      });
    });

    if (state.items.length <= INIT) {
      more.hidden = true;
    } else {
      more.hidden = false;
      more.textContent = state.visible > INIT
        ? '접기'
        : `더보기 (${Math.min(MAX_VISIBLE, state.items.length) - INIT}개 더)`;
    }
  }

  function render(state) {
    renderHeadlines(state);
    renderList(state);
  }

  function showDetail(state, item) {
    const main = state.root.querySelector('[data-gnw-main]');
    const detail = state.root.querySelector('[data-gnw-detail]');
    const href = item.original_link || item.link || '';

    detail.innerHTML = `
      <button type="button" class="gnw-detail-back" data-gnw-back>← 뉴스로 돌아가기</button>
      <div class="gnw-detail-meta">${escapeHtml(item.category || '증시')}${item.display_datetime ? ` · ${escapeHtml(item.display_datetime)}` : ''}</div>
      <div class="gnw-detail-title">${escapeHtml(item.title)}</div>
      <div class="gnw-detail-source">${escapeHtml(item.source || '출처 확인')}</div>
      <button type="button" class="gnw-original" data-gnw-original ${href ? '' : 'disabled'}>원문 보기</button>
    `;

    main.hidden = true;
    detail.hidden = false;
    detail.scrollTop = 0;

    detail.querySelector('[data-gnw-back]').addEventListener('click', () => {
      detail.hidden = true;
      main.hidden = false;
    });

    detail.querySelector('[data-gnw-original]').addEventListener('click', () => {
      if (href) window.open(href, '_blank', 'noopener,noreferrer');
    });
  }

  async function load(state, { allowStale = true } = {}) {
    const key = cacheKey(state.category, state.query);
    state.failed = false;
    state.visible = INIT;
    state.page = 0;

    if (allowStale) {
      const cached = memoryCache.get(key) || readSessionCache(key);
      if (cached && Array.isArray(cached.items) && cached.items.length) {
        state.items = cached.items;
        render(state);
      }
    }

    try {
      const items = await requestNews(state.category, state.query);
      state.items = items;
      state.failed = false;
      render(state);
    } catch (_) {
      if (!state.items.length) {
        state.failed = true;
        render(state);
      }
    }
  }

  function bind(state) {
    const root = state.root;
    let searchTimer = null;

    root.querySelector('[data-gnw-cats]').addEventListener('click', (event) => {
      const button = event.target.closest('[data-category]');
      if (!button) return;

      root.querySelectorAll('.gnw-cat').forEach((el) => el.classList.remove('is-active'));
      button.classList.add('is-active');

      state.category = button.dataset.category;
      state.query = '';
      root.querySelector('[data-gnw-search]').value = '';
      state.items = [];
      load(state);
    });

    root.querySelector('[data-gnw-search]').addEventListener('input', (event) => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {
        state.query = event.target.value.trim();
        state.items = [];
        load(state);
      }, 180);
    });

    root.querySelector('[data-gnw-prev]').addEventListener('click', () => {
      if (state.page > 0) {
        state.page -= 1;
        renderHeadlines(state);
      }
    });

    root.querySelector('[data-gnw-next]').addEventListener('click', () => {
      const total = Math.ceil(Math.min(MAX_VISIBLE, state.items.length) / HEADLINE_PER_PAGE);
      if (state.page < total - 1) {
        state.page += 1;
        renderHeadlines(state);
      }
    });

    root.querySelector('[data-gnw-more]').addEventListener('click', () => {
      state.visible = state.visible > INIT ? INIT : Math.min(MAX_VISIBLE, state.items.length);
      renderList(state);
    });
  }

  function mount(root) {
    if (!root) return;

    ensureStyle();

    if (stateByRoot.has(root)) {
      render(stateByRoot.get(root));
      return;
    }

    buildShell(root);

    const state = {
      root,
      category: '전체',
      query: '',
      items: [],
      visible: INIT,
      page: 0,
      failed: false,
    };

    stateByRoot.set(root, state);
    bind(state);

    const stale = readSessionCache(cacheKey('전체', ''));
    if (stale && Array.isArray(stale.items) && stale.items.length) {
      state.items = stale.items;
      render(state);
    }

    load(state);
  }

  function openNewsWidget() {
    if (window.GaemiGTPRightPanelTabs && typeof window.GaemiGTPRightPanelTabs.setActiveTab === 'function') {
      window.GaemiGTPRightPanelTabs.setActiveTab('dashboard');
    }

    if (window.GaemiGTPDashboard && typeof window.GaemiGTPDashboard.openWidget === 'function') {
      window.GaemiGTPDashboard.openWidget('news');
      return;
    }

    if (
      document.body.classList.contains('right-panel-closed') &&
      typeof window.toggleRightPanel === 'function'
    ) {
      window.toggleRightPanel();
    }
  }

  window.GaemiGTPNews = { mount, open: openNewsWidget };
  window.GaemiGTPWidgets = window.GaemiGTPWidgets || {};
  window.GaemiGTPWidgets.news = { mount, render: mount };
  window.openGaemiNews = openNewsWidget;
})();
