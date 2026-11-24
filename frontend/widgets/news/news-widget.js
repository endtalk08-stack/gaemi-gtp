/* Native News widget. UI modeled on the user-supplied compact news HTML, no iframe/API or DB. */
(function () {
  'use strict';
  const CATEGORIES = ['전체','종목','업종·섹터','실적 발표','실적 전망','증권사 평가','계약·수주','제품·기술','정책·규제','연준·금리','경제지표'];
  let items = [];
  let query = '';
  let selected = '전체';
  let detailId = null;
  let visible = 5;
  const escape = value => String(value == null ? '' : value)
    .replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')
    .replaceAll('"','&quot;').replaceAll("'",'&#039;');
  function widget() { return document.querySelector('[data-central-widget-id="news-feed"]'); }
  function normalize(raw,index) {
    if (!raw || typeof raw.title !== 'string' || !raw.title.trim()) return null;
    const category = String(raw.category || raw.cat || '종목');
    return {
      id: String(raw.id ?? raw.url ?? index), category,
      title: raw.title.trim(), summary: String(raw.summary || raw.description || raw.body || ''),
      time: String(raw.time || ''), published_at: String(raw.published_at || raw.publishedAt || ''),
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
  function currentItems() { return items; }
  function matches(item) {
    const c=selected === '전체' || item.category === selected;
    const q=query.trim().toLowerCase();
    return c && (!q || [item.title,item.summary,item.source,item.category,...(item.tickers||[])].join(' ').toLowerCase().includes(q));
  }
  function renderList(host) {
    const matchesAll=currentItems().filter(matches);
    const rows=matchesAll.slice(0,visible);
    host.innerHTML = `
      <div class="gnw-search">
        <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="8"></circle><path d="m21 21-4.3-4.3"></path></svg>
        <input type="search" data-gnw-search placeholder="검색어를 입력하세요" aria-label="뉴스 검색" value="${escape(query)}">
        <button type="button" class="gnw-close" data-central-widget-remove="news-feed" aria-label="뉴스 위젯 닫기" title="닫기"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12"></path></svg></button>
      </div>
      <div class="gnw-categories" role="group" aria-label="뉴스 분류">
        ${CATEGORIES.map(c=>`<button type="button" data-gnw-cat="${escape(c)}" class="gnw-category${c===selected?' is-active':''}" aria-pressed="${c===selected?'true':'false'}">${escape(c)}</button>`).join('')}
      </div>
      <div class="gnw-list">
        ${rows.map(item=>`<button type="button" class="gnw-item" data-gnw-open="${escape(item.id)}">
          <div class="gnw-meta"><span class="gnw-tag">${escape(item.category)}</span><span class="gnw-source">${escape(item.source)}</span></div>
          <div class="gnw-title">${escape(item.title)}</div>
          ${item.summary ? `<p class="gnw-summary">${escape(item.summary)}</p>` : ''}
          <time class="gnw-time">${escape(timeText(item))}</time>
        </button>`).join('')}
      </div>
      ${matchesAll.length>visible ? '<button type="button" class="gnw-more" data-gnw-more>더보기</button>' : ''}
    `;
    const search=host.querySelector('[data-gnw-search]');
    search?.addEventListener('input',e=>{
      query=e.target.value;
      visible=5;
      const list=host.querySelector('.gnw-list');
      const filtered=currentItems().filter(matches);
      if(!list) return;
      // Do not remount the search input while the user is typing.
      list.innerHTML=filtered.slice(0,visible).map(item=>`<button type="button" class="gnw-item" data-gnw-open="${escape(item.id)}">
        <div class="gnw-meta"><span class="gnw-tag">${escape(item.category)}</span><span class="gnw-source">${escape(item.source)}</span></div>
        <div class="gnw-title">${escape(item.title)}</div>
        ${item.summary ? `<p class="gnw-summary">${escape(item.summary)}</p>` : ''}
        <time class="gnw-time">${escape(timeText(item))}</time>
      </button>`).join('');
      host.querySelector('[data-gnw-more]')?.remove();
      if(filtered.length>visible) list.insertAdjacentHTML('afterend','<button type="button" class="gnw-more" data-gnw-more>더보기</button>');
    });
  }
  function renderDetail(host) {
    const item=currentItems().find(x=>x.id===detailId);
    if(!item){detailId=null;renderList(host);return;}
    const chips=(arr)=>arr?.length ? arr.map(x=>`<span class="gnw-chip">${escape(x)}</span>`).join('') : '';
    host.innerHTML=`
      <button type="button" class="gnw-back" data-gnw-back aria-label="뉴스 목록으로 돌아가기">←</button>
      <div class="gnw-detail-card">
        <div class="gnw-meta"><span class="gnw-tag">${escape(item.category)}</span><time class="gnw-time">${escape(timeText(item))}</time></div>
        <h3 class="gnw-detail-title">${escape(item.title)}</h3>
        <div class="gnw-detail-source">${escape(item.source)}</div>
        ${item.summary ? `<p class="gnw-detail-summary">${escape(item.summary)}</p>` : ''}
      </div>
      ${item.issues?.length ? `<section class="gnw-detail-section"><h4>관련 이슈</h4><div class="gnw-chips">${chips(item.issues)}</div></section>` : ''}
      ${item.tickers?.length ? `<section class="gnw-detail-section"><h4>관련 종목</h4><div class="gnw-chips">${chips(item.tickers)}</div></section>` : ''}
      ${item.industries?.length ? `<section class="gnw-detail-section"><h4>관련 산업·테마</h4><div class="gnw-chips">${chips(item.industries)}</div></section>` : ''}
      ${item.url ? `<a class="gnw-source-link" href="${escape(item.url)}" target="_blank" rel="noopener noreferrer">기사 원문 ↗</a>` : ''}
    `;
  }
  function render() {
    const host=widget()?.querySelector('[data-gnw-root]');
    if(!host)return;
    if(detailId !== null)renderDetail(host);else renderList(host);
  }
  function mount() { render(); }
  function setItems(raw) {
    items=(Array.isArray(raw)?raw:[]).map(normalize).filter(Boolean).sort((a,b)=>(Date.parse(b.published_at)||0)-(Date.parse(a.published_at)||0));
    detailId=null;selected='전체';query='';visible=5;render();
  }
  document.addEventListener('click',e=>{
    const host=e.target.closest('[data-gnw-root]');
    if(!host)return;
    const cat=e.target.closest('[data-gnw-cat]');
    if(cat){ selected=cat.dataset.gnwCat;visible=5;render();return;}
    const open=e.target.closest('[data-gnw-open]');
    if(open){detailId=open.dataset.gnwOpen;render();return;}
    if(e.target.closest('[data-gnw-back]')){detailId=null;render();return;}
    if(e.target.closest('[data-gnw-more]')){visible+=5;render();return;}
  });
  window.GaemiGTPNewsWidget={mount,setItems};
}());