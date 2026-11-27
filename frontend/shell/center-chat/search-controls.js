/* Center Chat Search Controls — stock search and mode controls owned by the central chat shell. */
(function () {
  'use strict';

  const STOCK_SEARCH_ALIASES = Object.freeze({
    '구글': '알파벳', 'google': '알파벳', 'alphabet': '알파벳',
    '스페이스엑스': '스페이스X', '스페이스x': '스페이스X', 'spacex': '스페이스X', 'spcx': '스페이스X',
    '현대자동차': '현대차', '네이버': 'NAVER', '포스코홀딩스': 'POSCO홀딩스', '에이치엘비': 'HLB',
    'sk하이닉스': 'SK하이닉스', '하이닉스': 'SK하이닉스',
    '삼성전자': '삼성전자', '005930': '삼성전자',
    '현대차': '현대차', '기아': '기아', '셀트리온': '셀트리온',
    '에코프로': '에코프로', '에코프로비엠': '에코프로비엠', '알테오젠': '알테오젠',
    '카카오': '카카오', '카카오뱅크': '카카오뱅크', 'lg에너지솔루션': 'LG에너지솔루션',
    '삼성바이오로직스': '삼성바이오로직스', '포스코퓨처엠': '포스코퓨처엠',
    '삼성sdi': '삼성SDI', 'lg화학': 'LG화학', '한미반도체': '한미반도체',
    '삼천당제약': '삼천당제약', '레인보우로보틱스': '레인보우로보틱스',
    '리가켐바이오': '리가켐바이오', '크래프톤': '크래프톤', '신한지주': '신한지주',
    'kb금융': 'KB금융', '두산에너빌리티': '두산에너빌리티', '두산로보틱스': '두산로보틱스',
    '현대모비스': '현대모비스', 'hd현대중공업': 'HD현대중공업',
    '한화에어로스페이스': '한화에어로스페이스', '하이브': '하이브',
    '한국전력': '한국전력', '엔씨소프트': '엔씨소프트', '유한양행': '유한양행', '루닛': '루닛',
    '엔비디아': '엔비디아', 'nvidia': '엔비디아', 'nvda': '엔비디아',
    '테슬라': '테슬라', 'tesla': '테슬라', 'tsla': '테슬라',
    '애플': '애플', 'apple': '애플', 'aapl': '애플',
    '마이크로소프트': '마이크로소프트', 'microsoft': '마이크로소프트', 'msft': '마이크로소프트',
    '아마존': '아마존', 'amazon': '아마존', 'amzn': '아마존',
    '알파벳': '알파벳', 'googl': '알파벳', 'goog': '알파벳',
    '메타': '메타', 'meta': '메타',
    '브로드컴': '브로드컴', 'broadcom': '브로드컴', 'avgo': '브로드컴',
    '버크셔해서웨이': '버크셔 해서웨이', 'brk.b': '버크셔 해서웨이',
    '일라이릴리': '일라이 릴리', 'lly': '일라이 릴리',
    'amd': 'AMD', '마이크론테크놀로지': '마이크론 테크놀로지', 'micron': '마이크론 테크놀로지', 'mu': '마이크론 테크놀로지',
    '퀄컴': '퀄컴', 'qualcomm': '퀄컴', 'qcom': '퀄컴',
    'tsmc': 'TSMC', 'asml': 'ASML', '팔란티어': '팔란티어', 'palantir': '팔란티어', 'pltr': '팔란티어',
    '로빈후드': '로빈후드', 'hood': '로빈후드', '록히드마틴': '록히드마틴', 'lmt': '록히드마틴',
    '엑슨모빌': '엑슨모빌', 'xom': '엑슨모빌', '스페이스x': '스페이스X',
    '샌디스크': '샌디스크', 'sndk': '샌디스크', '오라클': '오라클', 'oracle': '오라클', 'orcl': '오라클',
    '어도비': '어도비', 'adobe': '어도비', 'adbe': '어도비', '비트코인': '비트코인', 'btc': '비트코인'
  });

  function resolveStockSearchInput(stockName) {
    const query = String(stockName || '').trim();
    if (!query) return '';
    return STOCK_SEARCH_ALIASES[query.toLowerCase()] || STOCK_SEARCH_ALIASES[query] || query;
  }

  // Return a stock only when the complete chat input is a known company alias/ticker.
  // A longer natural-language question must stay on the normal question path.
  function resolveStockInputOnly(value) {
    const query = String(value || '').trim().toLowerCase();
    if (!query) return '';
    const compact = query.replace(/\\s+/g, '');
    return STOCK_SEARCH_ALIASES[query] || STOCK_SEARCH_ALIASES[compact] || '';
  }

  // Reuse stock-search aliases when a user mentions a company in a chat question.
  function resolveStockMention(question) {
    const words = String(question || '').toLowerCase().match(/[a-z0-9가-힣]+/g) || [];
    for (const word of words) {
      if (STOCK_SEARCH_ALIASES[word]) return STOCK_SEARCH_ALIASES[word];
      const bare = word.replace(/(?:에서|으로|부터|까지|은|는|이|가|을|를|도|와|과|랑|의|에|만)$/, '');
      if (bare !== word && STOCK_SEARCH_ALIASES[bare]) return STOCK_SEARCH_ALIASES[bare];
    }
    return '';
  }

  function enterChatWorkspace() {
    document.getElementById('mainHeroView')?.classList.add('hidden');
    document.getElementById('mainContent')?.classList.remove('is-news-view');
    document.getElementById('gaemiCenterNewsFeed')?.setAttribute('hidden', '');
    document.body.classList.add('analysis-mode');
    window.GaemiGTPWorkspaceState?.save?.();
  }

  function resetToHome() {
    document.getElementById('mainHeroView')?.classList.remove('hidden');
    document.getElementById('mainContent')?.classList.remove('is-news-view');
    document.getElementById('gaemiCenterNewsFeed')?.setAttribute('hidden', '');
    document.body.classList.remove('analysis-mode', 'left-home-open', 'left-market-open', 'left-context-open', 'left-plugin-open', 'right-panel-open', 'right-panel-maximized');
    window.GaemiGTPWorkspaceState?.save?.();
    window.GaemiGTPWorkspaceShellState?.apply?.();
  }

  function selectStock(stockName, { enterAnalysis = false, marketSelection = null } = {}) {
    // Sidebar rows already have a source-verified name and code: do not
    // rename them through free-text search aliases before server matching.
    const normalizedStockName = marketSelection?.name === stockName
      ? stockName : resolveStockSearchInput(stockName);
    if (!normalizedStockName) return;
    if (enterAnalysis) enterChatWorkspace();
    if (window.innerWidth < 1024) {
      document.body.classList.remove('left-home-open', 'left-market-open', 'left-context-open', 'left-plugin-open');
    }
    window.GaemiGTPWorkspaceShellState?.apply?.();
    window.GaemiGTPApp?.requestStock?.(normalizedStockName, marketSelection);
  }

  function openStockInChat(stockName, marketSelection = null) {
    selectStock(stockName || '삼성전자', { enterAnalysis: true, marketSelection });
  }

  function focusStockInput() {
    const hero = document.getElementById('heroStockInput');
    const bottom = document.getElementById('bottomStockInput');
    const heroVisible = !!hero && !hero.closest('.hidden') && getComputedStyle(hero).display !== 'none';
    const target = heroVisible ? hero : bottom;
    if (!target) return;
    target.focus();
    target.select?.();
  }

  function isQuestionInput(text) {
    // Preserve one-word stock searches (including aliases such as '하이닉스').
    // Treat natural-language requests as chat, not as a full stock name.
    return /[?？]|알려\s*줘|보여\s*줘|설명\s*해|분석\s*해|해\s*줘|얼마|몇|왜|어때|어떻게|52주|20일|큰손|평균단가|신고가|신저가|최고가|최저가|목표가|주가|움직였|상승률|하락률|추세|수급|뉴스|공시|이슈|비교|전망|실적|호재|악재|괜찮|궁금|알려줄|어떤|있어|없어|될까|할까|인가|일까/.test(text);
  }

  function submitChatInput(value, { enterAnalysis = false } = {}) {
    const query = String(value || '').trim();
    if (!query) return false;
    if (!isQuestionInput(query)) {
      selectStock(query, { enterAnalysis });
      return true;
    }
    enterChatWorkspace();
    if (window.innerWidth < 1024) {
      document.body.classList.remove('left-home-open', 'left-market-open', 'left-context-open', 'left-plugin-open');
    }
    window.GaemiGTPWorkspaceShellState?.apply?.();
    return window.GaemiGTPApp?.submitQuestion?.(query, { newConversation: enterAnalysis }) === true;
  }

  function submitStockSearch(inputId, { enterAnalysis = false, fallback = '' } = {}) {
    const input = document.getElementById(inputId);
    const query = String(input?.value || '').trim() || fallback;
    if (!query) return;
    const submitted = submitChatInput(query, { enterAnalysis });
    if (submitted && input && !enterAnalysis) input.value = '';
  }

  function handleHeroSearch() { submitStockSearch('heroStockInput', { enterAnalysis: true, fallback: '삼성전자' }); }
  function handleBottomSearch() { submitStockSearch('bottomStockInput'); }

  function toggleModeDropdown(which) {
    const heroMenu = document.getElementById('heroModeMenu');
    const bottomMenu = document.getElementById('bottomModeMenu');
    if (which === 'hero') {
      heroMenu?.classList.toggle('hidden');
      bottomMenu?.classList.add('hidden');
    } else {
      bottomMenu?.classList.toggle('hidden');
      heroMenu?.classList.add('hidden');
    }
  }

  function selectAppMode(mode) {
    if (!['gaemi', 'info', 'pro'].includes(mode)) return;
    window.GaemiGTPAppState?.setCurrentAppMode?.(mode);
    const heroLabel = document.getElementById('heroModeLabel');
    const bottomLabel = document.getElementById('bottomModeLabel');
    if (heroLabel) heroLabel.innerText = mode;
    if (bottomLabel) bottomLabel.innerText = mode;
    ['gaemi', 'info', 'pro'].forEach(m => {
      document.getElementById(`chk-hero-${m}`)?.classList.toggle('hidden', m !== mode);
      document.getElementById(`chk-bottom-${m}`)?.classList.toggle('hidden', m !== mode);
    });
    document.getElementById('heroModeMenu')?.classList.add('hidden');
    document.getElementById('bottomModeMenu')?.classList.add('hidden');
  }

  window.GaemiGTPCenterChatSearch = { resolveStockSearchInput, resolveStockInputOnly, resolveStockMention, selectStock, openStockInChat, focusStockInput, submitStockSearch, submitChatInput, handleHeroSearch, handleBottomSearch, toggleModeDropdown, selectAppMode, enterChatWorkspace, resetToHome };
  window.enterChatWorkspace = enterChatWorkspace;
  window.resetToHome = resetToHome;
  window.openStockInChat = openStockInChat;
  window.focusSidebarStockSearch = focusStockInput;
  window.handleHeroSearch = handleHeroSearch;
  window.handleBottomSearch = handleBottomSearch;
  window.toggleModeDropdown = toggleModeDropdown;
  window.selectAppMode = selectAppMode;
}());
