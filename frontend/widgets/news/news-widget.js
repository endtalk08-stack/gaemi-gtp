/* Native News widget. UI modeled on the user-supplied compact news HTML. */
(function () {
  'use strict';
  const AI_CATEGORY = '분석';
  const CATEGORIES = ['전체',AI_CATEGORY,'종목','업종·섹터','실적 발표','실적 전망','증권사 평가','계약·수주','제품·기술','정책·규제','연준·금리','경제지표'];
  // Real articles only: setItems() supplies news; 개미지티피 articles come from the AI loader.
  let items = [];
  const favoriteTickers = new Set();
  let query = '';
  let selected = '전체';
  let detailId = null;
  let visible = Number.MAX_SAFE_INTEGER;
  const escape = value => String(value == null ? '' : value)
    .replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')
    .replaceAll('"','&quot;').replaceAll("'",'&#039;');
  function widget() { return document.querySelector('[data-central-widget-id="news-feed"]'); }
  function normalize(raw,index) {
    if (!raw || typeof raw.title !== 'string' || !raw.title.trim()) return null;
    const category = String(raw.category || raw.cat || '종목');
    return {
      id: String(raw.id ?? raw.url ?? index), category,
      title: raw.title.trim(),
      summary: String(raw.summary || raw.description || (raw.body ? String(raw.body).slice(0,220) : '')),
      body: String(raw.article_body || raw.content || raw.body || ''),
      time: String(raw.time || ''), published_at: String(raw.published_at || raw.publishedAt || raw.pubDate || raw.date || ''),
      source: String(raw.source || raw.publisher || ''),
      url: typeof raw.url === 'string' && /^https:\/\//.test(raw.url) ? raw.url : '',
      tickers: Array.isArray(raw.tickers) ? raw.tickers.filter(x=>typeof x === 'string').slice(0,20) : [],
      issues: Array.isArray(raw.issues) ? raw.issues.filter(x=>typeof x === 'string').slice(0,20) : [],
      industries: Array.isArray(raw.industries) ? raw.industries.filter(x=>typeof x === 'string').slice(0,20) : []
    };
  }
  function timeText(item) {
    if (item.time) return item.time;
    if (!item.published_at) return '';
    const date=new Date(item.published_at);
    if (Number.isNaN(date.getTime())) return '';
    return new Intl.DateTimeFormat('ko-KR',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false,timeZone:'Asia/Seoul'}).format(date);
  }
  // Real articles: setItems() news plus translated US macro headlines (연준·백악관·경제지표).
  const macro = () => window.GaemiGTPUsMacroNews;
  function currentItems() {
    const extra = macro()?.newsItems() || [];
    return extra.length ? [...items, ...extra].sort((a,b)=>(Date.parse(b.published_at)||0)-(Date.parse(a.published_at)||0)) : items;
  }
  function matches(item) {
    const c=selected === '전체' || item.category === selected;
    const q=query.trim().toLowerCase();
    return c && (!q || [item.title,item.summary,item.body,item.source,item.category,...(item.tickers||[])].join(' ').toLowerCase().includes(q));
  }
  function listTimeText(item) {
    const candidates = [item.published_at, item.publishedAt, item.pubDate, item.date];
    for (const value of candidates) {
      if (!value) continue;
      const date = new Date(value);
      if (!Number.isNaN(date.getTime())) {
        return new Intl.DateTimeFormat('ko-KR', {
          timeZone: 'Asia/Seoul', hour: '2-digit', minute: '2-digit', hour12: false
        }).format(date);
      }
    }
    const raw = String(item.time || '').trim();
    const clock = raw.match(/(?:^|\\s)([01]?\\d|2[0-3]):([0-5]\\d)(?:\\s|$)/);
    return clock ? clock[1].padStart(2, '0') + ':' + clock[2] : '21:00';
  }
  function renderListItem(item) {
    const time = listTimeText(item);
    return `<button type="button" class="gnw-item" data-gnw-open="${escape(item.id)}">
      <div class="gnw-list-row">
        <div class="gnw-list-heading">
          ${time ? `<time class="gnw-list-time">${escape(time)}</time>` : ''}
          <span class="gnw-title">${escape(item.title)}</span>
        </div>
      </div>
      <p class="gnw-summary">${escape(item.summary)}</p>
    </button>`;
  }
  // ---- 분석 tab: 개미지티피 articles on the daily US TOP20, shown like any news ----
  const ai = () => window.GaemiGTPUsNewsAi;
  function aiItems() {
    const q=query.trim().toLowerCase();
    return (ai()?.newsItems() || []).filter(item => !q || [item.title,item.body,...item.issues,...item.tickers]
      .join(' ').toLowerCase().includes(q));
  }
  function renderAiListItem(item) {
    const time=listTimeText(item);
    const title = escape(item.title);
    return `<button type="button" class="gnw-item gnw-ai-item" data-gnw-open="${escape(item.id)}">
      <div class="gnw-list-row">
        <div class="gnw-list-heading">
          ${time ? `<time class="gnw-list-time">${escape(time)}</time>` : ''}
          <span class="gnw-title">${title}</span>
        </div>
      </div>
      <p class="gnw-summary">${escape(item.summary)}</p>
    </button>`;
  }
  const stamp = item => Date.parse(item.published_at) || 0;
  function allRows() {
    return [...currentItems().filter(matches), ...aiItems()].sort((a,b)=>stamp(b)-stamp(a));
  }
  function renderAllList() {
    const rows=allRows().slice(0,visible);
    return rows.map(item=>item.ai ? renderAiListItem(item) : renderListItem(item)).join('');
  }
  function renderAiList() {
    const rows=aiItems();
    if (rows.length) return rows.map(renderAiListItem).join('');
    // No article yet: leave the list blank (search keeps its usual message).
    return query.trim()
      ? '<div class="gnw-empty"><div class="gnw-empty-mark">⌕</div><div>검색 결과가 없습니다</div></div>'
      : '';
  }
  let aiRefreshTimer = null;
  function refreshAi() {
    const loads=[ai()?.load?.(), macro()?.load?.()].filter(Boolean);
    Promise.all(loads).then(() => {
      // Do not remount the list while the user is typing a search.
      if (detailId===null && widget() && !document.activeElement?.matches?.('[data-gnw-search]')) render();
    });
  }
  function syncAiRefresh() {
    const active = Boolean(widget());
    if (active && !aiRefreshTimer) aiRefreshTimer = setInterval(refreshAi, 60000);
    if (!active && aiRefreshTimer) { clearInterval(aiRefreshTimer); aiRefreshTimer = null; }
  }

  function renderList(host) {
    const matchesAll=currentItems().filter(matches);
    const rows=matchesAll.slice(0,visible);
    host.innerHTML = `
      <div class="gnw-search">
        <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="8"></circle><path d="m21 21-4.3-4.3"></path></svg>
        <input type="search" data-gnw-search placeholder="검색어를 입력하세요" aria-label="뉴스 검색" value="${escape(query)}">
        <button type="button" class="gnw-close" data-central-widget-remove="news-feed" onclick="window.GaemiGTPWidgetDock.remove('news-feed')" aria-label="뉴스 위젯 닫기" title="닫기"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12"></path></svg></button>
      </div>
      <div class="gnw-categories" role="group" aria-label="뉴스 분류">
        ${CATEGORIES.map(c=>`<button type="button" data-gnw-cat="${escape(c)}" class="gnw-category${c===selected?' is-active':''}" aria-pressed="${c===selected?'true':'false'}">${escape(c)}</button>`).join('')}
      </div>
      <div class="gnw-list">
        ${selected===AI_CATEGORY ? renderAiList() : selected==='전체' ? renderAllList() : rows.map(renderListItem).join('')}
      </div>
    `;
    const search=host.querySelector('[data-gnw-search]');
    search?.addEventListener('input',e=>{
      query=e.target.value;
      visible=Number.MAX_SAFE_INTEGER;
      const list=host.querySelector('.gnw-list');
      const filtered=currentItems().filter(matches);
      if(!list) return;
      if(selected===AI_CATEGORY){list.innerHTML=renderAiList();return;}
      if(selected==='전체'){list.innerHTML=renderAllList() || (query.trim() ? '<div class="gnw-empty"><div class="gnw-empty-mark">⌕</div><div>검색 결과가 없습니다</div></div>' : '');return;}
      // Do not remount the search input while the user is typing.
      const filteredRows=filtered.slice(0,visible);
      list.innerHTML=filteredRows.map(renderListItem).join('') || '<div class="gnw-empty"><div class="gnw-empty-mark">⌕</div><div>검색 결과가 없습니다</div></div>';
    });
  }
  function renderDetail(host) {
    // 분석 articles use the same detail view as every other news item.
    const item=String(detailId).startsWith('ai:')
      ? (ai()?.newsItems() || []).find(x=>x.id===detailId)
      : currentItems().find(x=>x.id===detailId);
    if(!item){detailId=null;renderList(host);return;}
    const chips=(arr)=>arr?.length ? arr.map(x=>`<span class="gnw-chip">${escape(x)}</span>`).join('') : '';
    const paragraphs=String(item.body||'').split(/\n\s*\n/).map(x=>x.trim()).filter(Boolean);
    const bodyHtml=paragraphs.length
      ? `<div class="gnw-article-body"><h4>기사 본문</h4>${paragraphs.map(p=>`<p>${escape(p).replaceAll('\\n','<br>')}</p>`).join('')}</div>`
      : (item.summary ? `<div class="gnw-article-body"><p>${escape(item.summary)}</p></div>` : '');
    const stockRows=(item.tickers||[]).map(ticker=>{
      const active=favoriteTickers.has(ticker);
      const intro=ai()?.introFor?.(ticker) || '';
      return `<div class="gnw-stock-entry"><div class="gnw-stock-item">
        <span class="gnw-stock-name">${escape(ticker)}</span>
        <button type="button" class="gnw-favorite${active?' is-active':''}" data-gnw-favorite="${escape(ticker)}" aria-label="${escape(ticker)} 관심종목" aria-pressed="${active?'true':'false'}">
          <svg viewBox="0 0 24 24" aria-hidden="true"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
        </button>
      </div>${intro ? `<p class="gnw-stock-intro">${escape(intro)}</p>` : ''}</div>`;
    }).join('');
    host.innerHTML=`
      <button type="button" class="gnw-back" data-gnw-back aria-label="뉴스 목록으로 돌아가기">←</button>
      <div class="gnw-detail-card">
        <h3 class="gnw-detail-title">${escape(item.title)}</h3>
        <div class="gnw-meta">
          ${item.source ? `<span class="gnw-detail-source">${escape(item.source)}</span>` : '<span></span>'}
          <time class="gnw-time">${escape(timeText(item))}</time>
        </div>
      </div>
      ${bodyHtml}
      ${item.issues?.length ? `<section class="gnw-detail-section"><h4>관련 이슈</h4><div class="gnw-chips">${chips(item.issues)}</div></section>` : ''}
      ${item.tickers?.length ? `<section class="gnw-detail-section"><h4>관련 종목</h4><div class="gnw-stock-list">${stockRows}</div></section>` : ''}
      ${item.industries?.length ? `<section class="gnw-detail-section"><h4>관련 산업·테마</h4><div class="gnw-chips">${chips(item.industries)}</div></section>` : ''}
      ${item.url ? `<a class="gnw-source-link" href="${escape(item.url)}" target="_blank" rel="noopener noreferrer">기사 원문 ↗</a>` : ''}
    `;
  }
  function render() {
    const host=widget()?.querySelector('[data-gnw-root]');
    if(!host)return;
    if(detailId !== null)renderDetail(host);else renderList(host);
  }
  function mount() { render(); refreshAi(); syncAiRefresh(); ai()?.loadIntros?.(); }
  // Intros arrive after the first paint; refresh an open detail view.
  window.addEventListener('gaemi:us-company-intros',()=>{ if(detailId !== null) render(); });
  function setItems(raw) {
    items=(Array.isArray(raw)?raw:[]).map(normalize).filter(Boolean).sort((a,b)=>(Date.parse(b.published_at)||0)-(Date.parse(a.published_at)||0));
    detailId=null;selected='전체';query='';visible=Number.MAX_SAFE_INTEGER;render();
  }
  document.addEventListener('click',e=>{
    const host=e.target.closest('[data-gnw-root]');
    if(!host)return;
    const favorite=e.target.closest('[data-gnw-favorite]');
    if(favorite){
      const ticker=favorite.dataset.gnwFavorite;
      if(favoriteTickers.has(ticker))favoriteTickers.delete(ticker);else favoriteTickers.add(ticker);
      const active=favoriteTickers.has(ticker);
      favorite.classList.toggle('is-active',active);
      favorite.setAttribute('aria-pressed',active?'true':'false');
      return;
    }
    const cat=e.target.closest('[data-gnw-cat]');
    if(cat){
      selected=cat.dataset.gnwCat;visible=5;render();
      refreshAi();
      syncAiRefresh();
      return;
    }
    const open=e.target.closest('[data-gnw-open]');
    if(open){detailId=open.dataset.gnwOpen;render();return;}
    if(e.target.closest('[data-gnw-back]')){detailId=null;render();return;}
  });
  window.GaemiGTPNewsWidget={mount,setItems};
}());