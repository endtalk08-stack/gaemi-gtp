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
  let disclosuresRenderVersion = 0;
  const PANEL_WORKSPACE_VIEWS = { 'panel-workspace': { label: '대시보드', icon: 'layout-dashboard' }, news: { label: '뉴스', icon: 'newspaper' }, 'overseas-stock': { label: '해외 종목', icon: 'globe' }, disclosures: { label: '공시', icon: 'file-text' } };
  const TRADINGVIEW_NVDA_TEST_NEWS = [
    {
      id: "tag:reuters.com,2026:newsml_L3N46G1VX:0",
      title: "AI 투자에 대한 우려가 커지면서 나스닥, 10월에 2조 달러 규모의 시가총액 폭락 위기에 직면",
      source: "Reuters", published_at: "2026-10-30T15:07:45+00:00", permission: "headline",
      related_symbols: ["NASDAQ:NVDA"],
      link: "https://www.tradingview.com/news/reuters.com,2026:newsml_L3N46G1VX:0/"
    },
    {
      id: "tag:reuters.com,2026:newsml_L3N46G1O0:0",
      title: "인텔, 사상 최악의 하루를 맞이할 전망… 전 세계 반도체 시장 폭락 촉발",
      source: "Reuters", published_at: "2026-10-30T13:26:15+00:00", permission: "headline",
      related_symbols: ["NASDAQ:NVDA"],
      link: "https://www.tradingview.com/news/reuters.com,2026:newsml_L3N46G1O0:0/"
    },
    {
      id: "tag:reuters.com,2026:newsml_L3N46G1CT:0",
      title: "인텔의 경고로 반도체주가 급락… PC 시장 부진이 회복세에 먹구름 드리워",
      source: "Reuters", published_at: "2026-10-30T11:24:37+00:00", permission: "headline",
      related_symbols: ["NASDAQ:NVDA"],
      link: "https://www.tradingview.com/news/reuters.com,2026:newsml_L3N46G1CT:0/"
    },
    {
      id: "tag:reuters.com,2026:newsml_L3N46G126:0",
      title: "아시아 반도체 기업들, AI 수요 호조 전망…시장 불안 지속",
      source: "Reuters", published_at: "2026-10-30T09:38:43+00:00", permission: "headline",
      related_symbols: ["NASDAQ:NVDA"],
      link: "https://www.tradingview.com/news/reuters.com,2026:newsml_L3N46G126:0/"
    },
    {
      id: "tag:reuters.com,2026:newsml_L3N46G0VP:0",
      title: "폭스콘, 오픈AI와 새로운 제휴 추진 중… “AI 버블은 없다”고 밝혀",
      source: "Reuters", published_at: "2026-10-30T08:35:03+00:00", permission: "headline",
      related_symbols: ["NASDAQ:NVDA"],
      link: "https://www.tradingview.com/news/reuters.com,2026:newsml_L3N46G0VP:0/"
    },
    {
      id: "tag:reuters.com,2026:newsml_L3N46G061:0",
      title: "인도 AI 기업, 엔비디아 칩 발주를 위해 30억 달러 자금 조달 추진 - 블룸버그 뉴스",
      source: "Reuters", published_at: "2026-10-30T01:54:43+00:00", permission: "headline",
      related_symbols: ["NASDAQ:NVDA"],
      link: "https://www.tradingview.com/news/reuters.com,2026:newsml_L3N46G061:0/"
    },
    {
      id: "tag:reuters.com,2026:newsml_L3N46G04I:0",
      title: "‘더 인포메이션’ 보도에 따르면, 엔비디아가 엔스케일(Nscale)과 앤트로픽(Anthropic) 간의 거래에 대한 신용 지원을 제공하기 위해 협의 중이라고 한다.",
      source: "Reuters", published_at: "2026-10-30T01:17:27+00:00", permission: "headline",
      related_symbols: ["NASDAQ:NVDA"],
      link: "https://www.tradingview.com/news/reuters.com,2026:newsml_L3N46G04I:0/"
    },
    {
      id: "tag:reuters.com,2026:newsml_L6N46F1HG:0",
      title: "인텔, 이스라엘 공장 폭발 사고와 PC 시장 부진으로 시간외서 주가 21% 급락",
      source: "Reuters", published_at: "2026-10-29T23:50:54+00:00", permission: "headline",
      related_symbols: ["NASDAQ:NVDA"],
      link: "https://www.tradingview.com/news/reuters.com,2026:newsml_L6N46F1HG:0/"
    },
    {
      id: "hankyung:9cc1fb2f065a7:0",
      title: "AI에 천문학적 돈 쏟아부었는데…알파벳, 하루 새 669조 증발 '패닉'",
      source: "Hankyung", published_at: "2026-10-29T23:26:55+00:00", permission: "",
      related_symbols: ["NASDAQ:NVDA"],
      description: "구글 모회사 알파벳 주가가 29일(현지시간) 검색 수익화 부진과 인공지능(AI) 투자 우려에 상장 이후 최대 하락률을 기록했다.",
      link: "https://www.tradingview.com/news/hankyung:9cc1fb2f065a7:0/"
    }
  ];

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
      const customTabs = state.tabs.filter(t => t && typeof t.id === 'string' && t.id.startsWith('tab_') && typeof t.label === 'string').map(t => ({ id: t.id, label: t.label, icon: typeof t.icon === 'string' ? t.icon : 'square-chart-gantt', closable: true }));
      const cleanTabs = [...DEFAULT_TABS.map(t => ({ ...t })), ...customTabs];
      return { tabs: cleanTabs, activeTabId: typeof state.activeTabId === 'string' ? state.activeTabId : 'panel-workspace' };
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
    if (panelWorkspaceView === 'news') { loadActiveStockNews(); return; }
    if (panelWorkspaceView === 'overseas-stock') { root.innerHTML = '<section class="right-panel-related-news" aria-label="해외 종목 뉴스"><div class="right-panel-related-news__empty">해외 종목 뉴스는 아직 연결되지 않았습니다.</div></section>'; return; }
    if (panelWorkspaceView === 'disclosures') { renderRelatedDisclosuresPanel(); return; }
  }
  function renderTabs() {
    const list = getTabList(); if (!list) return; list.innerHTML = '';
    tabs.forEach(tab => {
      if (tab.id === 'panel-workspace') {
        const wrap = document.createElement('div'); wrap.className = 'right-panel-workspace-menu-wrap';
        const button = document.createElement('button'); button.type = 'button'; button.className = 'right-panel-tab-add'; button.dataset.panelWorkspaceMenuToggle = 'true'; button.setAttribute('aria-label', '패널 메뉴'); button.setAttribute('aria-expanded', 'false'); button.title = '패널 메뉴'; button.innerHTML = '<i data-lucide="ellipsis"></i>'; wrap.appendChild(button);
        const menu = document.createElement('div'); menu.className = 'right-panel-tab-menu right-panel-workspace-menu'; menu.dataset.panelWorkspaceMenu = 'true'; menu.hidden = true; menu.innerHTML = `<button type="button" class="right-panel-tab-menu__item" data-panel-workspace-view="panel-workspace"><span>대시보드</span></button><button type="button" class="right-panel-tab-menu__item" data-panel-workspace-view="news"><span>종목뉴스</span></button><details class="right-panel-workspace-group"><summary class="right-panel-tab-menu__item" style="justify-content:space-between;list-style:none"><span>해외</span><span aria-hidden="true">▾</span></summary><button type="button" class="right-panel-tab-menu__item" style="padding-left:28px" data-panel-workspace-view="overseas-stock"><span>종목</span></button></details><button type="button" class="right-panel-tab-menu__item" data-panel-workspace-view="disclosures"><span>공시</span></button>`; wrap.appendChild(menu); list.appendChild(wrap); return;
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
      Array.isArray(snapshot?.panelDisclosures) && snapshot.panelDisclosures.length
        ? snapshot.panelDisclosures
        : (Array.isArray(snapshot?.panelUsFilings) ? snapshot.panelUsFilings : [])
    );
  }
  function selectRelatedNewsItems(items, limit = 20, officialReserve = 4) {
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

    let officialCount = 0;
    for (const item of byLatest) {
      if (officialCount >= officialReserve) break;
      if (item?.source_type !== 'official_company') continue;
      if (pushItem(item)) officialCount += 1;
    }

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
    // One-shot, real TradingView API snapshot from the approved DigitalOcean gateway test.
    // Headline-only items intentionally show no body text; each item links to its TradingView story.
    relatedNewsItems = TRADINGVIEW_NVDA_TEST_NEWS.map(item => ({ ...item }));
    renderRelatedNewsPanel();
  }
  function selectPanelWorkspaceView(type) {
    if (!PANEL_WORKSPACE_VIEWS[type]) return;
    panelWorkspaceView = type;
    if (type === 'disclosures') loadActiveStockDisclosures();
    setActiveTab('panel-workspace');
    savePanelWorkspaceView();
    togglePanelWorkspaceMenu(false);
    if (type === 'news') loadActiveStockNews();
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
    section.setAttribute('aria-label', '엔비디아 종목뉴스');

    const heading = document.createElement('h3');
    heading.className = 'right-panel-related-news__heading';
    heading.textContent = '엔비디아 (NASDAQ:NVDA) · TradingView 뉴스';
    section.appendChild(heading);

    const note = document.createElement('div');
    note.className = 'right-panel-related-news__meta';
    note.textContent = '실제 API 1회 수신 · 목록 200건 · 상위 10건 중 NVDA 연관 9건 · 자동 갱신 전';
    section.appendChild(note);

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
        article.appendChild(title);

        const descriptionText = item.description || item.summary || '';
        if (descriptionText) {
          const description = document.createElement('div');
          description.className = 'right-panel-related-news__description';
          description.textContent = descriptionText;
          article.appendChild(description);
        }

        const permissionLabel = item.permission === 'headline' ? '제목 제공' : '';
        const meta = document.createElement('div');
        meta.className = 'right-panel-related-news__meta';
        meta.textContent = [item.source || '뉴스', formatNewsDate(item.published_at), permissionLabel].filter(Boolean).join(' · ');
        article.appendChild(meta);
        list.appendChild(article);
      });
      section.appendChild(list);
    }
    root.appendChild(section);
  }
  async function renderRelatedDisclosuresPanel() {
    const root = document.getElementById('rightPanelWorkspace');
    if (!root) return;
    const renderVersion = ++disclosuresRenderVersion;
    const items = relatedDisclosureItems;
    const missingSecRows = [];
    root.innerHTML = '';
    if (window.GaemiGTPDisclosures?.hydrateDartDetails) {
      // Keep the original detail budget while showing only the rolling 24-hour window.
      await window.GaemiGTPDisclosures.hydrateDartDetails(items, 30);
    }
    // 다른 종목이나 메뉴를 선택하는 동안 완료된 이전 상세 요청은 무시한다.
    if (renderVersion !== disclosuresRenderVersion || panelWorkspaceView !== 'disclosures') return;
    const section = document.createElement('section');
    section.className = 'right-panel-related-news right-panel-disclosures';
    section.setAttribute('aria-label', '한달 공시');
    const list = document.createElement('div');
    list.className = 'right-panel-related-news__list';
    items.forEach((item) => {
      const row = document.createElement('div');
      row.className = 'right-panel-related-news__item right-panel-disclosures__item';

      const title = document.createElement('div');
      title.className = 'right-panel-disclosures__line right-panel-disclosures__title';
      title.textContent = window.GaemiGTPDisclosures?.secFilingTitle?.(item) || item.title || '공시 제목 확인 필요';

      const meta = document.createElement('div');
      meta.className = 'right-panel-disclosures__line';
      const metaLeft = document.createElement('span');
      metaLeft.textContent = [item.date || '', item.time || '', item.source || '공시'].filter(Boolean).join(' · ');
      meta.appendChild(metaLeft);

      const keywords = Array.isArray(item.keywords) ? item.keywords.filter(Boolean) : [];
      const keywordLine = document.createElement('span');
      keywordLine.textContent = keywords.map((keyword) => `#${keyword}`).join(' ');

      row.append(title, meta);

      if (['8-K', '8-K/A'].includes(String(item.form || '').toUpperCase())) {
        const keyPoints = Array.isArray(item.key_points_ko) ? item.key_points_ko.filter(Boolean).slice(0, 3) : [];
        if (!keyPoints.length && String(item.sec_items || '').trim()) {
          const itemLine = document.createElement('div');
          itemLine.className = 'right-panel-disclosures__line';
          itemLine.textContent = 'SEC 공시 항목 · ' + String(item.sec_items).trim();
          row.appendChild(itemLine);
        }
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

      if (['4', '4/A'].includes(String(item.form || '').toUpperCase())) {
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

        // SEC Table II represents rights (RSUs/options), NOT another executed
        // stock sale. Show them separately, never double-count in cash shares.
        const derivatives = Array.isArray(item.derivative_transactions)
          ? item.derivative_transactions : [];
        const derivativeGroups = new Map();
        derivatives.forEach((transaction) => {
          const security = String(transaction.security || '').trim();
          const type = /restricted stock unit|^rsu$/i.test(security)
            ? 'RSU' : (security || '파생증권');
          const direction = String(transaction.acquired_disposed || '').toUpperCase() === 'D'
            ? '처분' : '취득';
          const code = String(transaction.code || '').toUpperCase();
          const verb = code === 'M' ? '행사' : direction;
          const key = [type, verb, code].join('|');
          const rawShares = String(transaction.shares || '').replaceAll(',', '');
          const amount = rawShares.trim() && Number.isFinite(Number(rawShares))
            ? Number(rawShares) : null;
          const group = derivativeGroups.get(key) || { type, verb, count: 0, units: 0, hasUnits: false };
          group.count += 1;
          if (amount !== null) {
            group.units += amount;
            group.hasUnits = true;
          }
          derivativeGroups.set(key, group);
        });
        derivativeGroups.forEach((group) => {
          const line = document.createElement('div');
          line.className = 'right-panel-disclosures__line';
          const left = document.createElement('span');
          left.textContent = group.type + ' ' + group.verb + ' · ' + group.count + '건';
          line.appendChild(left);
          if (group.hasUnits) {
            const right = document.createElement('span');
            right.textContent = Math.round(group.units).toLocaleString('ko-KR') + '단위';
            line.appendChild(right);
          }
          row.appendChild(line);
        });
      } else if (!holdings.length && keywordLine.textContent) {
        const keywordOnlyLine = document.createElement('div');
        keywordOnlyLine.className = 'right-panel-disclosures__line';
        if (String(item.form || '').toUpperCase() === '8-K') {
          keywordOnlyLine.appendChild(document.createElement('span'));
        }
        keywordOnlyLine.appendChild(keywordLine);
        row.appendChild(keywordOnlyLine);
      }
      if (String(item.source || '').toUpperCase() === 'SEC' &&
          ['144', '10-Q', '10-K'].includes(String(item.form || '').toUpperCase()) &&
          item.link) {
        const extra = document.createElement('div');
        row.appendChild(extra);
        missingSecRows.push({ item, target: extra });
      }
      list.appendChild(row);
    });
    section.appendChild(list);
    root.appendChild(section);
    if (missingSecRows.length) {
      void window.GaemiGTPDisclosures?.hydrateMissingSecDetails?.(
        missingSecRows,
        () => renderVersion === disclosuresRenderVersion && panelWorkspaceView === 'disclosures'
      );
    }
  }
  function showRelatedDisclosures(items) {
    relatedDisclosureItems = Array.isArray(items) ? items : [];
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
  function syncActiveStockPanels() {
    // 화면별 재수집 없이 기존 분석 데이터 변경을 현재 열린 메뉴에 반영한다.
    if (panelWorkspaceView === 'news') loadActiveStockNews();
    else if (panelWorkspaceView === 'disclosures') {
      loadActiveStockDisclosures();
      void renderRelatedDisclosuresPanel();
    }
  }
  window.addEventListener('gaemi-analysis-data-change', syncActiveStockPanels);
  window.GaemiGTPRightPanelTabs = { initialize, addTab, addNamedTab, selectPanelWorkspaceView, removeTab, setActiveTab, showRelatedDisclosures, getTabs: () => tabs.map(tab => ({ ...tab })), getActiveTab: () => activeTabId };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initialize, { once: true }); else initialize();
})();
