/* Right Panel Tabs — workspace menu
   책임: 오른쪽 패널의 상단 탭/추가/삭제/선택 상태만 담당한다.
   패널 너비/채팅/사이드바는 건드리지 않는다.
*/
(function () {
  'use strict';
  const TABS_KEY = 'gaemiGTP_right_panel_tabs_v1';
  const PANEL_WORKSPACE_VIEW_KEY = 'gaemiGTP_right_panel_workspace_view_v1';
  const DEFAULT_TABS = [{ id: 'panel-workspace', label: '대시보드', icon: 'layout-dashboard', closable: false }, { id: 'auto-trade', label: '자동매매', icon: 'bot', closable: true }];
  let tabs = [];
  let activeTabId = 'panel-workspace';
  let panelWorkspaceView = '';
  let relatedNewsItems = [];
  let relatedDisclosureItems = [];
  const PANEL_WORKSPACE_VIEWS = { 'panel-workspace': { label: '대시보드', icon: 'layout-dashboard' }, news: { label: '뉴스', icon: 'newspaper' }, disclosures: { label: '공시', icon: 'file-text' } };

  function normalizeLegacyPanelWorkspaceDom() {
    const legacyView = document.getElementById('rightPanelTabView-dashboard');
    if (legacyView && !document.getElementById('rightPanelTabView-panel-workspace')) {
      legacyView.id = 'rightPanelTabView-panel-workspace';
      legacyView.dataset.tabView = 'panel-workspace';
      legacyView.setAttribute('aria-label', '대시보드');
    }
    const legacyRoot = document.getElementById('rightPanelDashboard');
    if (legacyRoot && !document.getElementById('rightPanelWorkspace')) {
      legacyRoot.id = 'rightPanelWorkspace';
      legacyRoot.setAttribute('aria-label', '대시보드');
    }
  }

  function readState() {
    try {
      const raw = localStorage.getItem(TABS_KEY);
      if (!raw) return null;
      const state = JSON.parse(raw);
      if (!state || !Array.isArray(state.tabs)) return null;
      const cleanTabs = state.tabs.filter(t => t && typeof t.id === 'string' && typeof t.label === 'string' && !['chart', 'news', 'industry', 'disclosures'].includes(t.id)).map(t => ({ id: t.id === 'dashboard' ? 'panel-workspace' : t.id, label: t.id === 'dashboard' || t.id === 'panel-workspace' ? '대시보드' : t.label, icon: typeof t.icon === 'string' ? t.icon : 'square-chart-gantt', closable: !['dashboard', 'panel-workspace'].includes(t.id) }));
      const storedActiveTabId = state.activeTabId === 'dashboard' ? 'panel-workspace' : state.activeTabId;
      return { tabs: cleanTabs.length ? cleanTabs : null, activeTabId: typeof storedActiveTabId === 'string' ? storedActiveTabId : 'panel-workspace' };
    } catch (e) { console.warn('[gaemiGTP] right panel tabs read warning:', e); return null; }
  }
  function saveState() { try { localStorage.setItem(TABS_KEY, JSON.stringify({ tabs, activeTabId })); } catch (e) { console.warn('[gaemiGTP] right panel tabs save warning:', e); } }
  function savePanelWorkspaceView() { try { localStorage.setItem(PANEL_WORKSPACE_VIEW_KEY, panelWorkspaceView); } catch (_) {} }
  function getTabList() { return document.getElementById('rightPanelTabs'); }
  function getContentRoot() { return document.getElementById('rightPanelContent'); }
  function getView(id) { return document.getElementById(`rightPanelTabView-${id}`); }
  function escapeHtml(value) { return String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#039;'); }
  function makePlaceholderView(tab) {
    const root = getContentRoot(); if (!root || getView(tab.id)) return;
    const section = document.createElement('section'); section.id = `rightPanelTabView-${tab.id}`; section.className = 'right-panel-tab-view'; section.dataset.tabView = tab.id; section.setAttribute('role', 'tabpanel'); section.setAttribute('aria-label', tab.label);
    section.innerHTML = `<div class="right-panel-tab-placeholder"><div class="right-panel-tab-placeholder__icon"><i data-lucide="square-chart-gantt"></i></div><div class="right-panel-tab-placeholder__title">${escapeHtml(tab.label)}</div><div class="right-panel-tab-placeholder__text">이 탭에 원하는 분석 화면을 구성할 수 있습니다.</div></div>`; root.appendChild(section);
  }
  function renderPanelWorkspaceView() {
    const root = document.getElementById('rightPanelWorkspace'); if (!root) return;
    if (!panelWorkspaceView) { root.innerHTML = ''; return; }
    if (panelWorkspaceView === 'panel-workspace') { root.innerHTML = '<section id="rightPanelGrid" aria-label="대시보드"></section>'; if (window.GaemiGTPPanelWorkspace && typeof window.GaemiGTPPanelWorkspace.mount === 'function') window.GaemiGTPPanelWorkspace.mount(root); return; }
    if (panelWorkspaceView === 'news') { renderRelatedNewsPanel(); return; }
    if (panelWorkspaceView === 'disclosures' && relatedDisclosureItems.length) { renderRelatedDisclosuresPanel(); return; }
    if (panelWorkspaceView === 'disclosures') { root.innerHTML = '<section id="rightPanelDisclosures" style="height:100%;min-height:0;" aria-label="공시"></section>'; mountDisclosuresPage(); }
  }
  function renderTabs() {
    const list = getTabList(); if (!list) return; list.innerHTML = '';
    tabs.forEach(tab => {
      if (tab.id === 'panel-workspace') {
        const wrap = document.createElement('div'); wrap.className = 'right-panel-workspace-menu-wrap';
        const button = document.createElement('button'); button.type = 'button'; button.className = 'right-panel-tab-add'; button.dataset.panelWorkspaceMenuToggle = 'true'; button.setAttribute('aria-label', '패널 메뉴'); button.setAttribute('aria-expanded', 'false'); button.title = '패널 메뉴'; button.innerHTML = '<i data-lucide="ellipsis"></i>'; wrap.appendChild(button);
        const menu = document.createElement('div'); menu.className = 'right-panel-tab-menu right-panel-workspace-menu'; menu.dataset.panelWorkspaceMenu = 'true'; menu.hidden = true; menu.innerHTML = `<button type="button" class="right-panel-tab-menu__item" data-panel-workspace-view="panel-workspace"><i data-lucide="layout-dashboard"></i><span>대시보드</span></button><button type="button" class="right-panel-tab-menu__item" data-panel-workspace-view="news"><i data-lucide="newspaper"></i><span>뉴스</span></button><button type="button" class="right-panel-tab-menu__item" data-panel-workspace-view="disclosures"><i data-lucide="file-text"></i><span>공시</span></button>`; wrap.appendChild(menu); list.appendChild(wrap); return;
      }
      const button = document.createElement('button'); button.type = 'button'; button.className = `right-panel-tab${activeTabId === tab.id ? ' is-active' : ''}`; button.dataset.rightPanelTab = tab.id; button.setAttribute('role', 'tab'); button.setAttribute('aria-selected', activeTabId === tab.id ? 'true' : 'false'); button.title = tab.label;
      const label = document.createElement('span'); label.className = 'right-panel-tab__label'; label.textContent = tab.label; button.appendChild(label);
      if (tab.closable !== false) { const close = document.createElement('span'); close.className = 'right-panel-tab__close'; close.dataset.closeTabId = tab.id; close.setAttribute('role', 'button'); close.tabIndex = 0; close.setAttribute('aria-label', `${tab.label} 탭 닫기`); close.title = `${tab.label} 탭 닫기`; close.innerHTML = '<i data-lucide="x"></i>'; button.appendChild(close); }
      list.appendChild(button);
    }); if (window.lucide) window.lucide.createIcons();
  }
  function togglePanelWorkspaceMenu(force) { const menu = document.querySelector('[data-panel-workspace-menu]'); const toggle = document.querySelector('[data-panel-workspace-menu-toggle]'); if (!menu || !toggle) return; const next = typeof force === 'boolean' ? force : menu.hidden; menu.hidden = !next; toggle.setAttribute('aria-expanded', String(next)); if (next && window.lucide) window.lucide.createIcons(); }
  function addNamedTab(type) { if (!['panel-workspace', 'auto-trade'].includes(type)) return; const existing = tabs.find(t => t.id === type); if (existing) { setActiveTab(existing.id); togglePanelWorkspaceMenu(false); return; } const labels = { 'panel-workspace': '대시보드', 'auto-trade': '자동매매' }; const icons = { 'panel-workspace': 'layout-dashboard', 'auto-trade': 'bot' }; const tab = { id: type, label: labels[type], icon: icons[type], closable: type !== 'panel-workspace' }; tabs.push(tab); if (type !== 'panel-workspace') makePlaceholderView(tab); setActiveTab(type); togglePanelWorkspaceMenu(false); }
  async function loadActiveStockDisclosures() {
    const stock = String(window.GaemiGTPActiveStock || '').trim();
    if (!stock) {
      relatedDisclosureItems = [];
      renderRelatedDisclosuresPanel();
      return;
    }
    const root = document.getElementById('rightPanelWorkspace');
    if (root) root.innerHTML = '<section class="right-panel-related-news"><div class="right-panel-related-news__meta">공시 확인중...</div></section>';
    try {
      const response = await fetch(`https://gaemi-gtp.onrender.com/analyze?stock=${encodeURIComponent(stock)}`);
      const result = await response.json();
      relatedDisclosureItems = (
        Array.isArray(result.disclosures) && result.disclosures.length
          ? result.disclosures
          : (Array.isArray(result.us_filings) ? result.us_filings : [])
      ).slice(0, 30);
    } catch (_) {
      relatedDisclosureItems = [];
    }
    renderRelatedDisclosuresPanel();
  }
  function selectPanelWorkspaceView(type) {
    if (!PANEL_WORKSPACE_VIEWS[type]) return;
    panelWorkspaceView = type;
    setActiveTab('panel-workspace');
    savePanelWorkspaceView();
    togglePanelWorkspaceMenu(false);
    if (type === 'disclosures') loadActiveStockDisclosures();
  }
  function formatNewsDate(value) {
    if (!value) return '';
    try {
      return new Intl.DateTimeFormat('ko-KR', {
        month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit',
        hour12: false, timeZone: 'Asia/Seoul'
      }).format(new Date(value));
    } catch (_) { return String(value); }
  }
  function renderRelatedNewsPanel() {
    const root = document.getElementById('rightPanelWorkspace');
    if (!root) return;
    root.innerHTML = '';
    if (!relatedNewsItems.length) return;
    const section = document.createElement('section');
    section.className = 'right-panel-related-news';
    section.setAttribute('aria-label', '관련 기사');
    if (!relatedNewsItems.length) {
      const empty = document.createElement('div');
      empty.className = 'right-panel-related-news__empty';
      empty.textContent = '관련 기사가 없습니다.';
      section.appendChild(empty);
    } else {
      const list = document.createElement('div');
      list.className = 'right-panel-related-news__list';
      relatedNewsItems.forEach((item) => {
        const article = document.createElement('button');
        article.type = 'button';
        article.className = 'right-panel-related-news__item';
        article.addEventListener('click', () => window.GaemiGTPExternalLinkModal?.openExternalLinkModal?.(item));
        const title = document.createElement('div');
        title.className = 'right-panel-related-news__title';
        title.textContent = item.title || '제목 확인 필요';
        const description = document.createElement('div');
        description.className = 'right-panel-related-news__description';
        description.textContent = item.description || item.summary || '기사 내용이 없습니다.';
        const meta = document.createElement('div');
        meta.className = 'right-panel-related-news__meta';
        meta.textContent = [item.source || '뉴스', formatNewsDate(item.published_at)].filter(Boolean).join(' · ');
        article.append(title, description, meta);
        list.appendChild(article);
      });
      section.appendChild(list);
    }
    root.appendChild(section);
  }
  function renderRelatedDisclosuresPanel() {
    const root = document.getElementById('rightPanelWorkspace');
    if (!root) return;
    root.innerHTML = '';
    const section = document.createElement('section');
    section.className = 'right-panel-related-news';
    section.setAttribute('aria-label', '한달 공시');
    const list = document.createElement('div');
    list.className = 'right-panel-related-news__list';
    relatedDisclosureItems.forEach((item) => {
      const row = document.createElement('button');
      row.type = 'button';
      row.className = 'right-panel-related-news__item';
      row.addEventListener('click', () => window.GaemiGTPExternalLinkModal?.openExternalLinkModal?.(item));
      const title = document.createElement('div');
      title.className = 'right-panel-related-news__title';
      title.textContent = item.title || '공시 제목 확인 필요';
      const meta = document.createElement('div');
      meta.className = 'right-panel-related-news__meta';
      meta.textContent = [item.date || '', item.time || '', item.source || '공시'].filter(Boolean).join(' · ');
      const keywords = Array.isArray(item.keywords) ? item.keywords.filter(Boolean) : [];
      const keywordLine = document.createElement('div');
      keywordLine.className = 'right-panel-related-news__meta';
      keywordLine.textContent = keywords.map((keyword) => `#${keyword}`).join(' ');
      row.append(title, meta);
      const holdings = Array.isArray(item.executive_shareholdings) ? item.executive_shareholdings : [];
      holdings.forEach((detail) => {
        const person = String(detail.repror || '').trim();
        const position = String(detail.isu_exctv_ofcps || '').trim();
        const currentShares = String(detail.sp_stock_lmp_cnt || '').trim();
        const shareDelta = String(detail.sp_stock_lmp_irds_cnt || '').trim();
        const currentRate = String(detail.sp_stock_lmp_rate || '').trim();
        const personLine = document.createElement('div');
        personLine.className = 'right-panel-related-news__meta';
        personLine.textContent = [person, position].filter(Boolean).join(' · ');
        const holdingLine = document.createElement('div');
        holdingLine.className = 'right-panel-related-news__meta';
        holdingLine.textContent = [
          currentShares ? `${currentShares}주` : '',
          shareDelta ? `${shareDelta}주` : '',
          currentRate ? `${currentRate}%` : ''
        ].filter(Boolean).join(' · ');
        if (personLine.textContent) row.appendChild(personLine);
        if (holdingLine.textContent) row.appendChild(holdingLine);
      });
      if (String(item.form || '').toUpperCase() === '4') {
        const person = String(item.person || '').trim();
        const position = String(item.officer_title || '').trim();
        const personLine = document.createElement('div');
        personLine.className = 'right-panel-related-news__meta';
        personLine.textContent = [person, position].filter(Boolean).join(' · ');
        if (personLine.textContent) row.appendChild(personLine);
        const transactions = Array.isArray(item.transactions) ? item.transactions : [];
        transactions.forEach((transaction) => {
          const shares = String(transaction.shares || '').trim();
          const price = String(transaction.price || '').trim();
          const transactionLine = document.createElement('div');
          transactionLine.className = 'right-panel-related-news__meta';
          transactionLine.textContent = [
            shares ? `${shares}주` : '',
            price ? `${price}` : ''
          ].filter(Boolean).join(' · ');
          if (transactionLine.textContent) row.appendChild(transactionLine);
        });
      }
      if (keywords.length) row.appendChild(keywordLine);
      list.appendChild(row);
    });
    section.appendChild(list);
    root.appendChild(section);
  }
  function showRelatedDisclosures(items) {
    relatedDisclosureItems = Array.isArray(items) ? items.slice(0, 30) : [];
    panelWorkspaceView = 'disclosures';
    savePanelWorkspaceView();
    document.body.classList.add('right-panel-open');
    window.applySidebarState?.();
    if (activeTabId !== 'panel-workspace') {
      setActiveTab('panel-workspace', false);
      return;
    }
    renderRelatedDisclosuresPanel();
  }
  function showRelatedNews(items) {
    relatedNewsItems = Array.isArray(items) ? items.slice(0, 20) : [];
    panelWorkspaceView = 'news';
    savePanelWorkspaceView();
    document.body.classList.add('right-panel-open');
    window.applySidebarState?.();
    if (activeTabId !== 'panel-workspace') {
      setActiveTab('panel-workspace', false);
      return;
    }
    renderRelatedNewsPanel();
  }
  function mountNewsPage() { const root = document.getElementById('rightPanelNews'); if (root && window.GaemiGTPMarketauxNews && typeof window.GaemiGTPMarketauxNews.mount === 'function') window.GaemiGTPMarketauxNews.mount(root); else if (root) window.addEventListener('load', () => { if (activeTabId === 'panel-workspace' && panelWorkspaceView === 'news' && window.GaemiGTPMarketauxNews && typeof window.GaemiGTPMarketauxNews.mount === 'function') window.GaemiGTPMarketauxNews.mount(root); }, { once: true }); }
  function mountDisclosuresPage() { const root = document.getElementById('rightPanelDisclosures'); if (root && window.GaemiGTPDisclosuresPage && typeof window.GaemiGTPDisclosuresPage.mount === 'function') window.GaemiGTPDisclosuresPage.mount(root); }
  function mountTabPage(tab) { if (tab?.id === 'auto-trade') { const root = document.getElementById('rightPanelAutoTrade'); if (root && window.GaemiGTPAutoTrade && typeof window.GaemiGTPAutoTrade.mount === 'function') window.GaemiGTPAutoTrade.mount(root); } }
  function setActiveTab(id, persist = true) { if (!tabs.some(t => t.id === id)) return; activeTabId = id; tabs.forEach(tab => { if (tab.id === 'auto-trade') mountTabPage(tab); else if (tab.id !== 'panel-workspace' && !getView(tab.id)) makePlaceholderView(tab); }); document.querySelectorAll('[data-tab-view]').forEach(view => { const active = view.dataset.tabView === activeTabId; view.hidden = !active; view.setAttribute('aria-hidden', active ? 'false' : 'true'); }); renderTabs(); if (activeTabId === 'panel-workspace') renderPanelWorkspaceView(); if (persist) saveState(); }
  function nextCustomLabel() { let n = 1; const existing = new Set(tabs.map(t => t.label)); while (existing.has(`분석 #${n}`)) n += 1; return `분석 #${n}`; }
  function addTab() { const id = `tab_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`; const tab = { id, label: nextCustomLabel(), icon: 'square-chart-gantt', closable: true }; tabs.push(tab); makePlaceholderView(tab); setActiveTab(id); }
  function removeTab(id) { const index = tabs.findIndex(t => t.id === id); if (index === -1 || tabs[index].closable === false || tabs.length <= 1) return; const wasActive = activeTabId === id; tabs.splice(index, 1); const view = getView(id); if (view) view.remove(); if (wasActive) activeTabId = (tabs[Math.max(0, index - 1)] || tabs[0]).id; setActiveTab(activeTabId); }
  function initialize() {
    normalizeLegacyPanelWorkspaceDom();
    if (!getTabList() || !getContentRoot() || getTabList().dataset.bound === 'true') return;
    const stored = readState(); tabs = stored?.tabs?.length ? stored.tabs : DEFAULT_TABS.map(t => ({ ...t })); activeTabId = tabs.some(t => t.id === stored?.activeTabId) ? stored.activeTabId : 'panel-workspace'; panelWorkspaceView = ''; savePanelWorkspaceView();
    tabs.forEach(tab => { if (tab.id !== 'panel-workspace' && tab.id !== 'auto-trade') makePlaceholderView(tab); });
    getTabList().addEventListener('click', event => { const toggle = event.target.closest('[data-panel-workspace-menu-toggle]'); if (toggle) { event.stopPropagation(); togglePanelWorkspaceMenu(); return; } const viewButton = event.target.closest('[data-panel-workspace-view]'); if (viewButton) { event.stopPropagation(); selectPanelWorkspaceView(viewButton.dataset.panelWorkspaceView); return; } const close = event.target.closest('[data-close-tab-id]'); if (close) { event.stopPropagation(); removeTab(close.dataset.closeTabId); return; } const tab = event.target.closest('[data-right-panel-tab]'); if (tab) { togglePanelWorkspaceMenu(false); setActiveTab(tab.dataset.rightPanelTab); } });
    document.addEventListener('click', event => { if (!event.target.closest('#rightPanelTabs')) togglePanelWorkspaceMenu(false); }); getTabList().dataset.bound = 'true'; setActiveTab(activeTabId, false); saveState();
  }
  window.GaemiGTPRightPanelTabs = { initialize, addTab, addNamedTab, selectPanelWorkspaceView, removeTab, setActiveTab, showRelatedNews, showRelatedDisclosures, getTabs: () => tabs.map(tab => ({ ...tab })), getActiveTab: () => activeTabId };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize, { once: true }); else initialize();
})();
