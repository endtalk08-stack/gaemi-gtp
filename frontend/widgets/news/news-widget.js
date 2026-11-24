/* Native News widget. UI modeled on the user-supplied compact news HTML, no iframe/API or DB. */
(function () {
  'use strict';
  const CATEGORIES = ['전체','종목','업종·섹터','실적 발표','실적 전망','증권사 평가','계약·수주','제품·기술','정책·규제','연준·금리','경제지표'];
  let items = [];
  let loaded = false;
  let loading = false;
  let loadError = false;
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
    const published_at = String(raw.published_at || raw.publishedAt || raw.pubDate || raw.date || '').trim();
    const publishedDate = new Date(published_at);
    if (!published_at || Number.isNaN(publishedDate.getTime())) return null;
    const body = String(raw.body || raw.article_body || raw.content || '');
    const summary = String(raw.list_excerpt || raw.summary || raw.description || raw.excerpt || body.slice(0,220));
    const urlValue = String(raw.url || raw.originallink || raw.link || '').trim();
    let url = '';
    try {
      const parsed = new URL(urlValue);
      if (parsed.protocol === 'https:' || parsed.protocol === 'http:') url = parsed.href;
    } catch (_) {}
    const tickerValues = Array.isArray(raw.tickers) ? raw.tickers : (Array.isArray(raw.symbols) ? raw.symbols : []);
    const issueValues = [
      ...(Array.isArray(raw.issues) ? raw.issues : []),
      ...(Array.isArray(raw.event_matches) ? raw.event_matches : []),
      ...(Array.isArray(raw.market_event_matches) ? raw.market_event_matches : [])
    ];
    const industryValues = [
      ...(Array.isArray(raw.industries) ? raw.industries : []),
      ...(Array.isArray(raw.industry_matches) ? raw.industry_matches : [])
    ];
    const labels = values => [...new Set(values.map(x => typeof x === 'string' ? x : String(x?.label || '')).filter(Boolean))].slice(0,20);
    const category = String(raw.event_category?.code === 'guidance'
      ? '실적 전망'
      : (raw.event_category?.label || raw.category || raw.cat || raw.market_event_category?.label || '종목'));
    return {
      id: String(raw.id ?? url ?? index),
      category,
      title: raw.title.trim(),
      summary,
      body,
      published_at,
      source: String(raw.source || raw.publisher || ''),
      url,
      tickers: tickerValues.filter(x => typeof x === 'string').slice(0,20),
      issues: labels(issueValues),
      industries: labels(industryValues)
    };
  }
  function timeText(item) {
    const date = new Date(item.published_at);
    if (Number.isNaN(date.getTime())) return '';
    return new Intl.DateTimeFormat('ko-KR', {
      timeZone: 'Asia/Seoul', hour: '2-digit', minute: '2-digit', hour12: false
    }).format(date);
  }
  function currentItems() { return items; }
  function matches(item) {
    const c=selected === '전체' || item.category === selected;
    const q=query.trim().toLowerCase();
    return c && (!q || [item.title,item.summary,item.body,item.source,item.category,...(item.tickers||[])].join(' ').toLowerCase().includes(q));
  }
  function listTimeText(item) { return timeText(item); }
  function renderListItem(item) {
    const time = listTimeText(item);
    return `<button type="button" class="gnw-item" data-gnw-open="${escape(item.id)}">
      <div class="gnw-list-row">
        <div class="gnw-list-heading">
          ${time ? `<time class="gnw-list-time" datetime="${escape(item.published_at)}">${escape(time)}</time>` : ''}
          <span class="gnw-title">${escape(item.title)}</span>
        </div>
      </div>
      <p class="gnw-summary">${escape(item.summary)}</p>
    </button>`;
  }
  function renderList(host) {
    const matchesAll=currentItems().filter(matches);
    const rows=matchesAll.slice(0,visible);
    const emptyMessage = loading ? '뉴스를 불러오는 중…' : (loadError ? '뉴스 데이터를 불러오지 못했습니다' : '표시할 뉴스가 없습니다');
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
        ${rows.length ? rows.map(renderListItem).join('') : `<div class="gnw-empty">${escape(emptyMessage)}</div>`}
      </div>
    `;
    const search=host.querySelector('[data-gnw-search]');
    search?.addEventListener('input',e=>{
      query=e.target.value;
      visible=Number.MAX_SAFE_INTEGER;
      const list=host.querySelector('.gnw-list');
      const filtered=currentItems().filter(matches);
      if(!list) return;
      const filteredRows=filtered.slice(0,visible);
      list.innerHTML=filteredRows.map(renderListItem).join('') || '<div class="gnw-empty"><div class="gnw-empty-mark">⌕</div><div>검색 결과가 없습니다</div></div>';
    });
  }
  async function loadItems() {
    if (loading || loaded) return;
    loading = true;
    loadError = false;
    render();
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 10000);
    try {
      const response = await fetch('/news/latest.json', {
        method: 'GET', cache: 'no-store', credentials: 'same-origin', signal: controller.signal
      });
      if (!response.ok) throw new Error('news_feed_http_' + response.status);
      const data = await response.json();
      if (!data || data.ok !== true || !Array.isArray(data.items)) throw new Error('news_feed_schema_invalid');
      const next = data.items.map((raw,index)=>normalize(raw,index)).filter(Boolean);
      if (!next.length) throw new Error('news_feed_has_no_items_with_publication_time');
      items = next.sort((a,b)=>Date.parse(b.published_at)-Date.parse(a.published_at));
      loaded = true;
      visible = Number.MAX_SAFE_INTEGER;
      detailId = null;
    } catch (error) {
      loadError = true;
      console.error('News R2 feed load failed:', error?.message || error);
    } finally {
      window.clearTimeout(timeout);
      loading = false;
      render();
    }
  }
  function renderDetail(host) {
    const item=currentItems().find(x=>x.id===detailId);
    if(!item){detailId=null;renderList(host);return;}
    const chips=(arr)=>arr?.length ? arr.map(x=>`<span class="gnw-chip">${escape(x)}</span>`).join('') : '';
    const paragraphs=String(item.body||'').split(/\n\s*\n/).map(x=>x.trim()).filter(Boolean);
    const bodyHtml=paragraphs.length
      ? `<div class="gnw-article-body"><h4>기사 본문</h4>${paragraphs.map(p=>`<p>${escape(p).replaceAll('\\n','<br>')}</p>`).join('')}</div>`
      : (item.summary ? `<div class="gnw-article-body"><p>${escape(item.summary)}</p></div>` : '');
    const stockRows=(item.tickers||[]).map(ticker=>{
      const active=favoriteTickers.has(ticker);
      return `<div class="gnw-stock-item">
        <span class="gnw-stock-name">${escape(ticker)}</span>
        <button type="button" class="gnw-favorite${active?' is-active':''}" data-gnw-favorite="${escape(ticker)}" aria-label="${escape(ticker)} 관심종목" aria-pressed="${active?'true':'false'}">
          <svg viewBox="0 0 24 24" aria-hidden="true"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
        </button>
      </div>`;
    }).join('');
    host.innerHTML=`
      <button type="button" class="gnw-back" data-gnw-back aria-label="뉴스 목록으로 돌아가기">←</button>
      <div class="gnw-detail-card">
        <h3 class="gnw-detail-title">${escape(item.title)}</h3>
        <div class="gnw-meta">
          ${item.source ? `<span class="gnw-detail-source">${escape(item.source)}</span>` : '<span></span>'}
          <time class="gnw-time" datetime="${escape(item.published_at)}">${escape(timeText(item))}</time>
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
  function mount() { render(); if (!loaded && !loading) void loadItems(); }
  function setItems(raw) {
    items=(Array.isArray(raw)?raw:[]).map(normalize).filter(Boolean).sort((a,b)=>Date.parse(b.published_at)-Date.parse(a.published_at));
    loaded=true;loadError=false;detailId=null;selected='전체';query='';visible=Number.MAX_SAFE_INTEGER;render();
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
    if(cat){ selected=cat.dataset.gnwCat;visible=Number.MAX_SAFE_INTEGER;render();return;}
    const open=e.target.closest('[data-gnw-open]');
    if(open){detailId=open.dataset.gnwOpen;render();return;}
    if(e.target.closest('[data-gnw-back]')){detailId=null;render();return;}
  });
  window.GaemiGTPNewsWidget={mount,setItems};
}());