/* gaemiGTP News Widget — layout only v1
   DATA CONNECTIONS: OFF
   - no fetch / XHR / WebSocket / EventSource
   - no /news call
   - no main-body news dependency
   - no external-link modal dependency
   - local demo data only, for layout completion and interaction testing
*/
(function () {
  'use strict';

  const INIT_VISIBLE = 5;
  const MAX_VISIBLE = 10;
  const HEADLINE_PER_PAGE = 3;
  const CATEGORIES = ['증시', '종목', '경제지표', '에너지', '연준', '일정', '투자의견', '실적발표'];

  const DEMO_ITEMS = [
    {
      id: 'demo-01',
      category: '연준',
      title: '연준 인사들, 금리 동결 시사… 인플레 둔화 속도 주시',
      source: '매일경제',
      display_datetime: '21:15',
      views: '18.2K',
      issues: ['#연준', '#금리동결'],
      stocks: [
        { symbol: '$TLT', name: 'iShares 20+ Year Treasury Bond ETF' },
        { symbol: '$SPY', name: 'SPDR S&P 500 ETF Trust' },
      ],
      themes: ['금융', '채권'],
    },
    {
      id: 'demo-02',
      category: '증시',
      title: '뉴욕증시, 기술주 중심 반등… 주요 지수 장중 상승',
      source: '연합뉴스',
      display_datetime: '20:58',
      views: '13.7K',
      issues: ['#뉴욕증시', '#기술주'],
      stocks: [
        { symbol: '$QQQ', name: 'Invesco QQQ Trust' },
        { symbol: '$NVDA', name: 'NVIDIA' },
      ],
      themes: ['미국증시', 'AI'],
    },
    {
      id: 'demo-03',
      category: '종목',
      title: '반도체 업황 기대감 확대… 메모리 가격 흐름에 관심',
      source: '한국경제',
      display_datetime: '20:42',
      views: '9.4K',
      issues: ['#반도체', '#메모리'],
      stocks: [
        { symbol: '005930', name: '삼성전자' },
        { symbol: '000660', name: 'SK하이닉스' },
      ],
      themes: ['반도체', 'AI인프라'],
    },
    {
      id: 'demo-04',
      category: '경제지표',
      title: '미국 소비자물가 발표 앞두고 시장 경계감 확대',
      source: '서울경제',
      display_datetime: '20:20',
      views: '8.8K',
      issues: ['#CPI', '#인플레이션'],
      stocks: [
        { symbol: '$DXY', name: 'US Dollar Index' },
        { symbol: '$TLT', name: 'iShares 20+ Year Treasury Bond ETF' },
      ],
      themes: ['매크로', '금리'],
    },
    {
      id: 'demo-05',
      category: '에너지',
      title: '국제유가 변동성 확대… 원유 재고와 중동 정세 주목',
      source: '머니투데이',
      display_datetime: '19:55',
      views: '7.6K',
      issues: ['#국제유가', '#원유재고'],
      stocks: [
        { symbol: '$XLE', name: 'Energy Select Sector SPDR Fund' },
        { symbol: '$CVX', name: 'Chevron' },
      ],
      themes: ['에너지', '정유'],
    },
    {
      id: 'demo-06',
      category: '일정',
      title: '이번 주 주요 경제 일정… 물가·고용·연준 발언 집중',
      source: '이데일리',
      display_datetime: '19:31',
      views: '6.9K',
      issues: ['#경제일정', '#고용'],
      stocks: [
        { symbol: '$SPY', name: 'SPDR S&P 500 ETF Trust' },
        { symbol: '$QQQ', name: 'Invesco QQQ Trust' },
      ],
      themes: ['매크로', '미국증시'],
    },
    {
      id: 'demo-07',
      category: '투자의견',
      title: '증권가, 대형 기술주 목표주가 잇따라 조정',
      source: '파이낸셜뉴스',
      display_datetime: '19:05',
      views: '5.2K',
      issues: ['#목표주가', '#투자의견'],
      stocks: [
        { symbol: '$AAPL', name: 'Apple' },
        { symbol: '$MSFT', name: 'Microsoft' },
      ],
      themes: ['빅테크', '미국증시'],
    },
    {
      id: 'demo-08',
      category: '실적발표',
      title: '주요 기업 실적 발표 시즌… 매출·가이던스에 시선',
      source: '조선비즈',
      display_datetime: '18:44',
      views: '4.7K',
      issues: ['#실적발표', '#가이던스'],
      stocks: [
        { symbol: '$AMZN', name: 'Amazon' },
        { symbol: '$META', name: 'Meta Platforms' },
      ],
      themes: ['실적', '빅테크'],
    },
    {
      id: 'demo-09',
      category: '종목',
      title: 'AI 데이터센터 투자 확대… 전력·냉각 관련주 관심',
      source: '전자신문',
      display_datetime: '18:22',
      views: '4.1K',
      issues: ['#데이터센터', '#AI인프라'],
      stocks: [
        { symbol: '$NVDA', name: 'NVIDIA' },
        { symbol: '$VRT', name: 'Vertiv' },
      ],
      themes: ['AI', '데이터센터'],
    },
    {
      id: 'demo-10',
      category: '증시',
      title: '아시아 증시 혼조… 환율과 외국인 수급이 변수',
      source: '뉴스1',
      display_datetime: '18:03',
      views: '3.8K',
      issues: ['#아시아증시', '#외국인수급'],
      stocks: [
        { symbol: 'KOSPI', name: '코스피' },
        { symbol: '$EWY', name: 'iShares MSCI South Korea ETF' },
      ],
      themes: ['국내증시', '환율'],
    },
  ];

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

  function searchIcon() {
    return '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>';
  }

  function eyeIcon() {
    return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z"></path><circle cx="12" cy="12" r="2.5"></circle></svg>';
  }

  function arrowLeftIcon() {
    return '<svg viewBox="0 0 24 24" aria-hidden="true"><polyline points="15 18 9 12 15 6"></polyline></svg>';
  }

  function arrowRightIcon() {
    return '<svg viewBox="0 0 24 24" aria-hidden="true"><polyline points="9 18 15 12 9 6"></polyline></svg>';
  }

  function externalIcon() {
    return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 5h5v5"></path><path d="M10 14 19 5"></path><path d="M19 13v6H5V5h6"></path></svg>';
  }

  function starIcon(filled) {
    return `<svg viewBox="0 0 24 24" aria-hidden="true"${filled ? ' class="is-filled"' : ''}><polygon points="12 2.8 14.8 8.5 21 9.4 16.5 13.8 17.6 20 12 17 6.4 20 7.5 13.8 3 9.4 9.2 8.5 12 2.8"></polygon></svg>`;
  }

  function ensureStyle() {
    if (document.getElementById('gaemiNewsLayoutOnlyStyle')) return;

    const style = document.createElement('style');
    style.id = 'gaemiNewsLayoutOnlyStyle';
    style.textContent = `
      .gnw{
        --gnw-bg:#131314;
        --gnw-card:#1E1F20;
        --gnw-card-2:#202124;
        --gnw-hover:#282a2c;
        --gnw-text:#f2f2f2;
        --gnw-sub:#8e918f;
        --gnw-faint:#6f7270;
        --gnw-line:#2a2c2f;
        --gnw-active:#2b3a5a;
        --gnw-active-text:#8ab4f8;
        width:100%;
        min-width:0;
        height:100%;
        min-height:0;
        container-type:inline-size;
        color:var(--gnw-text);
        font-family:Pretendard,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
      }
      .gnw *{box-sizing:border-box}
      .gnw button,.gnw input{font-family:inherit}
      .gnw button{color:inherit}
      .gnw svg{fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
      .gnw-main,.gnw-detail{
        width:100%;
        min-width:0;
        height:100%;
        min-height:0;
        overflow-y:auto;
        overflow-x:hidden;
        scrollbar-width:none;
      }
      .gnw-main::-webkit-scrollbar,.gnw-detail::-webkit-scrollbar{display:none}
      .gnw-main[hidden],.gnw-detail[hidden]{display:none!important}

      /* 대시보드 뉴스 슬롯과 바탕을 완전히 같은 색으로 맞춰 경계를 없앤다. */
      .dashboard-widget-slot[data-widget-slot="news"]{background:#131314!important;box-shadow:none!important;}
      .dashboard-widget-slot[data-widget-slot="news"] .dashboard-widget-slot__head{background:#131314!important;}
      .dashboard-widget-slot[data-widget-slot="news"] .dashboard-widget-slot__content{background:#131314!important;padding:0!important;}
      .dashboard-widget-slot[data-widget-slot="news"] .dashboard-widget-slot__mount{background:#131314!important;}
      .gnw-main,.gnw-detail{background:#131314!important;}
      .gnw-main-inner,.gnw-detail-inner{padding-left:0!important;padding-right:0!important;}

      /* 목록 화면 */
      .gnw-main-inner{width:100%;min-width:0;padding:0}
      .gnw-search{
        display:flex;
        align-items:center;
        gap:9px;
        background:var(--gnw-card);
        border-radius:10px;
        padding:12px 14px;
        margin-bottom:18px;
      }
      .gnw-search svg{width:15px;height:15px;color:var(--gnw-sub);flex:0 0 auto}
      .gnw-search input{
        flex:1;
        min-width:0;
        border:0!important;
        outline:0!important;
        background:transparent!important;
        color:var(--gnw-text);
        font-size:14px;
        font-weight:600;
      }
      .gnw-search input::placeholder{color:#70736f}
      .gnw-search-action{
        flex:0 0 auto;
        width:32px;
        height:32px;
        border:0!important;
        outline:0!important;
        background:transparent;
        color:#777a77;
        display:flex;
        align-items:center;
        justify-content:center;
        border-radius:50%;
        cursor:pointer;
      }
      .gnw-search-action:hover{background:#25272a;color:#c7c8c7}
      .gnw-search-action.is-active{color:#d8d8d8}
      .gnw-search-action svg{width:16px;height:16px}
      .gnw-search-action.is-active svg{fill:#9ea19e;stroke:#9ea19e}
      .gnw-cats{
        display:flex;
        align-items:center;
        flex-wrap:nowrap;
        gap:5px;
        overflow:visible;
        margin-bottom:24px;
        padding:0;
      }
      .gnw-cat{
        flex:0 0 auto;
        min-width:0;
        border:0!important;
        outline:0!important;
        background:#1e1f21;
        color:var(--gnw-sub);
        padding:7px 10px;
        border-radius:8px;
        font-size:12px;
        line-height:1;
        font-weight:750;
        white-space:nowrap;
        cursor:pointer;
      }
      .gnw-cat:hover{background:#1a1b1e}
      .gnw-cat.is-active{background:var(--gnw-active);color:var(--gnw-active-text)}

      .gnw-section-head{
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:10px;
        margin-bottom:9px;
      }
      .gnw-section-title{font-size:18px;font-weight:850;color:#d8d8d8}
      .gnw-counter{font-size:14px;color:var(--gnw-faint);white-space:nowrap}

      .gnw-headline-wrap{
        display:grid;
        grid-template-columns:32px minmax(0,1fr) 32px;
        align-items:center;
        gap:7px;
      }
      .gnw-arrow{
        width:32px;
        height:32px;
        padding:0;
        border:0!important;
        outline:0!important;
        background:transparent;
        color:#7c7f7d;
        display:flex;
        align-items:center;
        justify-content:center;
        border-radius:50%;
        cursor:pointer;
      }
      .gnw-arrow:hover{background:#1a1b1e;color:#c7c8c7}
      .gnw-arrow:disabled{opacity:.18;cursor:default;background:transparent}
      .gnw-arrow svg{width:15px;height:15px}
      .gnw-track{display:grid;grid-template-columns:1fr;gap:7px;min-width:0}
      .gnw-headline{
        width:100%;
        min-width:0;
        min-height:54px;
        border:0!important;
        outline:0!important;
        background:var(--gnw-card);
        border-radius:8px;
        padding:10px 14px;
        display:flex;
        align-items:center;
        text-align:left;
        cursor:pointer;
      }
      .gnw-headline:hover{background:var(--gnw-hover)}
      .gnw-headline-title{
        min-width:0;
        color:var(--gnw-sub);
        font-size:14px;
        line-height:1.4;
        font-weight:800;
        display:-webkit-box;
        -webkit-line-clamp:2;
        -webkit-box-orient:vertical;
        overflow:hidden;
      }
      .gnw-dots{
        min-height:16px;
        display:flex;
        align-items:center;
        justify-content:center;
        gap:5px;
        margin:8px 0 14px;
      }
      .gnw-dot{width:5px;height:5px;border-radius:999px;background:#383a3d}
      .gnw-dot.is-active{width:16px;background:#8ab4f8}

      .gnw-news-head{
        display:grid;
        grid-template-columns:auto minmax(0,1fr);
        align-items:center;
        gap:6px;
        margin-bottom:8px;
      }
      .gnw-news-title{font-size:18px;font-weight:850;color:#d8d8d8}
      .gnw-filters{
        display:flex;
        align-items:center;
        justify-content:flex-end;
        gap:7px;
        min-width:0;
      }
      .gnw-filter{
        min-height:30px;
        border:0!important;
        outline:0!important;
        border-radius:7px;
        background:var(--gnw-card);
        color:#777a77;
        padding:0 10px;
        font-size:12px;
        line-height:1;
        font-weight:750;
        white-space:nowrap;
        cursor:pointer;
      }
      .gnw-filter:hover{background:#242629;color:#aaa}
      .gnw-filter.gnw-filter-refresh{
        width:30px;
        min-width:30px;
        padding:0;
        font-size:13px;
      }
      .gnw-list{display:flex;flex-direction:column;min-width:0}
      .gnw-item{
        width:100%;
        height:68px;
        border:0!important;
        outline:0!important;
        background:var(--gnw-card);
        border-radius:8px;
        padding:9px 12px;
        margin-bottom:7px;
        overflow:hidden;
        cursor:pointer;
        display:grid;
        grid-template-columns:minmax(0,1fr) auto;
        grid-template-rows:auto auto;
        column-gap:12px;
        row-gap:6px;
        align-items:center;
        text-align:left;
      }
      .gnw-item:hover{background:var(--gnw-hover)}
      .gnw-meta-left{
        grid-column:1;
        grid-row:1;
        min-width:0;
        font-size:10px;
        color:var(--gnw-sub);
        overflow:hidden;
        text-overflow:ellipsis;
        white-space:nowrap;
      }
      .gnw-meta-right{
        grid-column:2;
        grid-row:1;
        font-size:10px;
        color:var(--gnw-sub);
        white-space:nowrap;
        text-align:right;
      }
      .gnw-tag{
        display:inline-flex;
        align-items:center;
        min-height:15px;
        padding:1px 5px;
        border-radius:4px;
        background:#282a2c;
        color:#a2a4a2;
        font-weight:800;
      }
      .gnw-title{
        grid-column:1;
        grid-row:2;
        min-width:0;
        color:var(--gnw-sub);
        font-size:13px;
        font-weight:800;
        line-height:1.35;
        white-space:nowrap;
        overflow:hidden;
        text-overflow:ellipsis;
      }
      .gnw-views{
        grid-column:2;
        grid-row:2;
        display:flex;
        align-items:center;
        justify-content:flex-end;
        gap:4px;
        font-size:10px;
        color:var(--gnw-sub);
        white-space:nowrap;
      }
      .gnw-views svg{width:13px;height:13px}
      .gnw-more{
        width:100%;
        border:0!important;
        outline:0!important;
        border-radius:8px;
        background:var(--gnw-card);
        color:var(--gnw-text);
        padding:15px;
        font-size:14px;
        font-weight:800;
        cursor:pointer;
        margin-top:1px;
      }
      .gnw-more:hover{background:var(--gnw-hover)}
      .gnw-no-result{
        min-height:120px;
        display:flex;
        align-items:center;
        justify-content:center;
        color:#6f7270;
        font-size:11px;
      }

      /* 상세 화면 */
      .gnw-detail-inner{
        width:min(100%,540px);
        min-width:0;
        margin:0 auto;
        padding:4px 0 18px;
      }
      .gnw-back{
        width:34px;
        height:34px;
        padding:0;
        border:0!important;
        outline:0!important;
        background:transparent;
        color:#a2a4a2;
        display:flex;
        align-items:center;
        justify-content:flex-start;
        cursor:pointer;
        margin-bottom:10px;
      }
      .gnw-back svg{width:18px;height:18px}
      .gnw-article-card{
        min-height:124px;
        padding:14px 16px;
        background:var(--gnw-card);
        border-radius:8px;
        display:grid;
        grid-template-columns:minmax(0,1fr) auto;
        grid-template-rows:auto 1fr auto;
        gap:8px 12px;
        margin-bottom:18px;
      }
      .gnw-detail-category{
        grid-column:1;
        grid-row:1;
        justify-self:start;
        min-height:20px;
        display:inline-flex;
        align-items:center;
        padding:2px 6px;
        border-radius:4px;
        background:#2b2d30;
        color:#a5a7a5;
        font-size:11px;
        font-weight:850;
      }
      .gnw-detail-time{
        grid-column:2;
        grid-row:1;
        color:#777a77;
        font-size:12px;
        white-space:nowrap;
      }
      .gnw-detail-title{
        grid-column:1/3;
        grid-row:2;
        color:#dedfde;
        font-size:15px;
        line-height:1.45;
        font-weight:850;
        align-self:start;
      }
      .gnw-detail-source{
        grid-column:1;
        grid-row:3;
        color:#777a77;
        font-size:12px;
      }
      .gnw-detail-views{
        grid-column:2;
        grid-row:3;
        display:flex;
        align-items:center;
        justify-content:flex-end;
        gap:4px;
        color:#777a77;
        font-size:12px;
      }
      .gnw-detail-views svg{width:13px;height:13px}

      .gnw-detail-section{margin-bottom:18px}
      .gnw-detail-heading{
        color:#a8aaa8;
        font-size:13px;
        font-weight:800;
        margin-bottom:9px;
      }
      .gnw-chip-row{display:flex;flex-wrap:wrap;gap:7px}
      .gnw-chip{
        min-height:30px;
        border:0!important;
        outline:0!important;
        border-radius:6px;
        background:var(--gnw-card);
        color:#d4d5d4;
        padding:0 10px;
        font-size:13px;
        font-weight:800;
        display:inline-flex;
        align-items:center;
        justify-content:center;
      }

      .gnw-stock-list{display:flex;flex-direction:column;gap:8px}
      .gnw-stock-row{
        width:100%;
        min-height:50px;
        background:var(--gnw-card);
        border-radius:8px;
        display:grid;
        grid-template-columns:minmax(0,1fr) 34px;
        align-items:center;
        padding:0 8px 0 13px;
      }
      .gnw-stock-main{min-width:0;display:flex;align-items:baseline;gap:8px}
      .gnw-stock-symbol{color:#ececec;font-size:14px;font-weight:900;white-space:nowrap}
      .gnw-stock-name{
        min-width:0;
        color:#6f7270;
        font-size:10px;
        white-space:nowrap;
        overflow:hidden;
        text-overflow:ellipsis;
      }
      .gnw-star{
        width:34px;
        height:34px;
        border:0!important;
        outline:0!important;
        background:transparent;
        color:#777a77;
        display:flex;
        align-items:center;
        justify-content:center;
        cursor:pointer;
        border-radius:50%;
      }
      .gnw-star:hover{background:#282a2c}
      .gnw-star svg{width:18px;height:18px}
      .gnw-star svg.is-filled{fill:#aaa;stroke:#aaa}

      .gnw-original{
        width:100%;
        height:46px;
        border:0!important;
        outline:0!important;
        border-radius:8px;
        background:var(--gnw-card);
        color:#e1e1e1;
        font-size:14px;
        font-weight:850;
        display:flex;
        align-items:center;
        justify-content:center;
        gap:7px;
        cursor:default;
        opacity:.92;
      }
      .gnw-original svg{width:14px;height:14px}
      /* 원본 폰트/크기는 유지하고 카테고리 줄만 반응형 */
      @container (max-width:450px){
        .gnw-cats{
          display:grid;
          grid-template-columns:repeat(4,minmax(0,1fr));
          gap:6px;
        }
        .gnw-cat{width:100%;padding-left:6px;padding-right:6px;text-align:center}
      }

      @container (max-width:330px){
        .gnw-cats{gap:5px}
        .gnw-cat{padding-left:3px;padding-right:3px}
      }
    `;
    document.head.appendChild(style);
  }

  function filteredItems(state) {
    const query = state.query.trim().toLowerCase();
    const filtered = DEMO_ITEMS.filter((item) => {
      const categoryOk = true; // layout-only: category buttons do not change demo row count
      if (!categoryOk) return false;
      if (!query) return true;
      const blob = [
        item.title,
        item.source,
        item.category,
        ...(item.issues || []),
        ...(item.themes || []),
        ...(item.stocks || []).flatMap((stock) => [stock.symbol, stock.name]),
      ].join(' ').toLowerCase();
      return blob.includes(query);
    });
    return state.sortOrder === 'oldest' ? [...filtered].reverse() : filtered;
  }

  function buildShell(root) {
    root.innerHTML = `
      <section class="gnw" data-gnw>
        <div class="gnw-main" data-gnw-main>
          <div class="gnw-main-inner">
            <div class="gnw-search">
              ${searchIcon()}
              <input type="search" data-gnw-search placeholder="검색어를 입력하세요" autocomplete="off">
              <button type="button" class="gnw-search-action" data-gnw-favorite aria-label="관심 뉴스">
                ${starIcon(false)}
              </button>
            </div>

            <div class="gnw-cats" data-gnw-cats>
              ${CATEGORIES.map((category, index) => `
                <button type="button"
                        class="gnw-cat${index === 0 ? ' is-active' : ''}"
                        data-category="${category}">${category}</button>
              `).join('')}
            </div>

            <div class="gnw-section-head">
              <div class="gnw-section-title">주요뉴스 &gt;</div>
              <div class="gnw-counter" data-gnw-counter></div>
            </div>

            <div class="gnw-headline-wrap">
              <button type="button" class="gnw-arrow" data-gnw-prev aria-label="이전 주요뉴스">
                ${arrowLeftIcon()}
              </button>
              <div class="gnw-track" data-gnw-track></div>
              <button type="button" class="gnw-arrow" data-gnw-next aria-label="다음 주요뉴스">
                ${arrowRightIcon()}
              </button>
            </div>
            <div class="gnw-dots" data-gnw-dots></div>

            <div class="gnw-news-head gnw-news-head--filters-only">
              <div class="gnw-filters">
                <button type="button" class="gnw-filter" data-gnw-source-filter>출처⌄</button>
                <button type="button" class="gnw-filter" data-gnw-sort>전체·최신순⌄</button>
                <button type="button" class="gnw-filter gnw-filter-refresh" data-gnw-refresh aria-label="새로고침">↻</button>
              </div>
            </div>

            <div class="gnw-list" data-gnw-list></div>
            <button type="button" class="gnw-more" data-gnw-more>더보기</button>
          </div>
        </div>

        <div class="gnw-detail" data-gnw-detail hidden></div>
      </section>
    `;
  }

  function renderHeadlines(state, items) {
    const headlineItems = items.slice(0, MAX_VISIBLE);
    const totalPages = Math.max(1, Math.ceil(headlineItems.length / HEADLINE_PER_PAGE));

    if (state.page >= totalPages) state.page = 0;

    const start = state.page * HEADLINE_PER_PAGE;
    const visible = headlineItems.slice(start, start + HEADLINE_PER_PAGE);

    const track = state.root.querySelector('[data-gnw-track]');
    const counter = state.root.querySelector('[data-gnw-counter]');
    const dots = state.root.querySelector('[data-gnw-dots]');
    const prev = state.root.querySelector('[data-gnw-prev]');
    const next = state.root.querySelector('[data-gnw-next]');

    counter.textContent = headlineItems.length ? `${state.page + 1} / ${totalPages}` : '';
    prev.disabled = !headlineItems.length || state.page === 0;
    next.disabled = !headlineItems.length || state.page >= totalPages - 1;

    if (!visible.length) {
      track.innerHTML = '<div class="gnw-no-result">표시할 뉴스가 없습니다.</div>';
      dots.innerHTML = '';
      return;
    }

    track.innerHTML = visible.map((item, index) => `
      <button type="button" class="gnw-headline" data-headline-id="${escapeHtml(item.id)}">
        <span class="gnw-headline-title">${escapeHtml(item.title)}</span>
      </button>
    `).join('');

    dots.innerHTML = Array.from({ length: totalPages }, (_, index) => (
      `<span class="gnw-dot${index === state.page ? ' is-active' : ''}"></span>`
    )).join('');

    track.querySelectorAll('[data-headline-id]').forEach((button) => {
      button.addEventListener('click', () => {
        const item = visible.find((candidate) => candidate.id === button.dataset.headlineId);
        if (item) showDetail(state, item);
      });
    });
  }

  function renderList(state, items) {
    const list = state.root.querySelector('[data-gnw-list]');
    const more = state.root.querySelector('[data-gnw-more]');

    if (!items.length) {
      list.innerHTML = '<div class="gnw-no-result">검색 결과가 없습니다.</div>';
      more.hidden = true;
      return;
    }

    const visibleItems = items.slice(0, state.visible);

    list.innerHTML = visibleItems.map((item) => `
      <button type="button" class="gnw-item" data-news-id="${escapeHtml(item.id)}">
        <span class="gnw-meta-left">
          <span class="gnw-tag">${escapeHtml(item.category)}</span>
        </span>
        <span class="gnw-meta-right">${escapeHtml(item.source)} · ${escapeHtml(item.display_datetime)}</span>
        <span class="gnw-title">${escapeHtml(item.title)}</span>
        <span class="gnw-views">${eyeIcon()} ${escapeHtml(item.views)}</span>
      </button>
    `).join('');

    list.querySelectorAll('[data-news-id]').forEach((button) => {
      button.addEventListener('click', () => {
        const item = visibleItems.find((candidate) => candidate.id === button.dataset.newsId);
        if (item) showDetail(state, item);
      });
    });

    more.hidden = items.length <= INIT_VISIBLE;
    if (!more.hidden) {
      more.textContent = state.visible > INIT_VISIBLE ? '접기' : '더보기';
    }
  }

  function render(state) {
    const items = filteredItems(state);
    renderHeadlines(state, items);
    renderList(state, items);
  }

  function showDetail(state, item) {
    const main = state.root.querySelector('[data-gnw-main]');
    const detail = state.root.querySelector('[data-gnw-detail]');

    detail.innerHTML = `
      <div class="gnw-detail-inner">
        <button type="button" class="gnw-back" data-gnw-back aria-label="뉴스 목록으로 돌아가기">
          ${arrowLeftIcon()}
        </button>

        <div class="gnw-article-card">
          <span class="gnw-detail-category">${escapeHtml(item.category)}</span>
          <span class="gnw-detail-time">${escapeHtml(item.display_datetime)}</span>
          <div class="gnw-detail-title">${escapeHtml(item.title)}</div>
          <div class="gnw-detail-source">${escapeHtml(item.source)}</div>
          <div class="gnw-detail-views">${eyeIcon()} ${escapeHtml(item.views)}</div>
        </div>

        <section class="gnw-detail-section">
          <div class="gnw-detail-heading">관련 이슈</div>
          <div class="gnw-chip-row">
            ${(item.issues || []).map((issue) => `<span class="gnw-chip">${escapeHtml(issue)}</span>`).join('')}
          </div>
        </section>

        <section class="gnw-detail-section">
          <div class="gnw-detail-heading">관련 종목</div>
          <div class="gnw-stock-list">
            ${(item.stocks || []).map((stock, index) => `
              <div class="gnw-stock-row">
                <div class="gnw-stock-main">
                  <span class="gnw-stock-symbol">${escapeHtml(stock.symbol)}</span>
                </div>
                <button type="button" class="gnw-star" data-stock-star="${index}" aria-label="관심 종목 표시">
                  ${starIcon(false)}
                </button>
              </div>
            `).join('')}
          </div>
        </section>

        <section class="gnw-detail-section">
          <div class="gnw-detail-heading">관련 산업·테마</div>
          <div class="gnw-chip-row">
            ${(item.themes || []).map((theme) => `<span class="gnw-chip">${escapeHtml(theme)}</span>`).join('')}
          </div>
        </section>

        <button type="button" class="gnw-original" aria-disabled="true">
          기사 원문 ${externalIcon()}
        </button>
      </div>
    `;

    main.hidden = true;
    detail.hidden = false;
    detail.scrollTop = 0;

    detail.querySelector('[data-gnw-back]').addEventListener('click', () => {
      detail.hidden = true;
      main.hidden = false;
      main.scrollTop = state.listScrollTop;
    });

    detail.querySelectorAll('[data-stock-star]').forEach((button) => {
      let active = false;
      button.addEventListener('click', () => {
        active = !active;
        button.innerHTML = starIcon(active);
      });
    });
  }

  function bind(state) {
    const root = state.root;
    const main = root.querySelector('[data-gnw-main]');

    root.querySelector('[data-gnw-favorite]').addEventListener('click', (event) => {
      const button = event.currentTarget;
      state.favoriteOnly = !state.favoriteOnly;
      button.classList.toggle('is-active', state.favoriteOnly);
      button.innerHTML = starIcon(state.favoriteOnly);
    });

    root.querySelector('[data-gnw-source-filter]').addEventListener('click', (event) => {
      event.currentTarget.classList.toggle('is-active');
    });

    root.querySelector('[data-gnw-sort]').addEventListener('click', (event) => {
      state.sortOrder = state.sortOrder === 'latest' ? 'oldest' : 'latest';
      event.currentTarget.textContent = state.sortOrder === 'latest' ? '전체·최신순⌄' : '전체·오래된순⌄';
      state.page = 0;
      render(state);
    });

    root.querySelector('[data-gnw-refresh]').addEventListener('click', () => {
      state.category = '증시';
      state.query = '';
      state.sortOrder = 'latest';
      state.visible = INIT_VISIBLE;
      state.page = 0;
      root.querySelector('[data-gnw-search]').value = '';
      root.querySelectorAll('.gnw-cat').forEach((element) => {
        element.classList.toggle('is-active', element.dataset.category === '증시');
      });
      root.querySelector('[data-gnw-sort]').textContent = '전체·최신순⌄';
      render(state);
      main.scrollTop = 0;
    });

    root.querySelector('[data-gnw-cats]').addEventListener('click', (event) => {
      const button = event.target.closest('[data-category]');
      if (!button) return;

      root.querySelectorAll('.gnw-cat').forEach((element) => {
        element.classList.toggle('is-active', element === button);
      });

      state.category = button.dataset.category;
      state.page = 0;
      state.visible = INIT_VISIBLE;
      render(state);
      main.scrollTop = 0;
    });

    root.querySelector('[data-gnw-search]').addEventListener('input', (event) => {
      state.query = event.target.value || '';
      state.page = 0;
      state.visible = INIT_VISIBLE;
      render(state);
    });

    root.querySelector('[data-gnw-prev]').addEventListener('click', () => {
      if (state.page <= 0) return;
      state.page -= 1;
      renderHeadlines(state, filteredItems(state));
    });

    root.querySelector('[data-gnw-next]').addEventListener('click', () => {
      const itemCount = Math.min(MAX_VISIBLE, filteredItems(state).length);
      const totalPages = Math.max(1, Math.ceil(itemCount / HEADLINE_PER_PAGE));
      if (state.page >= totalPages - 1) return;
      state.page += 1;
      renderHeadlines(state, filteredItems(state));
    });

    root.querySelector('[data-gnw-more]').addEventListener('click', () => {
      state.visible = state.visible > INIT_VISIBLE ? INIT_VISIBLE : MAX_VISIBLE;
      renderList(state, filteredItems(state));
    });

    main.addEventListener('scroll', () => {
      state.listScrollTop = main.scrollTop;
    }, { passive: true });
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
      category: '증시',
      query: '',
      visible: INIT_VISIBLE,
      page: 0,
      listScrollTop: 0,
      sortOrder: 'latest',
      favoriteOnly: false,
    };

    stateByRoot.set(root, state);
    bind(state);
    render(state);
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

  window.GaemiGTPNews = {
    mount,
    open: openNewsWidget,
    mode: 'layout-only',
  };

  window.GaemiGTPWidgets = window.GaemiGTPWidgets || {};
  window.GaemiGTPWidgets.news = {
    mount,
    render: mount,
    mode: 'layout-only',
  };

  window.openGaemiNews = openNewsWidget;
})();
