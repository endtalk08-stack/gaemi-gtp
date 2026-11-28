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
      ${item.summary ? `<p class="gnw-summary">${escape(item.summary)}</p>` : ''}
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
  let aiTestToken = '';
  let aiTestStocks = [];
  let aiTestPrompt = '';
  let aiTestSelectedSymbol = '';
  let aiTestResult = null;
  let aiTestStatus = '관리자 인증 후 현재 거래대금 TOP20을 불러오세요.';
  const aiTestBackend = window.location.hostname === 'gaemigtp-main.pages.dev' || window.location.hostname.endsWith('github.io') ? 'https://gaemi-gtp.onrender.com' : window.location.origin;
  function aiTestPanel() {
    const options = aiTestStocks.map(row => '<option value="' + escape(row.symbol) + '"' + (row.symbol === aiTestSelectedSymbol ? ' selected' : '') + '>' + escape(row.rank + '위 · ' + row.name + ' (' + row.symbol + ')') + '</option>').join('');
    let preview = '';
    if (aiTestResult) {
      preview = '<div class="gnw-ai-test-preview"><div class="gnw-ai-test-preview-label">뉴스 위젯 표시 미리보기 · 운영 R2 미저장</div><strong>' + escape(aiTestResult.headline || ((aiTestResult.stock || {}).name || '') + ' 분석 결과') + '</strong>' + (aiTestResult.lines || []).slice(0,2).map(line => '<p>' + escape(line) + '</p>').join('') + ((aiTestResult.keywords || []).length ? '<div class="gnw-ai-test-tags">' + aiTestResult.keywords.map(k => '<span>#' + escape(k) + '</span>').join('') + '</div>' : '') + '<small>' + escape((aiTestResult.stock || {}).symbol || '') + ' · 기사 ' + escape(aiTestResult.article_count) + '건 · 토큰 ' + escape(aiTestResult.tokens == null ? '미확인' : aiTestResult.tokens) + ' · ' + escape(aiTestResult.model || '') + '</small></div>';
    }
    return '<section class="gnw-ai-test" aria-label="미국 거래대금 TOP20 AI 분석 테스트"><div class="gnw-ai-test-head"><strong>TOP20 AI 분석 테스트</strong><span>선택한 1종목만 실제 뉴스·본문·AI 분석</span></div>' + '<label class="gnw-ai-test-label">관리자 테스트 비밀번호</label><input type="password" data-gnw-ai-test-token autocomplete="off" placeholder="기존 AI_TEST_TOKEN" aria-label="관리자 테스트 비밀번호" value="' + escape(aiTestToken) + '">' + '<div class="gnw-ai-test-actions"><button type="button" data-gnw-ai-test-load>현재 거래대금 TOP20 불러오기</button><span data-gnw-ai-test-status role="status">' + escape(aiTestStatus) + '</span></div>' + '<label class="gnw-ai-test-label">테스트 종목</label><select data-gnw-ai-test-symbol aria-label="테스트 종목">' + (options || '<option value="">먼저 TOP20을 불러오세요</option>') + '</select>' + '<label class="gnw-ai-test-label">시스템 프롬프트 · 수정 가능</label><textarea data-gnw-ai-test-prompt rows="5" maxlength="6000" placeholder="TOP20을 불러오면 기존 운영 프롬프트가 표시됩니다.">' + escape(aiTestPrompt) + '</textarea>' + '<div class="gnw-ai-test-actions"><button type="button" data-gnw-ai-test-run' + (aiTestStocks.length ? '' : ' disabled') + '>선택 종목 AI 분석 테스트 실행</button></div>' + preview + '</section>';
  }
  async function aiTestRequest(path, payload) {
    const response = await fetch(aiTestBackend + path, { method: payload ? 'POST' : 'GET', cache: 'no-store', headers: { 'Authorization': 'Bearer ' + aiTestToken, ...(payload ? {'Content-Type':'application/json'} : {}) }, body: payload ? JSON.stringify(payload) : undefined });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok) throw new Error(data.error || ('HTTP ' + response.status));
    return data;
  }
  async function loadAiTestTop20(host) {
    aiTestToken = host.querySelector('[data-gnw-ai-test-token]')?.value.trim() || '';
    if (!aiTestToken) { aiTestStatus = '관리자 테스트 비밀번호를 입력해 주세요.'; render(); return; }
    aiTestStatus = '현재 TOP20과 기존 프롬프트를 불러오는 중...'; render();
    try { const pair = await Promise.all([aiTestRequest('/api/us-news-ai-test/top20'), aiTestRequest('/api/us-news-ai-test/config')]); aiTestStocks = pair[0].items || []; aiTestPrompt = pair[1].system_prompt || ''; aiTestSelectedSymbol = aiTestStocks[0]?.symbol || ''; aiTestResult = null; aiTestStatus = aiTestStocks.length + '개 종목을 불러왔어요. 테스트할 종목을 선택하세요.'; }
    catch (error) { aiTestStatus = error.message === 'unauthorized_or_disabled' ? '인증 실패: AI_TEST_TOKEN과 AI_TEST_ENABLED를 확인해 주세요.' : '불러오기 실패: ' + error.message; }
    render();
  }
  async function runAiTest(host) {
    aiTestToken = host.querySelector('[data-gnw-ai-test-token]')?.value.trim() || aiTestToken;
    aiTestSelectedSymbol = host.querySelector('[data-gnw-ai-test-symbol]')?.value || '';
    aiTestPrompt = host.querySelector('[data-gnw-ai-test-prompt]')?.value || '';
    if (!aiTestToken || !aiTestSelectedSymbol) { aiTestStatus = '비밀번호와 테스트 종목을 확인해 주세요.'; render(); return; }
    const button = host.querySelector('[data-gnw-ai-test-run]'); if (button) button.disabled = true;
    aiTestStatus = '실제 뉴스 수집과 AI 분석 실행 중입니다. 선택한 종목 1개만 분석합니다...'; aiTestResult = null; render();
    try { aiTestResult = await aiTestRequest('/api/us-news-ai-test/run', {symbol: aiTestSelectedSymbol, system_prompt: aiTestPrompt}); aiTestStatus = aiTestResult.status === 'ok' ? '분석 완료 · 미리보기 결과는 운영 뉴스와 R2에 저장되지 않았어요.' : '분석 결과: ' + aiTestResult.status + ' · 최신 뉴스가 없으면 AI 호출은 생략됩니다.'; }
    catch (error) { aiTestStatus = '테스트 실패: ' + error.message; }
    render();
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
      ${selected===AI_CATEGORY ? aiTestPanel() : ''}
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
    if(e.target.closest('[data-gnw-ai-test-load]')) { loadAiTestTop20(host); return; }
    if(e.target.closest('[data-gnw-ai-test-run]')) { runAiTest(host); return; }
    const cat=e.target.closest('[data-gnw-cat]');
    if(cat){
      selected=cat.dataset.gnwCat;visible=Number.MAX_SAFE_INTEGER;render();
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