/* Native News widget. UI modeled on the user-supplied compact news HTML, no iframe/API or DB. */
(function () {
  'use strict';
  const AI_CATEGORY = '분석';
  const CATEGORIES = ['전체',AI_CATEGORY,'종목','업종·섹터','실적 발표','실적 전망','증권사 평가','계약·수주','제품·기술','정책·규제','연준·금리','경제지표'];
  // Original news_compact_v6_850_news_card_source_time(4).html preview rows.
  // These 19 records are the source HTML's mock content, NOT current verified news.
  const SOURCE_PREVIEW_ITEMS = [
    {
      "id": "101",
      "category": "연준",
      "source": "한국경제",
      "time": "방금 전",
      "title": "연준 의장 긴급 기자회견… 시장 예상 뒤집어",
      "tickers": [
        "$SPY"
      ],
      "issues": [
        "#연준",
        "#긴급"
      ],
      "industries": [
        "금융",
        "채권"
      ],
      "url": "https://www.hankyung.com"
    },
    {
      "id": "102",
      "category": "관세",
      "source": "연합뉴스",
      "time": "1분 전",
      "title": "중국, 미국산 반도체 관세 25% 부과 발표",
      "tickers": [
        "$NVDA",
        "$AMD"
      ],
      "issues": [
        "#관세",
        "#반도체"
      ],
      "industries": [
        "반도체",
        "무역"
      ],
      "url": "https://www.yna.co.kr"
    },
    {
      "id": "1",
      "category": "정부정책",
      "source": "한국경제",
      "time": "11:19",
      "title": "미중, AI·무역 협상 진전…'미중 AI 대화' 출범 합의",
      "tickers": [
        "$SPY",
        "$QQQ"
      ],
      "issues": [
        "#미중정상회담",
        "#AI협력"
      ],
      "industries": [
        "AI·데이터",
        "반도체"
      ],
      "url": "https://www.hankyung.com"
    },
    {
      "id": "9",
      "category": "주요지수",
      "source": "파이낸셜뉴스",
      "time": "15:42",
      "title": "나스닥 사상 최고치 경신… 기술주 랠리 이어져",
      "tickers": [
        "$QQQ"
      ],
      "issues": [
        "#나스닥",
        "#기술주"
      ],
      "industries": [
        "반도체",
        "소프트웨어"
      ],
      "url": "https://www.fnnews.com"
    },
    {
      "id": "4",
      "category": "종목",
      "source": "조선비즈",
      "time": "20:48",
      "title": "테슬라, 신형 모델 Y 생산 일정 6개월 앞당긴다",
      "tickers": [
        "$TSLA",
        "$RIVN"
      ],
      "issues": [
        "#테슬라",
        "#전기차"
      ],
      "industries": [
        "자동차",
        "2차전지"
      ],
      "url": "https://biz.chosun.com"
    },
    {
      "id": "5",
      "category": "종목",
      "source": "이데일리",
      "time": "19:22",
      "title": "애플, AI 탑재 신형 아이패드 다음 달 공개 예정",
      "tickers": [
        "$AAPL",
        "$TSM"
      ],
      "issues": [
        "#애플",
        "#AI"
      ],
      "industries": [
        "소프트웨어",
        "AI·데이터"
      ],
      "url": "https://www.edaily.co.kr"
    },
    {
      "id": "6",
      "category": "종목",
      "source": "머니투데이",
      "time": "18:05",
      "title": "엔비디아, 차세대 GPU 블랙웰 울트라 발표 임박",
      "tickers": [
        "$NVDA",
        "$AMD"
      ],
      "issues": [
        "#엔비디아",
        "#GPU"
      ],
      "industries": [
        "반도체",
        "AI·데이터"
      ],
      "url": "https://www.mt.co.kr"
    },
    {
      "id": "103",
      "category": "경제지표",
      "source": "매일경제",
      "time": "10분 전",
      "title": "미국 CPI 예상치 상회… 3.2% 기록",
      "tickers": [
        "$TLT"
      ],
      "issues": [
        "#CPI",
        "#물가"
      ],
      "industries": [
        "금융",
        "채권"
      ],
      "url": "https://www.mk.co.kr"
    },
    {
      "id": "104",
      "category": "경제지표",
      "source": "헤럴드경제",
      "time": "25분 전",
      "title": "한국 GDP 성장률 0.6%… 예상치 부합",
      "tickers": [],
      "issues": [
        "#GDP",
        "#성장률"
      ],
      "industries": [
        "경제",
        "지표"
      ],
      "url": "https://biz.heraldcorp.com"
    },
    {
      "id": "2",
      "category": "국제정세",
      "source": "한국일보",
      "time": "22:41",
      "title": "트럼프, 이란 대통령과 회담 가능성 열어둬",
      "tickers": [
        "$WTI",
        "$XOM"
      ],
      "issues": [
        "#중동정세",
        "#지정학적리스크"
      ],
      "industries": [
        "에너지",
        "정유"
      ],
      "url": "https://www.hankookilbo.com"
    },
    {
      "id": "7",
      "category": "에너지",
      "source": "서울경제",
      "time": "17:33",
      "title": "국제 유가 3% 급락… 중동 긴장 완화 기대감",
      "tickers": [
        "$WTI",
        "$CVX"
      ],
      "issues": [
        "#국제유가",
        "#중동정세"
      ],
      "industries": [
        "에너지",
        "정유"
      ],
      "url": "https://www.sedaily.com"
    },
    {
      "id": "3",
      "category": "연준",
      "source": "매일경제",
      "time": "21:15",
      "title": "연준 인사들, 금리 동결 시사… 인플레 둔화 속도 주시",
      "tickers": [
        "$TLT",
        "$SPY"
      ],
      "issues": [
        "#연준",
        "#금리동결"
      ],
      "industries": [
        "금융",
        "채권"
      ],
      "url": "https://www.mk.co.kr"
    },
    {
      "id": "8",
      "category": "금리·환율",
      "source": "헤럴드경제",
      "time": "16:11",
      "title": "일본은행, 예상대로 금리 동결… 엔화 약세 지속",
      "tickers": [
        "$JPY"
      ],
      "issues": [
        "#일본은행",
        "#엔화"
      ],
      "industries": [
        "금융",
        "환율"
      ],
      "url": "https://biz.heraldcorp.com"
    },
    {
      "id": "105",
      "category": "연준",
      "source": "연합뉴스",
      "time": "2시간 전",
      "title": "FOMC 회의 다음 주 개최… 금리 결정 임박",
      "tickers": [],
      "issues": [
        "#FOMC",
        "#금리"
      ],
      "industries": [
        "금융"
      ],
      "url": "https://www.yna.co.kr"
    },
    {
      "id": "106",
      "category": "일정",
      "source": "한국경제",
      "time": "3시간 전",
      "title": "엔비디아 GTC 컨퍼런스 3월 개최 예정",
      "tickers": [
        "$NVDA"
      ],
      "issues": [
        "#GTC",
        "#엔비디아"
      ],
      "industries": [
        "반도체",
        "AI·데이터"
      ],
      "url": "https://www.hankyung.com"
    },
    {
      "id": "10",
      "category": "투자의견",
      "source": "연합뉴스",
      "time": "14:18",
      "title": "비트코인 10만 달러 돌파… 기관 자금 유입 가속",
      "tickers": [
        "$COIN",
        "$MSTR"
      ],
      "issues": [
        "#비트코인",
        "#가상자산"
      ],
      "industries": [
        "가상자산",
        "핀테크"
      ],
      "url": "https://www.yna.co.kr"
    },
    {
      "id": "107",
      "category": "투자의견",
      "source": "머니투데이",
      "time": "4시간 전",
      "title": "골드만삭스, S&P500 목표가 6,200으로 상향",
      "tickers": [
        "$SPY",
        "$GS"
      ],
      "issues": [
        "#골드만",
        "#목표가"
      ],
      "industries": [
        "금융",
        "증시"
      ],
      "url": "https://www.mt.co.kr"
    },
    {
      "id": "108",
      "category": "실적발표",
      "source": "조선비즈",
      "time": "5시간 전",
      "title": "테슬라 4분기 실적 예상치 상회… 시간외 5% 급등",
      "tickers": [
        "$TSLA"
      ],
      "issues": [
        "#실적",
        "#테슬라"
      ],
      "industries": [
        "자동차"
      ],
      "url": "https://biz.chosun.com"
    },
    {
      "id": "109",
      "category": "실적발표",
      "source": "이데일리",
      "time": "6시간 전",
      "title": "애플, 아이폰 판매 호조로 사상 최대 매출",
      "tickers": [
        "$AAPL"
      ],
      "issues": [
        "#실적",
        "#애플"
      ],
      "industries": [
        "소프트웨어",
        "하드웨어"
      ],
      "url": "https://www.edaily.co.kr"
    }
  ];
  let items = SOURCE_PREVIEW_ITEMS.map((item,index)=>normalize(item,index));
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
  function currentItems() { return items; }
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
    ai()?.load()?.then(() => { if (selected===AI_CATEGORY && detailId===null) render(); });
  }
  function syncAiRefresh() {
    const active = selected===AI_CATEGORY && Boolean(widget());
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
        ${selected===AI_CATEGORY ? renderAiList() : rows.map(renderListItem).join('')}
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
  function mount() { render(); }
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
      if(selected===AI_CATEGORY) refreshAi();
      syncAiRefresh();
      return;
    }
    const open=e.target.closest('[data-gnw-open]');
    if(open){detailId=open.dataset.gnwOpen;render();return;}
    if(e.target.closest('[data-gnw-back]')){detailId=null;render();return;}
  });
  window.GaemiGTPNewsWidget={mount,setItems};
}());