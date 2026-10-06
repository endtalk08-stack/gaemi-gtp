/* Center Chat Search Controls — stock search and mode controls owned by the central chat shell. */
(function () {
  'use strict';

  const STOCK_SEARCH_ALIASES = Object.freeze({
    '구글': '알파벳', 'google': '알파벳', 'alphabet': '알파벳',
    '스페이스엑스': '스페이스X', '스페이스x': '스페이스X', 'spacex': '스페이스X', 'spcx': '스페이스X',
    '현대자동차': '현대차', '네이버': 'NAVER', '포스코홀딩스': 'POSCO홀딩스', '에이치엘비': 'HLB'
  });

  function resolveStockSearchInput(stockName) {
    const query = String(stockName || '').trim();
    if (!query) return '';
    return STOCK_SEARCH_ALIASES[query.toLowerCase()] || STOCK_SEARCH_ALIASES[query] || query;
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

  function selectStock(stockName, { enterAnalysis = false } = {}) {
    const normalizedStockName = resolveStockSearchInput(stockName);
    if (!normalizedStockName) return;
    if (enterAnalysis) enterChatWorkspace();
    if (window.innerWidth < 1024) {
      document.body.classList.remove('left-home-open', 'left-market-open', 'left-context-open', 'left-plugin-open');
    }
    window.GaemiGTPWorkspaceShellState?.apply?.();
    window.GaemiGTPApp?.requestStock?.(normalizedStockName);
  }

  function openStockInChat(stockName) { selectStock(stockName || '삼성전자', { enterAnalysis: true }); }

  function focusStockInput() {
    const hero = document.getElementById('heroStockInput');
    const bottom = document.getElementById('bottomStockInput');
    const heroVisible = !!hero && !hero.closest('.hidden') && getComputedStyle(hero).display !== 'none';
    const target = heroVisible ? hero : bottom;
    if (!target) return;
    target.focus();
    target.select?.();
  }

  function submitStockSearch(inputId, { enterAnalysis = false, fallback = '' } = {}) {
    const input = document.getElementById(inputId);
    const query = String(input?.value || '').trim() || fallback;
    if (!query) return;
    selectStock(query, { enterAnalysis });
    if (input && !enterAnalysis) input.value = '';
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

  window.GaemiGTPCenterChatSearch = { resolveStockSearchInput, selectStock, openStockInChat, focusStockInput, submitStockSearch, handleHeroSearch, handleBottomSearch, toggleModeDropdown, selectAppMode, enterChatWorkspace, resetToHome };
  window.enterChatWorkspace = enterChatWorkspace;
  window.resetToHome = resetToHome;
  window.openStockInChat = openStockInChat;
  window.focusSidebarStockSearch = focusStockInput;
  window.handleHeroSearch = handleHeroSearch;
  window.handleBottomSearch = handleBottomSearch;
  window.toggleModeDropdown = toggleModeDropdown;
  window.selectAppMode = selectAppMode;
}());
