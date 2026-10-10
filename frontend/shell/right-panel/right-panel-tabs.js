/* Right Panel Tabs — workspace menu
   책임: 오른쪽 패널의 상단 탭/추가/삭제/선택 상태만 담당한다.
   패널 너비/채팅/사이드바는 건드리지 않는다.
*/
(function () {
  'use strict';
  const TABS_KEY = 'gaemiGTP_right_panel_tabs_v1';
  const PANEL_WORKSPACE_VIEW_KEY = 'gaemiGTP_right_panel_workspace_view_v1';
  const DEFAULT_TABS = [{ id: 'panel-workspace', label: '대시보드', icon: 'layout-dashboard', closable: false }];
  let tabs = [];
  let activeTabId = 'panel-workspace';
  let panelWorkspaceView = '';
  let relatedNewsItems = [];
  let relatedDisclosureItems = [];
  let earningsCalendarElement = null;
  const PANEL_WORKSPACE_VIEWS = { 'panel-workspace': { label: '대시보드', icon: 'layout-dashboard' }, news: { label: '뉴스', icon: 'newspaper' }, disclosures: { label: '공시', icon: 'file-text' }, earnings: { label: '실적', icon: 'calendar-days' } };

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
      const cleanTabs = state.tabs.filter(t => t && typeof t.id === 'string' && typeof t.label === 'string' && !['chart', 'news', 'industry', 'disclosures', 'auto-trade'].includes(t.id)).map(t => ({ id: t.id === 'dashboard' ? 'panel-workspace' : t.id, label: t.id === 'dashboard' || t.id === 'panel-workspace' ? '대시보드' : t.label, icon: typeof t.icon === 'string' ? t.icon : 'square-chart-gantt', closable: !['dashboard', 'panel-workspace'].includes(t.id) }));
      const storedActiveTabId = ['dashboard', 'auto-trade'].includes(state.activeTabId) ? 'panel-workspace' : state.activeTabId;
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
    if (panelWorkspaceView === 'disclosures') { renderRelatedDisclosuresPanel(); return; }
    if (panelWorkspaceView === 'earnings') { renderEarningsCalendarPanel(); return; }
  }
  function renderTabs() {
    const list = getTabList(); if (!list) return; list.innerHTML = '';
    tabs.forEach(tab => {
      if (tab.id === 'panel-workspace') {
        const wrap = document.createElement('div'); wrap.className = 'right-panel-workspace-menu-wrap';
        const button = document.createElement('button'); button.type = 'button'; button.className = 'right-panel-tab-add'; button.dataset.panelWorkspaceMenuToggle = 'true'; button.setAttribute('aria-label', '패널 메뉴'); button.setAttribute('aria-expanded', 'false'); button.title = '패널 메뉴'; button.innerHTML = '<i data-lucide="ellipsis"></i>'; wrap.appendChild(button);
        const menu = document.createElement('div'); menu.className = 'right-panel-tab-menu right-panel-workspace-menu'; menu.dataset.panelWorkspaceMenu = 'true'; menu.hidden = true; menu.innerHTML = `<button type="button" class="right-panel-tab-menu__item" data-panel-workspace-view="panel-workspace"><span>대시보드</span></button><button type="button" class="right-panel-tab-menu__item" data-panel-workspace-view="news"><span>뉴스</span></button><button type="button" class="right-panel-tab-menu__item" data-panel-workspace-view="disclosures"><span>공시</span></button><button type="button" class="right-panel-tab-menu__item" data-panel-workspace-view="earnings"><span>실적</span></button>`; wrap.appendChild(menu); list.appendChild(wrap); return;
      }
      const button = document.createElement('button'); button.type = 'button'; button.className = `right-panel-tab${activeTabId === tab.id ? ' is-active' : ''}`; button.dataset.rightPanelTab = tab.id; button.setAttribute('role', 'tab'); button.setAttribute('aria-selected', activeTabId === tab.id ? 'true' : 'false'); button.title = tab.label;
      const label = document.createElement('span'); label.className = 'right-panel-tab__label'; label.textContent = tab.label; button.appendChild(label);
      if (tab.closable !== false) { const close = document.createElement('span'); close.className = 'right-panel-tab__close'; close.dataset.closeTabId = tab.id; close.setAttribute('role', 'button'); close.tabIndex = 0; close.setAttribute('aria-label', `${tab.label} 탭 닫기`); close.title = `${tab.label} 탭 닫기`; close.innerHTML = '<i data-lucide="x"></i>'; button.appendChild(close); }
      list.appendChild(button);
    }); if (window.lucide) window.lucide.createIcons();
  }
  function togglePanelWorkspaceMenu(force) { const menu = document.querySelector('[data-panel-workspace-menu]'); const toggle = document.querySelector('[data-panel-workspace-menu-toggle]'); if (!menu || !toggle) return; const next = typeof force === 'boolean' ? force : menu.hidden; menu.hidden = !next; toggle.setAttribute('aria-expanded', String(next)); if (next && window.lucide) window.lucide.createIcons(); }
  function addNamedTab(type) {
    if (type !== 'panel-workspace') return;
    const existing = tabs.find(t => t.id === type);
    if (existing) {
      setActiveTab(existing.id);
      togglePanelWorkspaceMenu(false);
    }
  }
  function loadActiveStockDisclosures() {
    const snapshot = window.GaemiGTPAnalysisData?.get?.();
    relatedDisclosureItems = (
      Array.isArray(snapshot?.disclosures) && snapshot.disclosures.length
        ? snapshot.disclosures
        : (Array.isArray(snapshot?.usFilings) ? snapshot.usFilings : [])
    ).slice(0, 30);
    renderRelatedDisclosuresPanel();
  }
  function selectRelatedNewsItems(items, limit = 20) {
    const source = Array.isArray(items) ? [...items] : [];
    const byLatest = source.sort((left, right) => {
      const leftTime = Date.parse(left?.published_at || '') || 0;
      const rightTime = Date.parse(right?.published_at || '') || 0;
      return rightTime - leftTime;
    });

    const selected = [];
    const seen = new Set();
    const itemKey = (item) => String(item?.url || item?.link || item?.title || '').trim();
    const pushItem = (item) => {
      const key = itemKey(item);
      if (!key || seen.has(key) || selected.length >= limit) return false;
      seen.add(key);
      selected.push(item);
      return true;
    };

    for (const item of byLatest) {
      if (selected.length >= limit) break;
      pushItem(item);
    }

    return selected.sort((left, right) => {
      const leftTime = Date.parse(left?.published_at || '') || 0;
      const rightTime = Date.parse(right?.published_at || '') || 0;
      return rightTime - leftTime;
    });
  }

  function loadActiveStockNews() {
    const snapshot = window.GaemiGTPAnalysisData?.get?.();
    relatedNewsItems = selectRelatedNewsItems(snapshot?.newsItems, 20);
    renderRelatedNewsPanel();
  }
  function selectPanelWorkspaceView(type) {
    if (!PANEL_WORKSPACE_VIEWS[type]) return;
    panelWorkspaceView = type;
    setActiveTab('panel-workspace');
    savePanelWorkspaceView();
    togglePanelWorkspaceMenu(false);
    if (type === 'news') loadActiveStockNews();
    if (type === 'disclosures') loadActiveStockDisclosures();
    if (type === 'earnings') renderEarningsCalendarPanel();
  }

  function renderEarningsCalendarPanel() {
    const root = document.getElementById('rightPanelWorkspace');
    if (!root) return;
    const calendar = earningsCalendarElement || document.getElementById('leftEarningsCalendarSidebar');
    if (!calendar) return;
    earningsCalendarElement = calendar;
    root.replaceChildren(calendar);
    calendar.removeAttribute('aria-hidden');
    calendar.classList.add('earnings-calendar-sidebar--panel');
    if (window.lucide) window.lucide.createIcons();
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
  async function renderRelatedDisclosuresPanel() {
    const root = document.getElementById('rightPanelWorkspace');
    if (!root) return;
    root.innerHTML = '';
    if (window.GaemiGTPDisclosures?.hydrateDartDetails) {
      await window.GaemiGTPDisclosures.hydrateDartDetails(relatedDisclosureItems);
    }
    const section = document.createElement('section');
    section.className = 'right-panel-related-news right-panel-disclosures';
    section.setAttribute('aria-label', '한달 공시');
    const list = document.createElement('div');
    list.className = 'right-panel-related-news__list';
    relatedDisclosureItems.forEach((item) => {
      const row = document.createElement('div');
      row.className = 'right-panel-related-news__item right-panel-disclosures__item';

      const title = document.createElement('div');
      title.className = 'right-panel-disclosures__line right-panel-disclosures__title';
      title.textContent = item.title || '공시 제목 확인 필요';

      const meta = document.createElement('div');
      meta.className = 'right-panel-disclosures__line';
      const metaLeft = document.createElement('span');
      metaLeft.textContent = [item.date || '', item.time || '', item.source || '공시'].filter(Boolean).join(' · ');
      meta.appendChild(metaLeft);

      const keywords = Array.isArray(item.keywords) ? item.keywords.filter(Boolean) : [];
      const keywordLine = document.createElement('span');
      keywordLine.textContent = keywords.map((keyword) => `#${keyword}`).join(' ');

      row.append(title, meta);

      if (String(item.form || '').toUpperCase() === '8-K') {
        const keyPoints = Array.isArray(item.key_points_ko) ? item.key_points_ko.filter(Boolean).slice(0, 3) : [];
        keyPoints.forEach((point) => {
          const pointText = String(point).trim();
          const pointLine = document.createElement('div');
          pointLine.className = 'right-panel-disclosures__line';

          const pointLeft = document.createElement('span');
          let pointRightText = '';
          let pointLeftText = pointText;

          let match = pointText.match(/^(생산량|인도량|에너지 저장|재무실적) · (.+)$/);
          if (match) {
            pointLeftText = match[1];
            pointRightText = match[2];
          } else {
            match = pointText.match(/^회전신용 한도 최대 (.+?) 추가 확대 가능 · 총 한도 최대 (.+)$/);
          }
          if (!pointRightText && match && pointText.startsWith('회전신용 한도 최대 ')) {
            pointLeftText = '회전신용 한도 추가 확대';
            pointRightText = `${match[1]} · 총 ${match[2]}`;
          } else if (!pointRightText) {
            match = pointText.match(/^최소 (.+?) 유동성 유지 조건$/);
            if (match) {
              pointLeftText = '최소 유동성 유지 조건';
              pointRightText = match[1];
            } else {
              match = pointText.match(/^기존 회전신용 계약 한도 (.+?) · (\d{4}-\d{2}-\d{2}) 만기$/);
              if (match) {
                pointLeftText = '기존 회전신용 계약 만기';
                pointRightText = match[2];
              }
            }
          }

          pointLeft.textContent = pointLeftText;
          pointLine.appendChild(pointLeft);

          if (pointRightText) {
            const pointRight = document.createElement('span');
            pointRight.textContent = pointRightText;
            pointLine.appendChild(pointRight);
          }

          row.appendChild(pointLine);
        });
      }

      const actionDetail = item.corporate_action_detail && typeof item.corporate_action_detail === 'object'
        ? item.corporate_action_detail : null;
      if (actionDetail && Object.keys(actionDetail).length) {
        const amount = Number(actionDetail.amount);
        const equityRatio = Number(actionDetail.equity_ratio);
        const shares = Number(actionDetail.shares);
        const ratio = Number(actionDetail.ratio);
        [
          ['구분', String(actionDetail.kind || '')],
          ['상대회사', String(actionDetail.counterparty || '')],
          ['거래금액', Number.isFinite(amount) ? Math.round(amount).toLocaleString('ko-KR') : ''],
          ['지분율', Number.isFinite(equityRatio) ? `${equityRatio.toFixed(2)}%` : ''],
          ['주식수', Number.isFinite(shares) ? `${Math.round(shares).toLocaleString('ko-KR')}주` : ''],
          ['자기자본 대비', Number.isFinite(ratio) ? `${ratio.toFixed(2)}%` : ''],
          ['목적', String(actionDetail.purpose || '')]
        ].filter(([, value]) => value).slice(0, 4).forEach(([label, value]) => {
          const detailLine = document.createElement('div');
          detailLine.className = 'right-panel-disclosures__line';
          const left = document.createElement('span');
          left.textContent = label;
          const right = document.createElement('span');
          right.textContent = value;
          detailLine.append(left, right);
          row.appendChild(detailLine);
        });
      }

      const dividendDetail = item.dividend_detail && typeof item.dividend_detail === 'object'
        ? item.dividend_detail : null;
      if (dividendDetail && Object.keys(dividendDetail).length) {
        const perShare = Number(dividendDetail.dividend_per_share);
        const rate = Number(dividendDetail.dividend_rate);
        const total = Number(dividendDetail.total_amount);
        [
          ['주당배당금', Number.isFinite(perShare) ? `${Math.round(perShare).toLocaleString('ko-KR')}원` : ''],
          ['시가배당률', Number.isFinite(rate) ? `${rate.toFixed(2)}%` : ''],
          ['배당금총액', Number.isFinite(total) ? Math.round(total).toLocaleString('ko-KR') : ''],
          ['배당기준일', String(dividendDetail.record_date || '')]
        ].filter(([, value]) => value).forEach(([label, value]) => {
          const detailLine = document.createElement('div');
          detailLine.className = 'right-panel-disclosures__line';
          const left = document.createElement('span');
          left.textContent = label;
          const right = document.createElement('span');
          right.textContent = value;
          detailLine.append(left, right);
          row.appendChild(detailLine);
        });
      }

      const treasuryDetail = item.treasury_stock_detail && typeof item.treasury_stock_detail === 'object'
        ? item.treasury_stock_detail : null;
      if (treasuryDetail && Object.keys(treasuryDetail).length) {
        const shares = Number(treasuryDetail.shares);
        const amount = Number(treasuryDetail.amount);
        const price = Number(treasuryDetail.price);
        [
          ['구분', String(treasuryDetail.kind || '')],
          ['예정주식수', Number.isFinite(shares) ? `${Math.round(shares).toLocaleString('ko-KR')}주` : ''],
          ['예정금액', Number.isFinite(amount) ? Math.round(amount).toLocaleString('ko-KR') : ''],
          ['1주당가액', Number.isFinite(price) ? Math.round(price).toLocaleString('ko-KR') : ''],
          ['목적', String(treasuryDetail.purpose || '')],
          ['방법', String(treasuryDetail.method || '')]
        ].filter(([, value]) => value).slice(0, 4).forEach(([label, value]) => {
          const detailLine = document.createElement('div');
          detailLine.className = 'right-panel-disclosures__line';
          const left = document.createElement('span');
          left.textContent = label;
          const right = document.createElement('span');
          right.textContent = value;
          detailLine.append(left, right);
          row.appendChild(detailLine);
        });
      }

      const financingDetail = item.financing_detail && typeof item.financing_detail === 'object'
        ? item.financing_detail : null;
      if (financingDetail && Object.keys(financingDetail).length) {
        const amount = Number(financingDetail.amount);
        const issuePrice = Number(financingDetail.issue_price);
        const newShares = Number(financingDetail.new_shares);
        [
          ['조달유형', String(financingDetail.kind || '')],
          ['조달금액', Number.isFinite(amount) ? Math.round(amount).toLocaleString('ko-KR') : ''],
          ['발행가액', Number.isFinite(issuePrice) ? Math.round(issuePrice).toLocaleString('ko-KR') : ''],
          ['신주수', Number.isFinite(newShares) ? `${Math.round(newShares).toLocaleString('ko-KR')}주` : ''],
          ['방식', String(financingDetail.method || '')],
          ['목적', String(financingDetail.purpose || '')]
        ].filter(([, value]) => value).slice(0, 4).forEach(([label, value]) => {
          const detailLine = document.createElement('div');
          detailLine.className = 'right-panel-disclosures__line';
          const left = document.createElement('span');
          left.textContent = label;
          const right = document.createElement('span');
          right.textContent = value;
          detailLine.append(left, right);
          row.appendChild(detailLine);
        });
      }

      const supplyDetail = item.supply_contract_detail && typeof item.supply_contract_detail === 'object'
        ? item.supply_contract_detail : null;
      if (supplyDetail && Object.keys(supplyDetail).length) {
        const contractAmount = Number(supplyDetail.contract_amount);
        const salesRatio = Number(supplyDetail.sales_ratio);
        [
          ['계약금액', Number.isFinite(contractAmount) ? Math.round(contractAmount).toLocaleString('ko-KR') : ''],
          ['매출액 대비', Number.isFinite(salesRatio) ? `${salesRatio.toFixed(2)}%` : ''],
          ['계약상대', String(supplyDetail.counterparty || '')],
          ['계약내용', String(supplyDetail.contract_name || '')]
        ].filter(([, value]) => value).slice(0, 4).forEach(([label, value]) => {
          const detailLine = document.createElement('div');
          detailLine.className = 'right-panel-disclosures__line';
          const left = document.createElement('span');
          left.textContent = label;
          const right = document.createElement('span');
          right.textContent = value;
          detailLine.append(left, right);
          row.appendChild(detailLine);
        });
      }

      const earningsDetail = item.earnings_detail && typeof item.earnings_detail === 'object'
        ? item.earnings_detail : null;
      const earningsMetrics = Array.isArray(earningsDetail?.metrics) ? earningsDetail.metrics : [];
      earningsMetrics.slice(0, 3).forEach((metric) => {
        const metricLine = document.createElement('div');
        metricLine.className = 'right-panel-disclosures__line';
        const metricLeft = document.createElement('span');
        metricLeft.textContent = String(metric.label || '');
        metricLine.appendChild(metricLeft);
        const current = Number(metric.current);
        const changeRate = Number(metric.change_rate);
        const metricRight = document.createElement('span');
        metricRight.textContent = [
          Number.isFinite(current) ? Math.round(current).toLocaleString('ko-KR') : '',
          Number.isFinite(changeRate) ? `${changeRate > 0 ? '+' : ''}${changeRate.toFixed(2)}%` : ''
        ].filter(Boolean).join(' · ');
        if (metricRight.textContent) metricLine.appendChild(metricRight);
        if (metricLine.textContent) row.appendChild(metricLine);
      });

      const majorChange = item.major_shareholder_change && typeof item.major_shareholder_change === 'object'
        ? item.major_shareholder_change : null;
      if (majorChange) {
        const shareDelta = Number(majorChange.share_delta);
        const currentRate = Number(majorChange.current_rate);
        const rateDelta = Number(majorChange.rate_delta);
        const summaryLine = document.createElement('span');
        summaryLine.textContent = [
          Number.isFinite(shareDelta) ? `총 ${shareDelta > 0 ? '+' : ''}${Math.round(shareDelta).toLocaleString('ko-KR')}주` : '',
          Number.isFinite(currentRate) ? `지분율 ${currentRate.toFixed(2)}%` : '',
          Number.isFinite(rateDelta) && rateDelta !== 0 ? `(${rateDelta > 0 ? '+' : ''}${rateDelta.toFixed(2)}%p)` : (Number.isFinite(currentRate) ? '유지' : '')
        ].filter(Boolean).join(' · ');
        if (summaryLine.textContent) meta.appendChild(summaryLine);

        const detailChanges = Array.isArray(majorChange.detail_changes) ? majorChange.detail_changes : [];
        detailChanges.forEach((detail) => {
          const detailLine = document.createElement('div');
          detailLine.className = 'right-panel-disclosures__line';
          const detailLeft = document.createElement('span');
          detailLeft.textContent = [detail.name || '', detail.relation || '', detail.reason || ''].filter(Boolean).join(' · ');
          detailLine.appendChild(detailLeft);
          const detailRight = document.createElement('span');
          const delta = Number(detail.share_delta);
          detailRight.textContent = Number.isFinite(delta)
            ? `${delta > 0 ? '+' : ''}${Math.round(delta).toLocaleString('ko-KR')}주`
            : '';
          if (detailRight.textContent) detailLine.appendChild(detailRight);
          if (detailLine.textContent) row.appendChild(detailLine);
        });
      }

      const holdings = Array.isArray(item.executive_shareholdings) ? item.executive_shareholdings : [];
      holdings.forEach((detail) => {
        const person = String(detail.repror || '').trim();
        const position = String(detail.isu_exctv_ofcps || '').trim();
        const currentShares = String(detail.sp_stock_lmp_cnt || '').trim();
        const shareDelta = String(detail.sp_stock_lmp_irds_cnt || '').trim();
        const currentRate = String(detail.sp_stock_lmp_rate || '').trim();
        const personLine = document.createElement('div');
        personLine.className = 'right-panel-disclosures__line';
        personLine.textContent = [person, position].filter(Boolean).join(' · ');
        const holdingLine = document.createElement('span');
        holdingLine.textContent = [
          currentShares ? `${currentShares}주` : '',
          shareDelta ? `${shareDelta}주` : '',
          currentRate ? `${currentRate}%` : ''
        ].filter(Boolean).join(' · ');
        if (holdingLine.textContent) meta.appendChild(holdingLine);
        if (keywordLine.textContent) personLine.appendChild(keywordLine);
        if (personLine.textContent) row.appendChild(personLine);
      });

      if (String(item.form || '').toUpperCase() === '4') {
        const person = String(item.person || '').trim();
        const position = String(item.officer_title || '').trim();
        const personLine = document.createElement('div');
        personLine.className = 'right-panel-disclosures__line';
        const personLeft = document.createElement('span');
        personLeft.textContent = [person, position].filter(Boolean).join(' · ');
        personLine.appendChild(personLeft);

        const transactions = Array.isArray(item.transactions) ? item.transactions : [];
        let totalShares = 0;
        let totalValue = 0;
        transactions.forEach((transaction) => {
          const shares = Number(String(transaction.shares || '').replaceAll(',', ''));
          const price = Number(String(transaction.price || '').replaceAll(',', ''));
          if (Number.isFinite(shares)) totalShares += shares;
          if (Number.isFinite(shares) && Number.isFinite(price)) totalValue += shares * price;
        });
        if (transactions.length) {
          const totalValueText = totalValue >= 1000000
            ? `약 $${(totalValue / 1000000).toLocaleString('en-US', { maximumFractionDigits: 2 })}M`
            : (totalValue > 0 ? `약 $${Math.round(totalValue).toLocaleString('en-US')}` : '');
          const transactionLine = document.createElement('span');
          transactionLine.textContent = [
            totalShares > 0 ? `총 ${Math.round(totalShares).toLocaleString('en-US')}주` : '',
            totalValueText
          ].filter(Boolean).join(' · ');
          if (transactionLine.textContent) meta.appendChild(transactionLine);
        }
        if (keywordLine.textContent) personLine.appendChild(keywordLine);
        if (personLine.textContent) row.appendChild(personLine);
      } else if (!holdings.length && keywordLine.textContent) {
        const keywordOnlyLine = document.createElement('div');
        keywordOnlyLine.className = 'right-panel-disclosures__line';
        if (String(item.form || '').toUpperCase() === '8-K') {
          keywordOnlyLine.appendChild(document.createElement('span'));
        }
        keywordOnlyLine.appendChild(keywordLine);
        row.appendChild(keywordOnlyLine);
      }
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
    relatedNewsItems = selectRelatedNewsItems(items, 20);
    // 분석이 끝났다는 이유만으로 오른쪽 패널을 열거나 화면을 바꾸지 않는다.
    // 사용자가 메뉴에서 '뉴스'를 선택했을 때만 목록을 표시한다.
    if (activeTabId === 'panel-workspace' && panelWorkspaceView === 'news') renderRelatedNewsPanel();
  }
  function setActiveTab(id, persist = true) { if (!tabs.some(t => t.id === id)) return; activeTabId = id; tabs.forEach(tab => { if (tab.id !== 'panel-workspace' && !getView(tab.id)) makePlaceholderView(tab); }); document.querySelectorAll('[data-tab-view]').forEach(view => { const active = view.dataset.tabView === activeTabId; view.hidden = !active; view.setAttribute('aria-hidden', active ? 'false' : 'true'); }); renderTabs(); if (activeTabId === 'panel-workspace') renderPanelWorkspaceView(); if (persist) saveState(); }
  function nextCustomLabel() { let n = 1; const existing = new Set(tabs.map(t => t.label)); while (existing.has(`분석 #${n}`)) n += 1; return `분석 #${n}`; }
  function addTab() { const id = `tab_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`; const tab = { id, label: nextCustomLabel(), icon: 'square-chart-gantt', closable: true }; tabs.push(tab); makePlaceholderView(tab); setActiveTab(id); }
  function removeTab(id) { const index = tabs.findIndex(t => t.id === id); if (index === -1 || tabs[index].closable === false || tabs.length <= 1) return; const wasActive = activeTabId === id; tabs.splice(index, 1); const view = getView(id); if (view) view.remove(); if (wasActive) activeTabId = (tabs[Math.max(0, index - 1)] || tabs[0]).id; setActiveTab(activeTabId); }
  function initialize() {
    normalizeLegacyPanelWorkspaceDom();
    if (!getTabList() || !getContentRoot() || getTabList().dataset.bound === 'true') return;
    const stored = readState(); tabs = stored?.tabs?.length ? stored.tabs : DEFAULT_TABS.map(t => ({ ...t })); activeTabId = tabs.some(t => t.id === stored?.activeTabId) ? stored.activeTabId : 'panel-workspace'; panelWorkspaceView = ''; savePanelWorkspaceView();
    tabs.forEach(tab => { if (tab.id !== 'panel-workspace') makePlaceholderView(tab); });
    getTabList().addEventListener('click', event => { const toggle = event.target.closest('[data-panel-workspace-menu-toggle]'); if (toggle) { event.stopPropagation(); togglePanelWorkspaceMenu(); return; } const viewButton = event.target.closest('[data-panel-workspace-view]'); if (viewButton) { event.stopPropagation(); selectPanelWorkspaceView(viewButton.dataset.panelWorkspaceView); return; } const close = event.target.closest('[data-close-tab-id]'); if (close) { event.stopPropagation(); removeTab(close.dataset.closeTabId); return; } const tab = event.target.closest('[data-right-panel-tab]'); if (tab) { togglePanelWorkspaceMenu(false); setActiveTab(tab.dataset.rightPanelTab); } });
    document.addEventListener('click', event => { if (!event.target.closest('#rightPanelTabs')) togglePanelWorkspaceMenu(false); }); getTabList().dataset.bound = 'true'; setActiveTab(activeTabId, false); saveState();
  }
  window.GaemiGTPRightPanelTabs = { initialize, addTab, addNamedTab, selectPanelWorkspaceView, removeTab, setActiveTab, showRelatedNews, showRelatedDisclosures, getTabs: () => tabs.map(tab => ({ ...tab })), getActiveTab: () => activeTabId };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize, { once: true }); else initialize();
})();
