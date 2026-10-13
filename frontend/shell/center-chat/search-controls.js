/* Center Chat Search Controls — stock search and mode controls owned by the central chat shell. */
(function () {
  'use strict';

  const STOCK_SEARCH_ALIASES = Object.freeze({
    '구글': '알파벳', 'google': '알파벳', 'alphabet': '알파벳',
    '스페이스엑스': '스페이스X', '스페이스x': '스페이스X', 'spacex': '스페이스X', 'spcx': '스페이스X',
    '현대자동차': '현대차', '네이버': 'NAVER', '포스코홀딩스': 'POSCO홀딩스', '에이치엘비': 'HLB',
    'sk하이닉스': 'SK하이닉스', '하이닉스': 'SK하이닉스'
  });

  function resolveStockSearchInput(stockName) {
    const query = String(stockName || '').trim();
    if (!query) return '';
    return STOCK_SEARCH_ALIASES[query.toLowerCase()] || STOCK_SEARCH_ALIASES[query] || query;
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
    document.body.classList.add('analysis-mode');
  }

  function resetToHome() {
    document.getElementById('mainHeroView')?.classList.remove('hidden');
    document.body.classList.remove('analysis-mode', 'left-home-open', 'left-market-open', 'left-context-open', 'left-plugin-open', 'right-panel-open', 'right-panel-maximized');
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

  window.GaemiGTPCenterChatSearch = { resolveStockSearchInput, resolveStockMention, selectStock, openStockInChat, focusStockInput, submitStockSearch, submitChatInput, handleHeroSearch, handleBottomSearch, toggleModeDropdown, selectAppMode, enterChatWorkspace, resetToHome };
  window.enterChatWorkspace = enterChatWorkspace;
  window.resetToHome = resetToHome;
  window.openStockInChat = openStockInChat;
  window.focusSidebarStockSearch = focusStockInput;
  window.handleHeroSearch = handleHeroSearch;
  window.handleBottomSearch = handleBottomSearch;
  window.toggleModeDropdown = toggleModeDropdown;
  window.selectAppMode = selectAppMode;
}());
