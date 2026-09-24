// Frontend is served by GitHub Pages; analysis API runs on Render.
const BACKEND_URL = 'https://gaemi-gtp.onrender.com';
    const PANEL_WIDTH_KEY = 'gaemiGTP_panel_width_v3';
    let activeAnalysisController = null;
    let activeStock = '삼성전자';
    let activeAnalysisRequestId = 0;
    let currentChartInstance = null;
    let currentAppMode = 'gaemi';
    let workspaceUIReady = false;
    let restoringWorkspaceState = false;
    const WORKSPACE_STATE_KEY = 'gaemiGTP_workspace_state_v1';

    function getWorkspace() {
      return document.getElementById('gaemiWorkspace');
    }

    function setPanelWidth(px) {
      const workspace = getWorkspace();
      if (!workspace) return;
      const rect = workspace.getBoundingClientRect();
      const minMainWidth = window.innerWidth < 1024 ? 0 : 360;
      const maxWidth = Math.max(280, Math.min(1200, rect.width - minMainWidth - 5));
      const width = Math.max(280, Math.min(Number(px) || 360, maxWidth));
      const rounded = Math.round(width);
      workspace.style.setProperty('--right-panel-width', `${rounded}px`);
      localStorage.setItem(PANEL_WIDTH_KEY, String(rounded));
    }

    function readWorkspaceState() {
      try {
        const raw = localStorage.getItem(WORKSPACE_STATE_KEY);
        if (!raw) return null;
        const state = JSON.parse(raw);
        if (!state || typeof state !== 'object') return null;
        return state;
      } catch (e) {
        console.warn('[gaemiGTP] workspace state read warning:', e);
        return null;
      }
    }

    function saveWorkspaceState() {
      if (restoringWorkspaceState) return;
      try {
        const heroView = document.getElementById('mainHeroView');
        const workspace = getWorkspace();
        const panelOpen = document.body.classList.contains('right-panel-open');
        const panelMaximized = document.body.classList.contains('right-panel-maximized');
        const state = {
          mode: document.body.classList.contains('analysis-mode') && heroView && heroView.classList.contains('hidden') ? 'analysis' : 'home',
          stock: activeStock || '삼성전자',
          leftMarketOpen: document.body.classList.contains('left-market-open'),
          rightPanelOpen: panelOpen,
          rightPanelMaximized: panelOpen && panelMaximized,
          panelWidth: workspace ? parseInt(getComputedStyle(workspace).getPropertyValue('--right-panel-width') || '360', 10) : 360,
          appMode: currentAppMode || 'gaemi'
        };
        if (!Number.isFinite(state.panelWidth)) state.panelWidth = 360;
        localStorage.setItem(WORKSPACE_STATE_KEY, JSON.stringify(state));
      } catch (e) {
        console.warn('[gaemiGTP] workspace state save warning:', e);
      }
    }

    function applySidebarState() {
      const market = document.getElementById('leftMarketSidebar');
      const panel = document.getElementById('rightPanel');
      const resizer = document.getElementById('rightPanelResizer');
      const backdrop = document.getElementById('sidebarBackdrop');
      const marketOpen = document.body.classList.contains('left-market-open');
      const panelOpen = document.body.classList.contains('right-panel-open');
      const mobile = window.innerWidth < 1024;
      const heroView = document.getElementById('mainHeroView');
      const onHero = !!heroView && !heroView.classList.contains('hidden');
      document.body.classList.toggle('left-market-closed', !marketOpen);
      document.body.classList.toggle('right-panel-closed', !panelOpen);

      if (market) market.setAttribute('aria-hidden', marketOpen ? 'false' : 'true');
      if (panel) panel.setAttribute('aria-hidden', panelOpen ? 'false' : 'true');
      const panelMaximized = document.body.classList.contains('right-panel-maximized');
      document.querySelectorAll('[data-panel-maximize-icon="maximize"]').forEach(el => el.classList.toggle('hidden', panelMaximized));
      document.querySelectorAll('[data-panel-maximize-icon="restore"]').forEach(el => el.classList.toggle('hidden', !panelMaximized));
      if (resizer) {
        resizer.classList.toggle('is-open', panelOpen);
        resizer.classList.toggle('hidden', !panelOpen);
        resizer.style.display = panelOpen ? '' : 'none';
      }
      if (panel) {
        panel.classList.toggle('hidden', !panelOpen);
        panel.style.display = panelOpen ? '' : 'none';
      }

      document.querySelectorAll('[data-panel-toggle-icon="closed"]').forEach(el => el.classList.toggle('hidden', panelOpen));
      document.querySelectorAll('[data-panel-toggle-icon="open"]').forEach(el => el.classList.toggle('hidden', !panelOpen));
      document.querySelectorAll('[data-left-sidebar-toggle]').forEach(el => {
        const top = el.getAttribute('data-left-sidebar-top');
        const shouldShow = top === 'hero' ? onHero : !onHero;
        el.classList.toggle('hidden', !shouldShow);
        el.setAttribute('aria-hidden', shouldShow ? 'false' : 'true');
        el.tabIndex = shouldShow ? 0 : -1;
      });

      document.querySelectorAll('[data-panel-header-toggle]').forEach(el => {
        el.setAttribute('aria-label', panelOpen ? '패널 닫기' : '패널 열기');
        el.setAttribute('title', panelOpen ? '패널 닫기' : '패널 열기');
        const top = el.getAttribute('data-panel-top');
        const shouldShow = top === 'hero' ? onHero : !onHero;
        el.classList.toggle('hidden', !shouldShow);
        el.setAttribute('aria-hidden', shouldShow ? 'false' : 'true');
        el.tabIndex = shouldShow ? 0 : -1;
      });

      // 모바일에서만 시장정보가 오버레이가 되며, 패널은 항상 workspace 오른쪽에 붙는다.
      if (backdrop) backdrop.classList.toggle('hidden', !(mobile && marketOpen));
      if (window.lucide) lucide.createIcons();
      saveWorkspaceState();
    }

    function resetToHome() {
      document.getElementById('mainHeroView').classList.remove('hidden');
      document.body.classList.remove('analysis-mode');
      document.body.classList.remove('left-market-open','right-panel-open','right-panel-maximized');
      applySidebarState();
    }

    function switchToAnalysisMode(stockName) {
      document.getElementById('mainHeroView').classList.add('hidden');
      document.body.classList.add('analysis-mode');

      // 홈 → 종목분석으로 이동할 때 현재 Workspace 상태를 그대로 보존한다.
      // 사용자가 열어둔 왼쪽 시장정보/오른쪽 패널을 임의로 닫지 않는다.
      // 화면 이동은 '분석 화면으로 전환'만 담당하고, 사이드바 상태는 사용자의 선택을 따른다.
      applySidebarState();
      requestStock(stockName || '삼성전자');
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

    function handleHeroSearch() {
      const val = document.getElementById('heroStockInput').value;
      switchToAnalysisMode(val || '삼성전자');
    }

    function handleBottomSearch() {
      const val = document.getElementById('bottomStockInput').value;
      if (val) {
        requestStock(val);
        document.getElementById('bottomStockInput').value = '';
      }
    }

    function toggleModeDropdown(which) {
      const heroMenu = document.getElementById('heroModeMenu');
      const bottomMenu = document.getElementById('bottomModeMenu');
      if (which === 'hero') {
        heroMenu.classList.toggle('hidden');
        if (bottomMenu) bottomMenu.classList.add('hidden');
      } else {
        bottomMenu.classList.toggle('hidden');
        if (heroMenu) heroMenu.classList.add('hidden');
      }
    }

    function selectAppMode(mode) {
      currentAppMode = mode;
      document.getElementById('heroModeLabel').innerText = mode;
      document.getElementById('bottomModeLabel').innerText = mode;
      ['gaemi', 'info', 'pro'].forEach(m => {
        const hChk = document.getElementById(`chk-hero-${m}`);
        const bChk = document.getElementById(`chk-bottom-${m}`);
        if (hChk) hChk.classList.toggle('hidden', m !== mode);
        if (bChk) bChk.classList.toggle('hidden', m !== mode);
      });
      document.getElementById('heroModeMenu').classList.add('hidden');
      document.getElementById('bottomModeMenu').classList.add('hidden');
    }

    function toggleLeftSidebar() {
      if (!workspaceUIReady) return;
      const isOpen = document.body.classList.contains('left-market-open');
      if (!isOpen && window.innerWidth < 1024) {
        document.body.classList.remove('right-panel-open', 'right-panel-maximized');
      }
      document.body.classList.toggle('left-market-open', !isOpen);
      applySidebarState();
    }

    function toggleRightPanel() {
      const isOpen = document.body.classList.contains('right-panel-open');
      if (isOpen) {
        document.body.classList.remove('right-panel-open', 'right-panel-maximized');
      } else {
        if (window.innerWidth < 1024) {
          document.body.classList.remove('left-market-open');
        }
        document.body.classList.add('right-panel-open');
      }
      applySidebarState();
    }

    function toggleRightPanelMaximize() {
      if (!document.body.classList.contains('right-panel-open')) {
        if (window.innerWidth < 1024) {
          document.body.classList.remove('left-market-open');
        }
        document.body.classList.add('right-panel-open');
      }
      const maximized = document.body.classList.toggle('right-panel-maximized');
      const button = document.querySelector('[data-panel-maximize]');
      if (button) {
        button.setAttribute('aria-label', maximized ? '패널 원래 크기로' : '패널 최대화');
        button.setAttribute('title', maximized ? '패널 원래 크기로' : '패널 최대화');
      }
      if (!maximized) {
        const savedWidth = parseInt(localStorage.getItem(PANEL_WIDTH_KEY) || '360', 10);
        requestAnimationFrame(() => setPanelWidth(Number.isFinite(savedWidth) ? savedWidth : 360));
      }
      applySidebarState();
    }

    function closeAllSidebars() {
      document.body.classList.remove('left-market-open','right-panel-open','right-panel-maximized');
      applySidebarState();
    }

    function initializeSidebars() {
      // 새로고침해도 마지막 화면/종목/사이드바/패널 상태를 그대로 복원한다.
      const saved = readWorkspaceState();
      restoringWorkspaceState = true;

      document.body.classList.remove('left-market-open','right-panel-open','right-panel-maximized','analysis-mode');

      const heroView = document.getElementById('mainHeroView');
      if (saved?.mode === 'analysis' && heroView) {
        heroView.classList.add('hidden');
        document.body.classList.add('analysis-mode');
      } else if (heroView) {
        heroView.classList.remove('hidden');
      }

      if (saved?.leftMarketOpen) document.body.classList.add('left-market-open');
      if (saved?.rightPanelOpen) document.body.classList.add('right-panel-open');
      if (saved?.rightPanelMaximized && saved?.rightPanelOpen) {
        document.body.classList.add('right-panel-maximized');
      }
      if (typeof saved?.stock === 'string' && saved.stock.trim()) activeStock = saved.stock.trim();
      if (typeof saved?.appMode === 'string' && ['gaemi', 'info', 'pro'].includes(saved.appMode)) currentAppMode = saved.appMode;
      // 새로고침 후에도 gaemi/info/pro 선택 표시가 실제 상태와 일치하도록 복원한다.
      selectAppMode(currentAppMode);

      // 상단 토글은 DOM 초기 렌더가 끝난 뒤에만 연결한다.
      document.querySelectorAll('[data-left-sidebar-toggle]').forEach((el) => {
        if (el.dataset.sidebarListenerBound === 'true') return;
        el.addEventListener('click', (event) => {
          event.preventDefault();
          event.stopPropagation();
          toggleLeftSidebar();
        });
        el.dataset.sidebarListenerBound = 'true';
      });

      workspaceUIReady = true;
      const savedWidth = parseInt(saved?.panelWidth || localStorage.getItem(PANEL_WIDTH_KEY) || '360', 10);

      // Workspace가 렌더링된 다음 저장된 패널 폭을 적용한다.
      setTimeout(() => {
        setPanelWidth(Number.isFinite(savedWidth) ? savedWidth : 360);
        applySidebarState();
        restoringWorkspaceState = false;
        saveWorkspaceState();

        // 마지막으로 종목분석 화면을 보고 있었다면 같은 종목으로 다시 분석 화면을 구성한다.
        const currentHero = document.getElementById('mainHeroView');
        const shouldRestoreAnalysis = saved?.mode === 'analysis' && currentHero && currentHero.classList.contains('hidden');
        if (shouldRestoreAnalysis) {
          requestStock(activeStock || '삼성전자');
        }
      }, 0);
    }

    function initializeWorkspaceInteractions() {
      const workspace = getWorkspace();
      const resizer = document.getElementById('rightPanelResizer');
      const panel = document.getElementById('rightPanel');
      if (!workspace || !resizer || !panel) return;

      // 왼쪽 시장정보 열림/닫힘이나 창 크기 변경으로 Workspace 폭이 바뀌어도
      // 저장된 패널 폭이 본문을 과도하게 침범하지 않도록 자동으로 다시 맞춘다.
      if (window.ResizeObserver) {
        const observer = new ResizeObserver(() => {
          if (document.body.classList.contains('right-panel-maximized')) return;
          const current = parseInt(getComputedStyle(workspace).getPropertyValue('--right-panel-width') || '360', 10);
          setPanelWidth(Number.isFinite(current) ? current : 360);
        });
        observer.observe(workspace);
      }

      resizer.addEventListener('pointerdown', (event) => {
        if (!document.body.classList.contains('right-panel-open') || document.body.classList.contains('right-panel-maximized')) return;
        event.preventDefault();
        const rect = workspace.getBoundingClientRect();
        const onMove = (moveEvent) => {
          // 패널은 항상 workspace 오른쪽에 고정한다.
          const width = rect.right - moveEvent.clientX;
          setPanelWidth(width);
        };
        const onUp = () => {
          window.removeEventListener('pointermove', onMove);
          window.removeEventListener('pointerup', onUp);
          document.body.classList.remove('panel-resizing');
        };
        document.body.classList.add('panel-resizing');
        window.addEventListener('pointermove', onMove);
        window.addEventListener('pointerup', onUp, { once: true });
      });
    }

    function updateThemeButtons() {
      const isDark = document.documentElement.classList.contains('dark');
      document.querySelectorAll('[data-theme-icon]').forEach(icon => {
        icon.setAttribute('data-lucide', isDark ? 'sun' : 'moon');
      });
      if (window.lucide) lucide.createIcons();
    }

    function toggleTheme() {
      const htmlEl = document.documentElement;
      htmlEl.classList.toggle('dark');
      updateThemeButtons();
    }

    async function fetchAnalysisFromBackend(stockName, signal) {
      try {
        const response = await fetch(`${BACKEND_URL}/analyze?stock=${encodeURIComponent(stockName)}`, { signal });
        if (!response.ok) throw new Error('서버 에러');
        const data = await response.json();
        // 기존 뉴스/공시 수집 로직은 그대로 두고, 서버가 내려주는
        // 구조화 데이터만 프론트까지 전달한다. (표시용 변경만)
        return {
          sections: data.sections || [],
          news_items: Array.isArray(data.news_items) ? data.news_items : [],
          disclosures: Array.isArray(data.disclosures) ? data.disclosures : [],
          us_filings: Array.isArray(data.us_filings) ? data.us_filings : [],
          ok: true
        };
      } catch (err) {
        if (err?.name === 'AbortError') return { sections: [], ok: false, aborted: true };
        return { sections: [], ok: false };
      }
    }

    function renderAnalysisStatus(chatArea, stockName, ok) {
      const state = document.createElement('div');
      state.className = 'analysis-state animate-fade';
      state.innerHTML = ok ? `
        <div class="w-10 h-10 mx-auto mb-3 rounded-full bg-[#f1f5f9] dark:bg-[#27272a] flex items-center justify-center text-[#64748b] dark:text-[#a1a1aa]">
          <i data-lucide="database" class="w-5 h-5"></i>
        </div>
        <div class="font-black text-base text-[#0f172a] dark:text-white">분석 데이터가 없습니다</div>
        <div class="mt-1 text-xs text-[#64748b] dark:text-[#a1a1aa]">${stockName}에 대한 분석 내용을 준비하고 있습니다.</div>
      ` : `
        <div class="w-10 h-10 mx-auto mb-3 rounded-full bg-[#f1f5f9] dark:bg-[#27272a] flex items-center justify-center text-[#64748b] dark:text-[#a1a1aa]">
          <i data-lucide="refresh-cw" class="w-5 h-5"></i>
        </div>
        <div class="font-black text-base text-[#0f172a] dark:text-white">분석 데이터를 불러오지 못했습니다</div>
        <div class="mt-1 text-xs text-[#64748b] dark:text-[#a1a1aa]">잠시 후 다시 시도해주세요.</div>
      `;
      chatArea.appendChild(state);
      if (window.lucide) lucide.createIcons();
      return state;
    }

    async function requestStock(stockName) {
      if (!stockName || !stockName.trim()) return;
      stockName = stockName.trim();

      // 새 종목을 누르면 이전 분석 HTTP 요청을 즉시 끊어 브라우저가 오래된 응답을 기다리지 않게 한다.
      // 서버에서도 같은 종목의 중복 외부 호출은 백엔드 캐시/single-flight가 막는다.
      if (activeAnalysisController) {
        activeAnalysisController.abort();
      }
      activeAnalysisController = new AbortController();

      const requestId = ++activeAnalysisRequestId;
      activeStock = stockName;
      saveWorkspaceState();

      const chatArea = document.getElementById('chatArea');
      chatArea.innerHTML = '';
      chatArea.scrollTop = 0;

      const userDiv = document.createElement('div');
      userDiv.className = "flex justify-end animate-fade";
      userDiv.innerHTML = `<div class="bg-[#f1f5f9] dark:bg-[#1e1f24] text-[#0f172a] dark:text-white text-base font-bold px-5 py-3 rounded-2xl border border-[#cbd5e1] dark:border-[#3f3f46]">${stockName}</div>`;
      chatArea.appendChild(userDiv);

      const loaderDiv = document.createElement('div');
      loaderDiv.className = "flex flex-col items-center justify-center p-8 bg-white dark:bg-[#1e1f24] border border-[#e2e8f0] dark:border-[#27272a] rounded-3xl my-2 text-center shadow-sm animate-fade";
      loaderDiv.innerHTML = `
        <div class="flex items-center gap-4 mb-3">
          <div class="w-14 h-14 rounded-full bg-[#f8fafc] dark:bg-[#27272a] border border-[#cbd5e1] dark:border-[#3f3f46] flex items-center justify-center text-2xl animate-bounce">🐜</div>
          <span class="text-[#94a3b8] dark:text-[#71717a] font-bold text-xl">×</span>
          <div class="w-14 h-14 rounded-full bg-[#0f172a] dark:bg-white text-white dark:text-black font-black flex items-center justify-center text-2xl">🕶️</div>
        </div>
        <h4 class="font-black text-lg text-[#0f172a] dark:text-white">${stockName} 퀀트 5초 정밀 스캔 중...</h4>
      `;
      chatArea.appendChild(loaderDiv);

      const controller = activeAnalysisController;
      const fetchPromise = fetchAnalysisFromBackend(stockName, controller.signal);
      const delayPromise = new Promise(resolve => setTimeout(resolve, 120));
      const [result] = await Promise.all([fetchPromise, delayPromise]);
      if (requestId !== activeAnalysisRequestId || result.aborted) {
        loaderDiv.remove();
        return;
      }
      const sections = result.sections || [];

      loaderDiv.remove();
      if (activeAnalysisController === controller) activeAnalysisController = null;

      if (!result.ok || sections.length === 0) {
        renderAnalysisStatus(chatArea, stockName, result.ok);
        chatArea.scrollTop = 0;
        return;
      }

      const surprisePopup = document.getElementById('surpriseAntPopup');
      surprisePopup.classList.remove('hidden');
      await new Promise(res => setTimeout(res, 600));
      if (requestId !== activeAnalysisRequestId) return;
      surprisePopup.classList.add('hidden');

      chatArea.scrollTop = 0;
      startTypewriterFlow(stockName, sections, result, requestId);
    }


    function openExternalLinkModal(item) {
      const modal = document.getElementById('externalLinkModal');
      if (!modal) return;
      const href = item.original_link || item.link || item.url || item.article_url || '';
      if (!href) return;

      const title = item.title || item.description || '제목 확인 필요';
      const source = item.source || (item.form ? 'SEC' : '출처 확인 필요');
      const when = item.display_datetime || item.datetime || item.date || item.pub_date || '';
      const time = item.time || item.acceptance_time || '';
      const tz = item.time_zone || '';
      const meta = `${source}${when ? ` · ${when}` : ''}${time ? ` · ${time}${tz ? ` ${tz}` : ''}` : ''}`;

      document.getElementById('externalLinkArticleTitle').textContent = title;
      document.getElementById('externalLinkArticleMeta').textContent = meta;
      document.getElementById('externalLinkUrl').textContent = href;
      modal.dataset.href = href;
      modal.classList.add('is-open');
      modal.setAttribute('aria-hidden', 'false');
      document.body.style.overflow = 'hidden';
      if (window.lucide) window.lucide.createIcons();
    }

    function closeExternalLinkModal() {
      const modal = document.getElementById('externalLinkModal');
      if (!modal) return;
      modal.classList.remove('is-open');
      modal.setAttribute('aria-hidden', 'true');
      modal.dataset.href = '';
      document.body.style.overflow = '';
    }

    function initExternalLinkModal() {
      const modal = document.getElementById('externalLinkModal');
      const close = document.getElementById('externalLinkClose');
      const copy = document.getElementById('externalLinkCopy');
      const open = document.getElementById('externalLinkOpen');
      if (!modal) return;
      close?.addEventListener('click', closeExternalLinkModal);
      modal.addEventListener('click', (e) => {
        if (e.target === modal) closeExternalLinkModal();
      });
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal.classList.contains('is-open')) closeExternalLinkModal();
      });
      copy?.addEventListener('click', async () => {
        const href = modal.dataset.href || '';
        if (!href) return;
        try {
          await navigator.clipboard.writeText(href);
          copy.textContent = '복사됨';
          setTimeout(() => copy.textContent = '링크 복사', 1200);
        } catch (_) {
          const ta = document.createElement('textarea');
          ta.value = href; document.body.appendChild(ta); ta.select();
          document.execCommand('copy'); ta.remove();
          copy.textContent = '복사됨';
          setTimeout(() => copy.textContent = '링크 복사', 1200);
        }
      });
      open?.addEventListener('click', () => {
        const href = modal.dataset.href || '';
        if (!href) return;
        window.open(href, '_blank', 'noopener,noreferrer');
      });
    }

    // ★ 버그 완벽 수정된 텍스트 파싱 로직
    function renderSourceLists(container, result) {
      if (!container || !result) return;

      const newsItems = Array.isArray(result.news_items) ? result.news_items : [];
      const disclosureItems = Array.isArray(result.disclosures) ? result.disclosures : [];
      const usFilingItems = Array.isArray(result.us_filings) ? result.us_filings : [];
      const sourceDisclosureItems = disclosureItems.length ? disclosureItems : usFilingItems;
      const sourceCount = newsItems.length + sourceDisclosureItems.length;
      if (!sourceCount) return;

      // 기존 '출처' 접기/펼치기 UI 대신 본문과 동일한 G 섹션으로 항상 노출한다.
      const wrap = document.createElement('div');
      wrap.className = 'source-toggle-wrap animate-fade';

      const header = document.createElement('div');
      header.className = 'flex items-center gap-2.5';
      header.innerHTML = `
        <div class="w-7 h-7 sm:w-8 sm:h-8 rounded-full bg-[#0f172a] dark:bg-white text-white dark:text-black flex items-center justify-center font-black text-xs sm:text-sm shadow-sm shrink-0">G</div>
        <h4 class="font-black text-lg sm:text-xl text-[#0f172a] dark:text-white">재료는 있어?</h4>
      `;
      wrap.appendChild(header);

      const panel = document.createElement('div');
      panel.className = 'source-list-panel is-open';
      panel.setAttribute('aria-hidden', 'false');

      const makeGroup = (label, items) => {
        if (!items.length) return null;
        const group = document.createElement('div');
        group.className = 'source-list-group';

        const heading = document.createElement('div');
        heading.className = 'source-list-group-title';
        heading.textContent = label;
        group.appendChild(heading);

        const card = document.createElement('div');
        card.className = 'source-list-card';

        items.slice(0, 3).forEach(item => {
          const link = document.createElement('a');
          link.className = 'source-list-row';
          const href = item.original_link || item.link || item.url || item.article_url || '';
          if (href) {
            link.href = '#';
            link.setAttribute('role', 'button');
            link.addEventListener('click', (event) => {
              event.preventDefault();
              openExternalLinkModal(item);
            });
          } else {
            link.removeAttribute('href');
            link.setAttribute('aria-disabled', 'true');
          }

          const isInsider = label === '공시' && (
            String(item.form || '').toUpperCase() === '4' ||
            !!item.person ||
            !!item.transaction_kind ||
            !!item.transaction_summary ||
            Object.prototype.hasOwnProperty.call(item, 'transaction_count')
          );
          const main = document.createElement('div');
          main.className = 'source-list-main';
          const titleEl = document.createElement('div');
          titleEl.className = 'source-list-title';
          const meta = document.createElement('div');
          meta.className = 'source-list-meta';

          if (isInsider) {
            const kind = item.transaction_kind || '';
            const summaryText = item.transaction_summary || '';
            const count = Number(item.transaction_count || 0);
            let summary = summaryText || kind || '내부자 거래';
            if (count > 0 && !/\d+건/.test(summary) && !summary.includes(' · ')) {
              summary = `${summary} · ${count}건`;
            }
            titleEl.textContent = summary;
            titleEl.style.color = /매도/.test(summary) ? '#FF8DA1' : (/매수|취득/.test(summary) ? '#38BDF8' : '');

            const person = item.person || '회사 내부자';
            const roleMap = {
              'DIRECTOR': '이사',
              'OFFICER': '임원',
              '10% OWNER': '10% 이상 주주',
              '10% OWNER OF CLASS': '10% 이상 주주'
            };
            const rawRole = String(item.officer_title || '').trim();
            const role = roleMap[rawRole.toUpperCase()] || rawRole;
            const personEl = document.createElement('div');
            personEl.className = 'source-list-meta';
            personEl.style.marginTop = '2px';
            personEl.textContent = `${person}${role ? ` · ${role}` : ''}`;
            main.appendChild(titleEl);
            main.appendChild(personEl);
          } else {
            titleEl.textContent = item.title || item.description || '제목 확인 필요';
            main.appendChild(titleEl);
          }
          const source = isInsider ? 'SEC' : (item.source || (item.form ? 'SEC' : '출처 확인 필요'));
          const rawWhen = item.display_datetime || item.datetime || item.date || item.pub_date || '';
          let when = rawWhen;
          if (rawWhen) {
            const raw = String(rawWhen).trim();
            const ymd = raw.match(/^(\d{4})[-/.]?(\d{2})[-/.]?(\d{2})$/);
            const md = raw.match(/^(\d{1,2})[-/.](\d{1,2})$/);
            if (ymd) {
              when = `${ymd[1]}.${ymd[2]}.${ymd[3]}`;
            } else if (md) {
              when = `${Number(md[1])}/${Number(md[2])}`;
            } else {
              when = raw;
            }
          } else {
            when = '날짜 확인 필요';
          }
          const rawTime = item.time || item.acceptance_time || '';
          const timeZone = item.time_zone || '';
          const timeText = rawTime ? ` · ${rawTime}${timeZone ? ` ${timeZone}` : ''}` : '';
          meta.textContent = `${source} · ${when}${timeText}`;
          main.appendChild(meta);

          const arrow = document.createElement('i');
          arrow.setAttribute('data-lucide', 'chevron-right');
          arrow.className = 'source-list-arrow w-5 h-5';
          link.appendChild(main);
          link.appendChild(arrow);
          card.appendChild(link);
        });

        group.appendChild(card);
        return group;
      };

      const newsGroup = makeGroup('뉴스', newsItems);
      const disclosureGroup = makeGroup('공시', sourceDisclosureItems);
      if (newsGroup) panel.appendChild(newsGroup);
      if (disclosureGroup) panel.appendChild(disclosureGroup);
      wrap.appendChild(panel);

      container.appendChild(wrap);
      if (window.lucide) window.lucide.createIcons();
    }

    function startTypewriterFlow(stockName, sections, result, requestId) {
      if (requestId !== activeAnalysisRequestId) return;
      const chatArea = document.getElementById('chatArea');
      const wrapperId = 'stream-' + Date.now();

      const mainContainer = document.createElement('div');
      mainContainer.id = wrapperId;
      mainContainer.className = "space-y-7 py-2";
      chatArea.appendChild(mainContainer);

      let secIdx = 0;

      function typeNextSection() {
        if (requestId !== activeAnalysisRequestId) return;
        if (!sections || secIdx >= sections.length) {
          renderBottomWidgets(wrapperId, stockName);
          return;
        }

        const sec = sections[secIdx];
        const dynamicTitle = sec.title || '';
        const text = (sec.content || '')
          .replace(/이런 뉴스 재료와 기업 공시가 나오면서 시장이 반응하고 있는 거야/g, '')
          .replace(/\n{3,}/g, '\n\n')
          .trim();

        const textBlock = document.createElement('div');
        textBlock.className = "space-y-4 animate-fade";
        textBlock.innerHTML = `
          <div class="flex items-center gap-2.5">
            <div class="w-7 h-7 sm:w-8 sm:h-8 rounded-full bg-[#0f172a] dark:bg-white text-white dark:text-black flex items-center justify-center font-black text-xs sm:text-sm shadow-sm shrink-0">G</div>
            ${dynamicTitle ? `<h4 class="font-black text-lg sm:text-xl text-[#0f172a] dark:text-white">${dynamicTitle}</h4>` : ''}
          </div>
          <p id="p-content-${secIdx}" class="text-base sm:text-lg text-[#334155] dark:text-[#e4e4e7] leading-relaxed whitespace-pre-line typing-cursor"></p>
        `;
        mainContainer.appendChild(textBlock);

        const pEl = document.getElementById(`p-content-${secIdx}`);
        let charIdx = 0;
        const chunkSize = 25;

        function typeChunk() {
          if (requestId !== activeAnalysisRequestId) return;
          if (charIdx < text.length) {
            pEl.textContent += text.substr(charIdx, chunkSize);
            charIdx += chunkSize;
            setTimeout(typeChunk, 15);
          } else {
            pEl.classList.remove('typing-cursor');
            let formatted = pEl.textContent;

            try {
              const isCalendarSection = dynamicTitle.includes('오늘 밤, 이번주 무슨 일이 있어?');

              // 1. 실적 종목명(#오라클, #어도비 등) -> 핑크
              formatted = formatted.replace(/(#(?:오라클|어도비|엔비디아|테슬라|애플|구글|마이크로소프트|아마존|메타|일라이릴리))/g, '<span class="font-bold" style="color: #FF8DA1;">$1</span>');

              // 2. 경제 지표(#PPI, #CPI, #FOMC, #PCE, #NFP) -> 블루
              formatted = formatted.replace(/(#(?:PPI|CPI|FOMC|PCE|NFP))/g, '<span class="font-bold" style="color: #38BDF8;">$1</span>');

              // 일정 섹션 전용 색상: 기업명 해시태그는 핑크, 경제지표 해시태그는 블루
              // 다른 분석 문장/태그 색상 규칙에는 영향을 주지 않는다.
              if (isCalendarSection) {
                formatted = formatted.replace(
                  /#(?:FOMC|CPI|PPI|PCE|NFP|GDP|PMI|JOLTS|ADP|ISM)(?=\s|$)/gi,
                  '<span class="font-bold" style="color: #38BDF8;">$&</span>'
                );
                formatted = formatted.replace(
                  /#(?:실업수당청구건수|신규실업수당청구건수|실업률|고용보고서|소매판매|신규주택판매|주택착공|건축허가|원유재고)(?=\s|$)/g,
                  '<span class="font-bold" style="color: #38BDF8;">$&</span>'
                );
                formatted = formatted.replace(
                  /#([^\n·]+?)(?=\s+실적발표)/g,
                  '<span class="font-bold" style="color: #FF8DA1;">#$1</span>'
                );
              }

              // 3. 매물대 색상
              // 매물대 라벨 + 가격 전체를 같은 색으로 표시한다.
              // 이 분기는 일반 해시태그 색상보다 먼저 실행해 색상 충돌을 막는다.
              if (formatted.includes('악성 매물대') || formatted.includes('생존 매물대') || formatted.includes('#생존 지지선')) {
                // 레거시 형식
                formatted = formatted.replace(/#생존\s+지지선\s+([$]?[\d,.]+[원]?)/g, '<span style="color: #FF8DA1; font-weight: 700;">#생존 지지선 $1</span>');
                formatted = formatted.replace(/#악성\s+매물대\s+([$]?[\d,.]+[원]?)/g, '<span style="color: #38BDF8; font-weight: 700;">#악성 매물대 $1</span>');

                // 현재 형식: 가격까지 포함해 전체를 색칠
                formatted = formatted.replace(/(악성 매물대\s+[$]?[\d,.]+[원]?)/g, '<span style="color: #38BDF8; font-weight: 700;">$1</span>');
                formatted = formatted.replace(/(생존 매물대\s+[$]?[\d,.]+[원]?)/g, '<span style="color: #FF8DA1; font-weight: 700;">$1</span>');

                // 각 매물대 바로 아래 태그는 해당 매물대와 같은 색으로 표시
                const blocks = formatted.split('\n\n');
                let zoneColor = null;
                for (let i = 0; i < blocks.length; i++) {
                  const plainBlock = blocks[i].replace(/<[^>]+>/g, '');
                  if (plainBlock.includes('악성 매물대')) zoneColor = '#38BDF8';
                  else if (plainBlock.includes('생존 매물대')) zoneColor = '#FF8DA1';
                  if (zoneColor && /^\s*#/.test(plainBlock)) {
                    blocks[i] = `<span class="font-bold" style="color: ${zoneColor};">${blocks[i]}</span>`;
                  }
                }
                formatted = blocks.join('\n\n');
              }
              // 4. 수급 매매동향 및 콜/풋 옵션 색상 
              else if (formatted.includes('#외국인') || formatted.includes('#콜')) {
                let lines = formatted.split('\n\n');
                let tagLine = lines[0];
                let rest = lines.slice(1).join('\n\n');

                if (tagLine.includes('#콜')) {
                  // 미국 주식 콜/풋/비율 분할 처리 (#콜은 전체 핑크, #풋은 전체 블루)
                  const parts = tagLine.split(/\s+(?=#)/);
                  let coloredTags = parts.map(part => {
                    if (part.startsWith('#콜')) return `<span class="whitespace-nowrap font-bold" style="color: #FF8DA1;">${part}</span>`;
                    if (part.startsWith('#풋')) return `<span class="whitespace-nowrap font-bold" style="color: #38BDF8;">${part}</span>`;
                    return `<span class="whitespace-nowrap font-bold" style="color: #94a3b8;">${part}</span>`;
                  });
                  tagLine = coloredTags.join(' ');
                } else {
                  // 국내 주식 외인/기관/개인 처리
                  tagLine = tagLine.replace(/#(외국인|기관|개인)\s+([+-]?[\d,.]+(?:만주|주|관망)?)/g, function(_, name, val) {
                    let color = val.includes('+') ? '#FF8DA1' : (val.includes('-') ? '#38BDF8' : '#94a3b8');
                    return `<span class="whitespace-nowrap font-bold" style="color: ${color};">#${name} ${val}</span>`;
                  });
                }
                formatted = `<div class="flex items-center gap-2 sm:gap-4 overflow-x-auto whitespace-nowrap text-base sm:text-lg mb-3 tracking-tight">${tagLine}</div>${rest}`;
              } 
              // 5. 첫 섹션 태그 라인 오류 완전 해결
              else if (formatted.includes('#') && !formatted.includes('캘린더') && !isCalendarSection) {
                const isDown = formatted.includes('-') || formatted.includes('보합') || formatted.includes('눈치싸움') || formatted.includes('파란불') || formatted.includes('숨고르기') || formatted.includes('투매');
                const themeColor = isDown ? '#38BDF8' : '#FF8DA1';
                
                let lines = formatted.split('\n\n');
                if (lines.length > 0) {
                  let lastLine = lines[lines.length - 1];
                  // HTML 태그(<span ...>)가 이미 들어간 경우 순수 텍스트만 뽑아서 다시 색을 칠함
                  if (lastLine.includes('#') && lastLine.includes('<span')) {
                     // 1. 임시 div를 만들어 HTML 태그를 모두 벗겨냄
                     let tempDiv = document.createElement('div');
                     tempDiv.innerHTML = lastLine;
                     let rawText = tempDiv.textContent || tempDiv.innerText || "";
                     
                     // 2. 벗겨낸 순수 텍스트(예: #엔비디아 #-2.01% #숨고르기 #버텨보자)를 단어별로 다시 칠함
                     const words = rawText.split(/\s+/);
                     const newWords = words.map(w => {
                       if (w.startsWith('#')) {
                         let color = themeColor;
                         if (w.includes('+')) color = '#FF8DA1';
                         else if (w.includes('-')) color = '#38BDF8';
                         return `<span class="font-bold" style="color: ${color};">${w}</span>`;
                       }
                       return w;
                     });
                     lines[lines.length - 1] = newWords.join(' ');
                     formatted = lines.join('\n\n');
                  } else if (lastLine.includes('#')) {
                     // HTML 태그가 없을 땐 기존 방식대로 처리
                     const words = lastLine.split(/\s+/);
                     const newWords = words.map(w => {
                       if (w.startsWith('#')) {
                         let color = themeColor;
                         if (w.includes('+')) color = '#FF8DA1';
                         else if (w.includes('-')) color = '#38BDF8';
                         return `<span class="font-bold" style="color: ${color};">${w}</span>`;
                       }
                       return w;
                     });
                     lines[lines.length - 1] = newWords.join(' ');
                     formatted = lines.join('\n\n');
                  }
                }
              }

              // 6. 본문 텍스트 내 등락률 (-0.19%, +8.26% 등)
              formatted = formatted.replace(/(?:\s|^)([+-]\d+(?:\.\d+)?%)/g, function(match, p1) {
                const color = p1.startsWith('+') ? '#FF8DA1' : '#38BDF8';
                return match.replace(p1, `<span class="font-bold" style="color: ${color};">${p1}</span>`);
              });

            } catch (err) {
              console.warn("치환 예외 안전 무시:", err);
            }

            // 뉴스/공시는 본문에 다시 렌더링하지 않는다.
            // 기존 백엔드가 남긴 레거시 📰/📌 줄만 안전하게 제거하고,
            // 실제 뉴스/공시는 renderSourceLists()에서 한 번만 표시한다.
            formatted = formatted
              .replace(/(^|\n)\s*[📰📌][^\n]*(?=\n|$)/g, '$1')
              .replace(/\n{3,}/g, '\n\n')
              .trim();

            pEl.innerHTML = formatted;

            // 첫 번째 분석 문장 아래에 뉴스·공시를 독립된 클릭형 목록으로 표시한다.
            // 본문 안의 📰/📌 텍스트 파싱은 더 이상 사용하지 않는다.
            if (secIdx === 0) {
              // 태그는 본문에 있는 원래 위치를 유지하고, 뉴스/공시는 그 아래에 표시한다.
              renderSourceLists(mainContainer, result);
            }

            secIdx++;
            if (requestId === activeAnalysisRequestId) {
              setTimeout(typeNextSection, 50);
            }
          }
        }
        typeChunk();
      }

      typeNextSection();
    }

    function renderBottomWidgets(wrapperId, stockName) {
      const container = document.getElementById(wrapperId);
      const bottomDiv = document.createElement('div');
      bottomDiv.className = "space-y-6 pt-4 animate-fade";
      bottomDiv.innerHTML = `
        <div class="space-y-3">
          <div class="flex items-center gap-2.5">
            <div class="w-7 h-7 sm:w-8 sm:h-8 rounded-full bg-[#0f172a] dark:bg-white text-white dark:text-black flex items-center justify-center font-black text-xs sm:text-sm shadow-sm shrink-0">G</div>
            <h4 class="font-black text-lg sm:text-xl text-[#0f172a] dark:text-white">내일 상승 할까? 하락 할까?</h4>
          </div>

          <div class="bg-white dark:bg-[#1e1f24] border border-[#cbd5e1] dark:border-[#282a30] rounded-3xl p-5 space-y-4 shadow-sm">
            <div class="flex items-center justify-between">
              <span class="font-black text-base text-[#0f172a] dark:text-white">개미 투표</span>
              <span class="text-xs text-[#64748b] dark:text-[#a1a1aa] font-bold">내일 주가 전망</span>
            </div>
            <div class="space-y-2">
              <div class="flex items-center justify-between text-xs font-black">
                <span id="voteUpLabel" class="text-[#FF8DA1]">상승 68%</span>
                <span id="voteDownLabel" class="text-[#38BDF8]">하락 32%</span>
              </div>
              <div class="w-full h-2 bg-[#38BDF8] rounded-full overflow-hidden flex">
                <div id="voteProgressBar" class="h-full bg-[#FF8DA1] rounded-full transition-all duration-500" style="width: 68%;"></div>
              </div>
            </div>
            <div class="grid grid-cols-2 gap-3">
              <button type="button" onclick="castVote('up')" class="py-3 rounded-xl border border-[#FF8DA1] bg-[#FF8DA1]/10 hover:bg-[#FF8DA1]/20 text-[#FF8DA1] font-black text-sm transition cursor-pointer">상승 전망</button>
              <button type="button" onclick="castVote('down')" class="py-3 rounded-xl border border-[#38BDF8] bg-[#38BDF8]/10 hover:bg-[#38BDF8]/20 text-[#38BDF8] font-black text-sm transition cursor-pointer">하락 전망</button>
            </div>
          </div>
        </div>

        <div class="space-y-4">
          <div class="flex items-center gap-2.5">
            <div class="w-7 h-7 sm:w-8 sm:h-8 rounded-full bg-[#0f172a] dark:bg-white text-white dark:text-black flex items-center justify-center font-black text-xs sm:text-sm shadow-sm shrink-0">G</div>
            <h4 class="font-black text-lg sm:text-xl text-[#0f172a] dark:text-white">내 투자 스타일에 맞는 전략도 확인해바.</h4>
          </div>

          <div class="space-y-2">
            <button type="button" onclick="toggleStrategyDashboard('서학', this)" id="card-btn-서학" class="w-full text-left p-4 sm:p-5 rounded-2xl bg-white dark:bg-[#1a1b23] border border-[#cbd5e1] dark:border-[#272935] hover:border-[#ff2d78] transition shadow-sm cursor-pointer">
              <div class="flex items-center justify-between gap-3">
                <div class="flex items-center gap-3.5 sm:gap-4 min-w-0">
                  <div class="w-12 h-12 sm:w-14 sm:h-14 rounded-2xl bg-[#231b26] border border-[#482035] flex items-center justify-center shrink-0 p-1">
                    <svg viewBox="0 0 64 64" class="w-full h-full">
                      <circle cx="32" cy="38" r="17" fill="#3f3f46"/>
                      <path d="M26 23 Q18 10 13 16 M38 23 Q46 10 51 16" stroke="#71717a" stroke-width="2.5" stroke-linecap="round" fill="none"/>
                      <rect x="18" y="32" width="12" height="7" rx="2" fill="#09090b"/>
                      <rect x="34" y="32" width="12" height="7" rx="2" fill="#09090b"/>
                      <line x1="30" y1="35.5" x2="34" y2="35.5" stroke="#09090b" stroke-width="2"/>
                      <rect x="15" y="44" width="10" height="7" rx="1" fill="#ef4444"/>
                      <rect x="15" y="44" width="5" height="4" fill="#2563eb"/>
                    </svg>
                  </div>
                  <div class="space-y-0.5 min-w-0">
                    <div class="flex items-center gap-2">
                      <span class="font-black text-base sm:text-lg text-[#0f172a] dark:text-white truncate">서학개미</span>
                      <span class="text-[11px] font-bold px-2 py-0.5 rounded-full bg-[#ff2d78]/10 text-[#ff2d78] border border-[#ff2d78]/30 shrink-0">장기</span>
                    </div>
                    <p class="text-xs sm:text-sm text-[#64748b] dark:text-[#a1a1aa] font-medium truncate">좋은 기업을 길게, 시간이 수익을 만든다.</p>
                  </div>
                </div>
                <div class="text-right shrink-0 border-l border-[#e2e8f0] dark:border-[#2b2e3c] pl-3 sm:pl-6">
                  <div class="text-[11px] text-[#94a3b8] dark:text-[#71717a] font-bold">10년 누적 성과</div>
                  <div class="text-base sm:text-lg font-black text-[#ff2d78]">+2,335%</div>
                </div>
              </div>
            </button>
            <div id="dash-slot-서학" class="hidden animate-fade"></div>
          </div>

          <div class="space-y-2">
            <button type="button" onclick="toggleStrategyDashboard('국장', this)" id="card-btn-국장" class="w-full text-left p-4 sm:p-5 rounded-2xl bg-white dark:bg-[#1a1b23] border border-[#cbd5e1] dark:border-[#272935] hover:border-[#00b8ff] transition shadow-sm cursor-pointer">
              <div class="flex items-center justify-between gap-3">
                <div class="flex items-center gap-3.5 sm:gap-4 min-w-0">
                  <div class="w-12 h-12 sm:w-14 sm:h-14 rounded-2xl bg-[#14232c] border border-[#1b3a4a] flex items-center justify-center shrink-0 p-1 relative">
                    <svg viewBox="0 0 64 64" class="w-full h-full">
                      <path d="M47 17 L53 11 M53 11 L48 11 M53 11 L53 16" stroke="#38bdf8" stroke-width="2.5" stroke-linecap="round"/>
                      <circle cx="32" cy="40" r="17" fill="#475569"/>
                      <path d="M17 33 Q32 19 47 33 Z" fill="#0284c7"/>
                      <text x="32" y="29" font-size="9" font-weight="900" fill="#ffffff" text-anchor="middle" font-family="sans-serif">K</text>
                      <circle cx="26" cy="40" r="2.5" fill="#ffffff"/>
                      <circle cx="38" cy="40" r="2.5" fill="#ffffff"/>
                    </svg>
                  </div>
                  <div class="space-y-0.5 min-w-0">
                    <div class="flex items-center gap-2">
                      <span class="font-black text-base sm:text-lg text-[#0f172a] dark:text-white truncate">국장개미</span>
                      <span class="text-[11px] font-bold px-2 py-0.5 rounded-full bg-[#00b8ff]/10 text-[#00b8ff] border border-[#00b8ff]/30 shrink-0">스윙</span>
                    </div>
                    <p class="text-xs sm:text-sm text-[#64748b] dark:text-[#a1a1aa] font-medium truncate">흐름을 타는 똑똑한 개미의 선택!</p>
                  </div>
                </div>
                <div class="text-right shrink-0 border-l border-[#e2e8f0] dark:border-[#2b2e3c] pl-3 sm:pl-6">
                  <div class="text-[11px] text-[#94a3b8] dark:text-[#71717a] font-bold">10년 누적 성과</div>
                  <div class="text-base sm:text-lg font-black text-[#00b8ff]">+2,335%</div>
                </div>
              </div>
            </button>
            <div id="dash-slot-국장" class="hidden animate-fade"></div>
          </div>

          <div class="space-y-2">
            <button type="button" onclick="toggleStrategyDashboard('트레이더', this)" id="card-btn-트레이더" class="w-full text-left p-4 sm:p-5 rounded-2xl bg-white dark:bg-[#1a1b23] border border-[#cbd5e1] dark:border-[#272935] hover:border-amber-400 transition shadow-sm cursor-pointer">
              <div class="flex items-center justify-between gap-3">
                <div class="flex items-center gap-3.5 sm:gap-4 min-w-0">
                  <div class="w-12 h-12 sm:w-14 sm:h-14 rounded-2xl bg-[#241f2a] border border-[#44354c] flex items-center justify-center shrink-0 p-1">
                    <svg viewBox="0 0 64 64" class="w-full h-full">
                      <path d="M15 37 A17 17 0 0 1 49 37" stroke="#a1a1aa" stroke-width="3" fill="none"/>
                      <rect x="13" y="32" width="6" height="13" rx="3" fill="#ef4444"/>
                      <rect x="45" y="32" width="6" height="13" rx="3" fill="#ef4444"/>
                      <circle cx="32" cy="39" r="16" fill="#3f3f46"/>
                      <path d="M20 33 L28 36" stroke="#f43f5e" stroke-width="2" stroke-linecap="round"/>
                      <path d="M44 33 L36 36" stroke="#f43f5e" stroke-width="2" stroke-linecap="round"/>
                      <ellipse cx="25" cy="40" rx="3.5" ry="4" fill="#ffffff"/>
                      <circle cx="26" cy="40" r="2" fill="#09090b"/>
                      <ellipse cx="39" cy="40" rx="3.5" ry="4" fill="#ffffff"/>
                      <circle cx="38" cy="40" r="2" fill="#09090b"/>
                    </svg>
                  </div>
                  <div class="space-y-0.5 min-w-0">
                    <div class="flex items-center gap-2">
                      <span class="font-black text-base sm:text-lg text-[#0f172a] dark:text-white truncate">트레이더</span>
                      <span class="text-[11px] font-bold px-2 py-0.5 rounded-full bg-amber-400/10 text-amber-400 border border-amber-400/30 shrink-0">단기</span>
                    </div>
                    <p class="text-xs sm:text-sm text-[#64748b] dark:text-[#a1a1aa] font-medium truncate">기회를 놓치지 않는 빠른 판단!</p>
                  </div>
                </div>
                <div class="text-right shrink-0 border-l border-[#e2e8f0] dark:border-[#2b2e3c] pl-3 sm:pl-6">
                  <div class="text-[11px] text-[#94a3b8] dark:text-[#71717a] font-bold">10년 누적 성과</div>
                  <div class="text-base sm:text-lg font-black text-amber-400">+3,140%</div>
                </div>
              </div>
            </button>
            <div id="dash-slot-트레이더" class="hidden animate-fade"></div>
          </div>
        </div>
      `;
      container.appendChild(bottomDiv);
    }

    const strategyData = {
      '서학': {
        name: '서학개미 전략', icon: '🇺🇸', quote: '"데이터는 거짓말을 하지 않는다."',
        dateRange: '2016.08.28 ~ 2026.08.27', initial: '1억원', finalAsset: '24.5억',
        totalReturn: '+2,335%', cagr: '38.6%', mdd: '-24.8%', trades: '286회', winRate: '62.9%',
        accentColor: '#ff2d78', benchLabel: 'QQQ',
        chartData: [1.0, 1.8, 2.7, 4.5, 7.8, 11.2, 8.9, 14.5, 18.2, 21.4, 24.5],
        benchData: [1.0, 1.2, 1.5, 1.8, 2.4, 3.1, 2.3, 3.2, 3.8, 4.0, 4.2],
        labels: ['16', '17', '18', '19', '20', '21', '22', '23', '24', '25', '26']
      },
      '국장': {
        name: '국장개미 전략', icon: '🇰🇷', quote: '"박스권 국장에서도 외인 턴어라운드는 통한다."',
        dateRange: '2016.08.28 ~ 2026.08.27', initial: '1억원', finalAsset: '24.5억',
        totalReturn: '+2,335%', cagr: '38.6%', mdd: '-18.4%', trades: '412회', winRate: '68.2%',
        accentColor: '#00b8ff', benchLabel: 'KOSPI',
        chartData: [1.0, 2.1, 3.4, 5.8, 9.2, 13.5, 11.0, 16.8, 19.5, 22.1, 24.5],
        benchData: [1.0, 1.05, 1.2, 1.15, 1.4, 1.6, 1.3, 1.45, 1.5, 1.65, 1.8],
        labels: ['16', '17', '18', '19', '20', '21', '22', '23', '24', '25', '26']
      },
      '트레이더': {
        name: '트레이더 전략', icon: '⚡', quote: '"가장 강한 돈이 쏠린 자리에만 베팅한다."',
        dateRange: '2016.08.28 ~ 2026.08.27', initial: '1억원', finalAsset: '32.4억',
        totalReturn: '+3,140%', cagr: '42.1%', mdd: '-15.2%', trades: '1,240회', winRate: '74.5%',
        accentColor: '#eab308', benchLabel: '무위험',
        chartData: [1.0, 2.8, 4.9, 8.2, 13.5, 18.2, 16.8, 23.0, 26.5, 29.8, 32.4],
        benchData: [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0],
        labels: ['16', '17', '18', '19', '20', '21', '22', '23', '24', '25', '26']
      }
    };

    function toggleStrategyDashboard(type, btnElement) {
      const allTypes = ['서학', '국장', '트레이더'];
      const targetSlot = document.getElementById(`dash-slot-${type}`);
      const isAlreadyOpen = targetSlot && !targetSlot.classList.contains('hidden');

      if (currentChartInstance) { 
        currentChartInstance.destroy(); 
        currentChartInstance = null; 
      }

      allTypes.forEach(t => {
        const slot = document.getElementById(`dash-slot-${t}`);
        if (slot) { slot.innerHTML = ''; slot.classList.add('hidden'); }
        const btn = document.getElementById(`card-btn-${t}`);
        if (btn) {
          btn.classList.remove('border-2', 'border-[#ff2d78]', 'border-[#00b8ff]', 'border-amber-400');
          btn.classList.add('border-[#cbd5e1]', 'dark:border-[#272935]');
        }
      });

      if (isAlreadyOpen) return;

      const data = strategyData[type];
      const activeBorderClass = type === '서학' ? 'border-[#ff2d78]' : (type === '국장' ? 'border-[#00b8ff]' : 'border-amber-400');
      if (btnElement) {
        btnElement.classList.remove('border-[#cbd5e1]', 'dark:border-[#272935]');
        btnElement.classList.add('border-2', activeBorderClass);
      }

      targetSlot.innerHTML = `
        <div class="bg-white dark:bg-[#121318] border border-[#cbd5e1] dark:border-[#22242f] rounded-3xl p-5 sm:p-7 shadow-2xl space-y-6 my-3 animate-fade text-[#0f172a] dark:text-white">
          <div class="flex flex-col sm:flex-row sm:items-start justify-between gap-4  border-[#e2e8f0] dark:border-[#1f212c] pb-5">
            <div class="flex items-center gap-3">
              <div class="w-12 h-12 rounded-2xl bg-[#ff2d78]/10 border border-[#ff2d78]/20 flex items-center justify-center text-2xl shrink-0">
                ${data.icon}
              </div>
              <div>
                <h2 class="text-xl sm:text-2xl font-black text-[#0f172a] dark:text-white tracking-tight">실제 백테스트 검증</h2>
                <p class="text-xs sm:text-sm text-[#64748b] dark:text-[#8e92a4] mt-0.5 font-medium">과거 데이터로 증명된, 개미GTP의 투자 전략입니다.</p>
              </div>
            </div>
            <div class="sm:text-right font-serif italic text-xs sm:text-sm text-[#64748b] dark:text-[#7e8294] shrink-0">
              ${data.quote}
              <div class="text-[11px] text-[#94a3b8] dark:text-[#525565] not-italic font-sans mt-0.5">- gaemiGTP -</div>
            </div>
          </div>

          <div class="flex flex-wrap items-center gap-2 sm:gap-3 text-xs sm:text-sm text-[#64748b] dark:text-[#8e92a4] font-medium">
            <span class="font-black text-[#0f172a] dark:text-white text-base">${data.name}</span>
            <span class="text-[#cbd5e1] dark:text-[#363949]">|</span>
            <span>${data.dateRange}</span>
            <span class="text-[#cbd5e1] dark:text-[#363949]">|</span>
            <span>초기자금 ${data.initial}</span>
            <span class="text-[#cbd5e1] dark:text-[#363949]">|</span>
            <span class="text-emerald-600 dark:text-emerald-400 font-bold">수수료 포함</span>
          </div>

          <div class="grid grid-cols-2 divide-x divide-[#e2e8f0] dark:divide-[#262837] bg-[#f8fafc] dark:bg-[#161720] border border-[#e2e8f0] dark:border-[#262837] rounded-3xl p-5 sm:p-6 text-center">
            <div class="flex flex-col items-center justify-center space-y-1 pr-2 sm:pr-4">
              <div class="text-xs text-[#64748b] dark:text-[#717588] font-bold">1억 → 최종 자산</div>
              <div class="text-2xl sm:text-4xl font-black text-[#0f172a] dark:text-white tracking-tight">${data.finalAsset}</div>
            </div>
            <div class="flex flex-col items-center justify-center space-y-1 pl-2 sm:pl-4">
              <div class="text-xs text-[#64748b] dark:text-[#8e92a4] font-bold">10년 누적수익률</div>
              <div class="text-2xl sm:text-4xl font-black tracking-tight" style="color: ${data.accentColor};">${data.totalReturn}</div>
            </div>
          </div>

          <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div class="bg-[#f8fafc] dark:bg-[#171821] border border-[#e2e8f0] dark:border-[#262837] rounded-2xl p-3.5 text-center space-y-1">
              <div class="text-xs text-[#64748b] dark:text-[#7e8294] font-bold">CAGR</div>
              <div class="text-xl sm:text-2xl font-black" style="color: ${data.accentColor};">${data.cagr}</div>
            </div>
            <div class="bg-[#f8fafc] dark:bg-[#171821] border border-[#e2e8f0] dark:border-[#262837] rounded-2xl p-3.5 text-center space-y-1">
              <div class="text-xs text-[#64748b] dark:text-[#7e8294] font-bold">MDD</div>
              <div class="text-xl sm:text-2xl font-black text-[#00b8ff]">${data.mdd}</div>
            </div>
            <div class="bg-[#f8fafc] dark:bg-[#171821] border border-[#e2e8f0] dark:border-[#262837] rounded-2xl p-3.5 text-center space-y-1">
              <div class="text-xs text-[#64748b] dark:text-[#7e8294] font-bold">총 거래</div>
              <div class="text-xl sm:text-2xl font-black text-[#0f172a] dark:text-white">${data.trades}</div>
            </div>
            <div class="bg-[#f8fafc] dark:bg-[#171821] border border-[#e2e8f0] dark:border-[#262837] rounded-2xl p-3.5 text-center space-y-1">
              <div class="text-xs text-[#64748b] dark:text-[#7e8294] font-bold">승률</div>
              <div class="text-xl sm:text-2xl font-black text-[#0f172a] dark:text-white">${data.winRate}</div>
            </div>
          </div>

          <div class="bg-[#f8fafc] dark:bg-[#161720] border border-[#e2e8f0] dark:border-[#262837] rounded-3xl p-4 sm:p-6 space-y-3">
            <div class="flex items-center justify-between text-xs sm:text-sm">
              <div class="flex items-center gap-2 font-black text-[#0f172a] dark:text-white">
                <span>10년 자산곡선 (단위: 억)</span>
              </div>
              <div class="flex items-center gap-4 text-xs font-bold">
                <span class="flex items-center gap-1.5" style="color: ${data.accentColor};">
                  <span class="w-2.5 h-2.5 rounded-full inline-block" style="background-color: ${data.accentColor};"></span> 전략 수익률
                </span>
                <span class="flex items-center gap-1.5 text-[#64748b] dark:text-[#7e8294]">
                  <span class="w-2.5 h-2.5 rounded-full bg-[#94a3b8] dark:bg-[#7e8294] inline-block"></span> ${data.benchLabel}
                </span>
              </div>
            </div>
            <div class="relative w-full h-52 sm:h-60">
              <canvas id="canvas-acc-${type}"></canvas>
            </div>
          </div>

          <a href="https://www.quantconnect.com" target="_blank" rel="noopener noreferrer" class="block w-full py-3.5 px-6 rounded-2xl bg-gradient-to-r from-[#00a6f4] via-[#00c5ff] to-[#008be3] hover:brightness-110 text-white font-black text-center text-sm sm:text-base shadow-lg shadow-sky-500/20 transition cursor-pointer">
            QuantConnect 원본 결과 보기 ↗
          </a>
        </div>
      `;

      targetSlot.classList.remove('hidden');

      const isDark = document.documentElement.classList.contains('dark');
      const ctx = document.getElementById(`canvas-acc-${type}`).getContext('2d');
      const gradient = ctx.createLinearGradient(0, 0, 0, 220);
      gradient.addColorStop(0, data.accentColor + '44');
      gradient.addColorStop(1, 'rgba(0,0,0,0)');

      currentChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
          labels: data.labels,
          datasets: [
            {
              label: '전략 수익률',
              data: data.chartData,
              borderColor: data.accentColor,
              backgroundColor: gradient,
              borderWidth: 2.5,
              fill: true,
              tension: 0.35,
              pointRadius: 0
            },
            {
              label: data.benchLabel,
              data: data.benchData,
              borderColor: isDark ? '#4e5264' : '#94a3b8',
              borderWidth: 1.5,
              borderDash: [4, 4],
              fill: false,
              tension: 0.2,
              pointRadius: 0
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: {
              grid: { display: false },
              ticks: { color: isDark ? '#686c80' : '#94a3b8', font: { size: 10 } }
            },
            y: {
              position: 'right',
              grid: { color: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)' },
              ticks: {
                color: isDark ? '#686c80' : '#94a3b8',
                font: { size: 10 },
                callback: v => v + '억'
              }
            }
          }
        }
      });
    }

    let voted = false;
    function castVote(type) {
      if (voted) return alert('이미 투표하셨습니다!');
      voted = true;
      const bar = document.getElementById('voteProgressBar');
      const upLbl = document.getElementById('voteUpLabel');
      const downLbl = document.getElementById('voteDownLabel');
      if (type === 'up') {
        bar.style.width = '74%';
        upLbl.innerText = '상승 74%';
        downLbl.innerText = '하락 26%';
      } else {
        bar.style.width = '61%';
        upLbl.innerText = '상승 61%';
        downLbl.innerText = '하락 39%';
      }
    }

window.addEventListener('resize', () => {
  if (!document.body.classList.contains('right-panel-maximized')) {
    const savedWidth = parseInt(localStorage.getItem(PANEL_WIDTH_KEY) || '360', 10);
    setPanelWidth(Number.isFinite(savedWidth) ? savedWidth : 360);
  }
  applySidebarState();
});

document.addEventListener("DOMContentLoaded", () => {
  try {
    initializeSidebars();
    initializeWorkspaceInteractions();
  } catch (e) {
    console.warn('[gaemiGTP] workspace initialization warning:', e);
  }
  if (window.lucide) lucide.createIcons();
});
    function setRightInfoTab(tab) {
      const titles = {
        popular: ['인기 TOP 20', '현재가'],
        value: ['거래대금 TOP 20', '거래대금'],
        industry: ['산업 TOP 20', '등락률'],
        theme: ['테마 TOP 20', '등락률']
      };
      document.querySelectorAll('.right-info-tab').forEach(btn => {
        const active = btn.dataset.infoTab === tab;
        btn.classList.toggle('bg-[#eef2f7]', active);
        btn.classList.toggle('dark:bg-[#272a31]', active);
        btn.classList.toggle('text-[#0f172a]', active);
        btn.classList.toggle('dark:text-white', active);
        btn.classList.toggle('text-[#64748b]', !active);
        btn.classList.toggle('dark:text-[#a1a1aa]', !active);
      });
      const title = document.getElementById('rightListTitle');
      const metric = document.getElementById('rightListMetric');
      if (title) title.textContent = titles[tab][0];
      if (metric) metric.textContent = titles[tab][1];
      const criteria = document.getElementById('valueCriteria');
      if (criteria) criteria.classList.toggle('hidden', tab !== 'value');
    }

    function setValueCriteria(button, label) {
      document.querySelectorAll('.value-criterion').forEach(btn => {
        const active = btn === button;
        btn.classList.toggle('bg-[#eef2f7]', active);
        btn.classList.toggle('dark:bg-[#272a31]', active);
        btn.classList.toggle('text-[#0f172a]', active);
        btn.classList.toggle('dark:text-white', active);
        btn.classList.toggle('text-[#64748b]', !active);
        btn.classList.toggle('dark:text-[#a1a1aa]', !active);
      });
      const metric = document.getElementById('rightListMetric');
      if (metric) metric.textContent = label;
    }


// DOM is already parsed because this file is loaded at the end of <body>.
try {
  if (typeof initExternalLinkModal === 'function') initExternalLinkModal();
  if (window.lucide) lucide.createIcons();
} catch (e) {
  console.warn('[gaemiGTP] UI initialization warning:', e);
}
