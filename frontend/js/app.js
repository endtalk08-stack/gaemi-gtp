// Frontend is served by GitHub Pages; analysis API runs on Render.
const BACKEND_URL = 'https://gaemi-gtp.onrender.com';
    let activeAnalysisController = null;
    let activeStock = '삼성전자';
    let activeAnalysisRequestId = 0;
    let currentAppMode = 'gaemi';
    let workspaceUIReady = false;
    let restoringWorkspaceState = false;
    const WORKSPACE_STATE_KEY = 'gaemiGTP_workspace_state_v1';

    function getWorkspace() {
      return document.getElementById('gaemiWorkspace');
    }

    function setPanelWidth() {
      const shell = window.GaemiGTPRightPanelShell;
      if (shell?.setPanelWidth) return shell.setPanelWidth();
      const workspace = getWorkspace();
      if (!workspace) return;
      const navRail = document.getElementById('leftNavRail');
      const navWidth = navRail ? navRail.getBoundingClientRect().width : 0;
      const rounded = window.innerWidth < 1024 ? 360 : Math.round((window.innerWidth - navWidth) * (3 / 12));
      workspace.style.setProperty('--right-panel-width', `${rounded}px`);
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
          leftHomeOpen: document.body.classList.contains('left-home-open'),
          leftMarketOpen: document.body.classList.contains('left-market-open'),
          leftContextOpen: document.body.classList.contains('left-context-open'),
          leftPluginOpen: document.body.classList.contains('left-plugin-open'),
          rightPanelOpen: panelOpen,
          rightPanelMaximized: panelOpen && panelMaximized,
          appMode: currentAppMode || 'gaemi'
        };
        localStorage.setItem(WORKSPACE_STATE_KEY, JSON.stringify(state));
      } catch (e) {
        console.warn('[gaemiGTP] workspace state save warning:', e);
      }
    }

    function applySidebarState() {
      const market = document.getElementById('leftMarketSidebar');
      const home = document.getElementById('leftSidebarHome');
      const panel = document.getElementById('rightPanel');
      const resizer = document.getElementById('rightPanelResizer');
      const backdrop = document.getElementById('sidebarBackdrop');
      const marketOpen = document.body.classList.contains('left-market-open');
      const homeOpen = document.body.classList.contains('left-home-open');
      const contextOpen = document.body.classList.contains('left-context-open');
      const pluginOpen = document.body.classList.contains('left-plugin-open');
      const panelOpen = document.body.classList.contains('right-panel-open');
      const mobile = window.innerWidth < 1024;
      const heroView = document.getElementById('mainHeroView');
      const onHero = !!heroView && !heroView.classList.contains('hidden');
      document.body.classList.toggle('left-home-closed', !homeOpen);
      document.body.classList.toggle('left-market-closed', !marketOpen);
      document.body.classList.toggle('left-context-closed', !contextOpen);
      document.body.classList.toggle('left-plugin-closed', !pluginOpen);
      document.body.classList.toggle('right-panel-closed', !panelOpen);

      const context = document.getElementById('leftContextSidebar');
      const plugin = document.getElementById('leftPluginSidebar');
      if (home) home.setAttribute('aria-hidden', homeOpen ? 'false' : 'true');
      if (market) market.setAttribute('aria-hidden', marketOpen ? 'false' : 'true');
      if (context) context.setAttribute('aria-hidden', contextOpen ? 'false' : 'true');
      if (plugin) plugin.setAttribute('aria-hidden', pluginOpen ? 'false' : 'true');
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
      if (backdrop) backdrop.classList.toggle('hidden', !(mobile && (homeOpen || marketOpen || contextOpen || pluginOpen)));
      if (homeOpen) window.GaemiGTPSidebarHome?.render?.();
      if (window.lucide) lucide.createIcons();
      saveWorkspaceState();
    }

    // Left context sidebar module 호출용 public bridge
    window.applySidebarState = applySidebarState;

    function resetToHome() {
      document.getElementById('mainHeroView').classList.remove('hidden');
      document.body.classList.remove('analysis-mode');
      document.body.classList.remove('left-home-open','left-market-open','left-context-open','left-plugin-open','right-panel-open','right-panel-maximized');
      applySidebarState();
    }

    function selectStock(stockName, { enterAnalysis = false } = {}) {
      const normalizedStockName = String(stockName || '').trim();
      if (!normalizedStockName) return;

      if (enterAnalysis) {
        document.getElementById('mainHeroView').classList.add('hidden');
        document.body.classList.add('analysis-mode');

        // 홈 → 종목분석으로 이동할 때 현재 Workspace 상태를 그대로 보존한다.
        // 사용자가 열어둔 왼쪽 시장정보/오른쪽 패널을 임의로 닫지 않는다.
        applySidebarState();
      }

      requestStock(normalizedStockName);
    }

    function switchToAnalysisMode(stockName) {
      selectStock(stockName || '삼성전자', { enterAnalysis: true });
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
        selectStock(val);
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
      if (!isOpen) {
        document.body.classList.remove('left-home-open','left-context-open','left-plugin-open');
        if (window.innerWidth < 1024) {
          document.body.classList.remove('right-panel-open', 'right-panel-maximized');
        }
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
          document.body.classList.remove('left-home-open', 'left-market-open', 'left-context-open', 'left-plugin-open');
        }
        document.body.classList.add('right-panel-open');
      }
      applySidebarState();
    }

    function toggleRightPanelMaximize() {
      if (!document.body.classList.contains('right-panel-open')) {
        if (window.innerWidth < 1024) {
          document.body.classList.remove('left-home-open', 'left-market-open', 'left-context-open', 'left-plugin-open');
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
        requestAnimationFrame(() => setPanelWidth());
      }
      applySidebarState();
    }

    function closeAllSidebars() {
      document.body.classList.remove('left-home-open','left-market-open','left-context-open','left-plugin-open','right-panel-open','right-panel-maximized');
      applySidebarState();
    }

    function toggleLeftSidebarHome() {
      if (!workspaceUIReady) return;
      const isOpen = document.body.classList.contains('left-home-open');
      if (isOpen) {
        document.body.classList.remove('left-home-open');
      } else {
        document.body.classList.remove('left-market-open', 'left-context-open', 'left-plugin-open');
        if (window.innerWidth < 1024) document.body.classList.remove('right-panel-open', 'right-panel-maximized');
        document.body.classList.add('left-home-open');
      }
      applySidebarState();
    }

    function closeLeftSidebarHome() {
      document.body.classList.remove('left-home-open');
      applySidebarState();
    }

    function focusSidebarStockSearch() {
      closeLeftSidebarHome();
      focusStockInput();
    }

    function initializeSidebars() {
      // 새로 열 때는 항상 검색 홈에서 시작하고, 레이아웃 설정만 복원한다.
      const saved = readWorkspaceState();
      restoringWorkspaceState = true;

      document.body.classList.remove('left-home-open','left-market-open','left-context-open','left-plugin-open','right-panel-open','right-panel-maximized','analysis-mode');

      const heroView = document.getElementById('mainHeroView');
      if (heroView) heroView.classList.remove('hidden');

      if (saved?.leftHomeOpen) document.body.classList.add('left-home-open');
      if (saved?.leftMarketOpen) document.body.classList.add('left-market-open');
      if (saved?.leftContextOpen) document.body.classList.add('left-context-open');
      if (saved?.leftPluginOpen) document.body.classList.add('left-plugin-open');
      if (saved?.rightPanelOpen) document.body.classList.add('right-panel-open');
      if (saved?.leftMarketOpen || saved?.leftContextOpen || saved?.leftPluginOpen) document.body.classList.remove('left-home-open');
      if (saved?.leftContextOpen || saved?.leftPluginOpen) document.body.classList.remove('left-market-open');
      if (saved?.leftContextOpen) document.body.classList.remove('left-plugin-open');
      if (saved?.leftPluginOpen) document.body.classList.remove('left-context-open');
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
          toggleLeftSidebarHome();
        });
        el.dataset.sidebarListenerBound = 'true';
      });

      workspaceUIReady = true;
      window.workspaceUIReady = true;
      // Workspace가 렌더링된 다음 저장된 상태를 적용한다.
      // 레이아웃/쉘 모듈의 초기화 타이밍 때문에 첫 프레임에서 상태가 덮어써지는 것을 막기 위해
      // 두 프레임 뒤에 한 번 더 복원한다. 사용자가 마지막으로 만들어 둔 상태가 새로고침 후에도 그대로 유지된다.
      const restoreWorkspace = () => {
        if (saved?.rightPanelOpen) document.body.classList.add('right-panel-open');
        else document.body.classList.remove('right-panel-open');
        if (saved?.rightPanelMaximized && saved?.rightPanelOpen) {
          document.body.classList.add('right-panel-maximized');
        } else {
          document.body.classList.remove('right-panel-maximized');
        }
        if (saved?.leftHomeOpen) document.body.classList.add('left-home-open');
        else document.body.classList.remove('left-home-open');
        if (saved?.leftMarketOpen) document.body.classList.add('left-market-open');
        else document.body.classList.remove('left-market-open');
        if (saved?.leftContextOpen) document.body.classList.add('left-context-open');
        else document.body.classList.remove('left-context-open');
        if (saved?.leftPluginOpen) document.body.classList.add('left-plugin-open');
        else document.body.classList.remove('left-plugin-open');
        if (saved?.leftMarketOpen || saved?.leftContextOpen || saved?.leftPluginOpen) document.body.classList.remove('left-home-open');
        if (saved?.leftContextOpen || saved?.leftPluginOpen) document.body.classList.remove('left-market-open');
        if (saved?.leftContextOpen) document.body.classList.remove('left-plugin-open');
        if (saved?.leftPluginOpen) document.body.classList.remove('left-context-open');

        if (!document.body.classList.contains('right-panel-maximized')) {
          setPanelWidth();
        }
        applySidebarState();
      };

      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          restoreWorkspace();
          restoringWorkspaceState = false;
          saveWorkspaceState();

          // 마지막 종목 분석은 복원하지 않는다. 새 접속은 항상 검색 홈에서 시작한다.
        });
      });
    }

    function initializeWorkspaceInteractions() {
      const shell = window.GaemiGTPRightPanelShell;
      if (shell?.initializeWorkspaceInteractions) {
        shell.initializeWorkspaceInteractions();
        return;
      }
    }

    function updateThemeButtons() {
      if (window.GaemiGTPTheme && typeof window.GaemiGTPTheme.applyTheme === 'function') {
        window.GaemiGTPTheme.applyTheme(window.GaemiGTPTheme.get(), false);
        return;
      }
      const isDark = document.documentElement.classList.contains('dark');
      document.querySelectorAll('[data-theme-icon]').forEach(icon => {
        icon.setAttribute('data-lucide', isDark ? 'sun' : 'moon');
      });
      if (window.lucide) lucide.createIcons();
    }

    function toggleTheme() {
      if (window.GaemiGTPTheme && typeof window.GaemiGTPTheme.toggle === 'function') {
        window.GaemiGTPTheme.toggle();
        return;
      }
      document.documentElement.classList.toggle('dark');
      updateThemeButtons();
    }

      async function fetchAnalysisFromBackend(stockName, signal) {
        return window.GaemiGTPAnalysisAPI.fetchAnalysisFromBackend(stockName, signal);
      }

      function renderAnalysisStatus(chatArea, stockName, ok) {
        return window.GaemiGTPAnalysisStatus.renderAnalysisStatus(chatArea, stockName, ok);
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
      window.GaemiGTPActiveStock = activeStock;
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

      // 채팅과 플러그인 위젯이 같은 분석 응답을 공유한다.
      // 위젯은 제목 문자열이 아니라 백엔드의 고정 section id를 사용한다.
      window.GaemiGTPAnalysisData?.set?.(stockName, result);

      const surprisePopup = document.getElementById('surpriseAntPopup');
      surprisePopup.classList.remove('hidden');
      await new Promise(res => setTimeout(res, 600));
      if (requestId !== activeAnalysisRequestId) return;
      surprisePopup.classList.add('hidden');

      chatArea.scrollTop = 0;
      startTypewriterFlow(stockName, sections, result, requestId);
    }


      function openExternalLinkModal(item) {
        return window.GaemiGTPExternalLinkModal.openExternalLinkModal(item);
      }

      function renderSourceLists(result, { includeHeader = true } = {}) {
        return window.GaemiGTPSourceLists.renderSourceLists(result, { includeHeader });
      }

    function startTypewriterFlow(stockName, sections, result, requestId) {
      if (requestId !== activeAnalysisRequestId) return;
      const chatArea = document.getElementById('chatArea');
      const wrapperId = 'stream-' + Date.now();

      const mainContainer = document.createElement('div');
      mainContainer.id = wrapperId;
      mainContainer.className = "space-y-7 py-2";
      chatArea.appendChild(mainContainer);

      // 첫 답변의 본문 크기·색상·반응형 규칙을 안내/연출 멘트의 공통 기준으로 쓴다.
      const responseMessageClass = 'text-base sm:text-lg text-[#334155] dark:text-[#e4e4e7] leading-relaxed';

      let secIdx = 0;

      function appendFirstReplyActions(anchor, replyText, actionGroup = 'first') {
        return window.GaemiGTPFirstReplyActions.appendFirstReplyActions(anchor, replyText, actionGroup, stockName);
      }

      function appendNextAnalysisChoices(anchor) {
        if (!anchor || anchor.parentElement?.querySelector('[data-next-analysis-choices]')) return;

        const whySection = Array.isArray(sections) ? sections.find((section) => section?.id === 'why-up') : null;
        const changeMatch = String(whySection?.content || '').match(/([+-]\d+(?:\.\d+)?)%/);
        const changePercent = changeMatch ? Number(changeMatch[1]) : 0;
        const whyState = changePercent >= 0.5
          ? { label: '왜 빨간불일까?', tag: '#왜_빨간불일까?', color: '#FF8DA1' }
          : changePercent <= -0.5
            ? { label: '왜 파란불일까?', tag: '#왜_파란불일까?', color: '#38BDF8' }
            : { label: '왜 보합일까?', tag: '#왜_보합일까?', color: '#94A3B8' };

        const makeUserPrompt = (text, dataName) => {
          const prompt = document.createElement('div');
          if (dataName) prompt.dataset[dataName] = 'true';
          prompt.className = 'flex justify-end animate-fade';
          const bubble = document.createElement('div');
          bubble.className = 'bg-[#f1f5f9] dark:bg-[#1e1f24] text-[#0f172a] dark:text-white text-base font-bold px-5 py-3 rounded-2xl border border-[#cbd5e1] dark:border-[#3f3f46]';
          bubble.textContent = text;
          prompt.appendChild(bubble);
          return prompt;
        };

        const getWhyEvidence = () => {
          const output = [];
          const seen = new Set();
          const add = (label, tone) => {
            if (!label || seen.has(label) || output.length >= 2) return;
            seen.add(label);
            output.push({ label: `#${label.replace(/^#/, '').replace(/\s+/g, '')}`, tone });
          };

          const articles = Array.isArray(result.news_items) ? result.news_items : [];
          articles.forEach((item) => {
            const serverSignals = Array.isArray(item.movement_signals) ? item.movement_signals : [];
            serverSignals.forEach((signal) => {
              if (signal && signal.label) add(signal.label, signal.tone || 'neutral');
            });
          });
          return { signals: output, articles };
        };

        const appendFollowupChoices = (after) => {
          const followups = document.createElement('section');
          followups.dataset.whyFollowupChoices = 'true';
          followups.className = 'mt-6 space-y-2 animate-fade';
          followups.innerHTML = `
            <p class="${responseMessageClass}">더 살펴볼래?</p>
            <div class="flex flex-wrap items-center gap-x-3 gap-y-1.5">
            </div>`;
          after.insertAdjacentElement('afterend', followups);
          return followups;
        };

        const choices = document.createElement('section');
        choices.dataset.nextAnalysisChoices = 'true';
        choices.className = 'mt-6 space-y-2 animate-fade text-right';
        choices.innerHTML = `
          <p class="${responseMessageClass}">뭐가 궁금해?</p>
          <div class="flex flex-wrap items-center justify-end gap-x-3 gap-y-1.5">
            <button type="button" class="text-sm font-semibold text-[#3b82f6] transition hover:text-[#2563eb] dark:text-[#7aa2e3] dark:hover:text-[#9ab8ee]" data-next-analysis="us-market">#미국장</button>
            <button type="button" class="text-sm font-semibold transition hover:opacity-80" style="color:${whyState.color}" data-next-analysis="why">${whyState.tag}</button>
          </div>`;

        const appendUsMarketPrompt = () => {
          if (mainContainer.querySelector('[data-us-market-prompt]')) return;
          const prompt = makeUserPrompt('미국장 어땠어?', 'usMarketPrompt');
          choices.insertAdjacentElement('afterend', prompt);
          prompt.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        };

        const appendMaterials = async (choiceAnchor = choices) => {
          return window.GaemiGTPMaterialsFlow.appendMaterials({
            mainContainer,
            requestId,
            getActiveAnalysisRequestId: () => activeAnalysisRequestId,
            result,
            choices: choiceAnchor,
            makeUserPrompt,
            responseMessageClass,
            stockName
          });
        };

        const typeText = async (element, text, { chunkSize = 3 } = {}) => {
          if (!element) return;
          element.textContent = '';
          element.classList.add('typing-cursor');
          let charIndex = 0;
          while (charIndex < text.length) {
            if (requestId !== activeAnalysisRequestId || !mainContainer.isConnected) return;
            const chunk = text.substr(charIndex, chunkSize);
            element.textContent += chunk;
            charIndex += chunk.length;
            const pause = /[.!?…]$/.test(chunk) ? 180 : (/\n$/.test(chunk) ? 120 : 40);
            await new Promise((resolve) => setTimeout(resolve, pause));
          }
          element.classList.remove('typing-cursor');
        };

        const appendWhy = async () => {
          return window.GaemiGTPWhyFlow.appendWhy({
            mainContainer,
            requestId,
            getActiveAnalysisRequestId: () => activeAnalysisRequestId,
            result,
            choices,
            whyState,
            makeUserPrompt,
            getWhyEvidence,
            appendFollowupChoices,
            typeText,
            responseMessageClass,
            stockName
          });
        };

        const handleNextAnalysisChoice = async (event) => {
          const button = event.currentTarget;
          if (button.dataset.nextAnalysis === 'us-market') {
            appendUsMarketPrompt();
            choices.remove();
            return;
          }
          if (button.dataset.nextAnalysis === 'why') {
            await appendWhy();
            return;
          }
          if (button.dataset.nextAnalysis === 'materials') await appendMaterials();
        };
        choices.querySelectorAll('[data-next-analysis]').forEach((button) => {
          button.addEventListener('click', handleNextAnalysisChoice);
        });

        anchor.insertAdjacentElement('afterend', choices);
      }

      function typeNextSection() {
        if (requestId !== activeAnalysisRequestId) return;
        if (!sections || secIdx >= sections.length) {
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
        const headingMarkup = `
          <div class="flex items-center gap-2.5">
            <div class="w-7 h-7 sm:w-8 sm:h-8 rounded-full bg-[#0f172a] dark:bg-white text-white dark:text-black flex items-center justify-center font-black text-xs sm:text-sm shadow-sm shrink-0">G</div>
            ${dynamicTitle ? `<h4 class="font-black text-lg sm:text-xl text-[#0f172a] dark:text-white">${dynamicTitle}</h4>` : ''}
          </div>`;
        const shouldTypeSection = true;
        const contentMarkup = `<p id="p-content-${secIdx}" class="${responseMessageClass} whitespace-pre-line typing-cursor"></p>`;
        // 첫 답변은 현재 가격 설명만 보여 준다. 고정 "오늘은 왜 올랐어?"
        // 제목과 시간표는 중앙 본문 흐름에서 제외한다.
        textBlock.innerHTML = sec.id === 'why-up'
          ? contentMarkup
          : `${headingMarkup}${contentMarkup}`;

        mainContainer.appendChild(textBlock);

        const pEl = document.getElementById(`p-content-${secIdx}`);
        let charIdx = 0;
        const chunkSize = 3;

        // 분석 본문은 모두 같은 타이핑 연출을 사용한다.
        function typeChunk() {
          if (requestId !== activeAnalysisRequestId) return;
          if (charIdx < text.length) {
            const chunk = text.substr(charIdx, chunkSize);
            pEl.textContent += chunk;
            charIdx += chunk.length;
            const pause = /[.!?…]$/.test(chunk) ? 180 : (/\n$/.test(chunk) ? 120 : 40);
            setTimeout(typeChunk, pause);
          } else {
            pEl.classList.remove('typing-cursor');
            let formatted = pEl.textContent;

            try {
              // 1. 실적 종목명(#오라클, #어도비 등) -> 핑크
              formatted = formatted.replace(/(#(?:오라클|어도비|엔비디아|테슬라|애플|구글|마이크로소프트|아마존|메타|일라이릴리))/g, '<span class="font-bold" style="color: #FF8DA1;">$1</span>');

              // 2. 경제 지표(#PPI, #CPI, #FOMC, #PCE, #NFP) -> 블루
              formatted = formatted.replace(/(#(?:PPI|CPI|FOMC|PCE|NFP))/g, '<span class="font-bold" style="color: #38BDF8;">$1</span>');

              // 5. 첫 섹션 태그 라인 오류 완전 해결
              if (formatted.includes('#') && !formatted.includes('캘린더')) {
                // HTML 변환 뒤의 문자열에는 class/style의 '-'도 들어가므로,
                // HTML 문자열이 아니라 실제 답변 텍스트를 기준으로 방향을 판단한다.
                const directionText = pEl.textContent || formatted;
                const isDown = /(?:^|\\n).*-(?:\\d+(?:\\.\\d+)?%)|보합|눈치싸움|파란불|숨고르기|투매/.test(directionText);
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

            // 첫 답변 안의 해시태그도 2단계와 같은 14px 기준으로 고정한다.
            formatted = formatted.replace(/<span([^>]*)>(#[^<]+)<\/span>/g, (match, attributes, tagText) => {
              const nextAttributes = /\bclass="/.test(attributes)
                ? attributes.replace(/class="([^"]*)"/, 'class="$1 first-answer-hashtag"')
                : `${attributes} class="analysis-hashtag"`;
              return `<span${nextAttributes}>${tagText}</span>`;
            });

            pEl.innerHTML = formatted;

            // 첫 번째 분석 문장 아래에 뉴스·공시를 독립된 클릭형 목록으로 표시한다.
            // 본문 안의 📰/📌 텍스트 파싱은 더 이상 사용하지 않는다.
            if (secIdx === 0) {
              const actions = appendFirstReplyActions(pEl, pEl.innerText);
              appendNextAnalysisChoices(actions);
              return;
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

window.addEventListener('pagehide', () => {
  // 페이지를 떠나거나 새로고침할 때 마지막 실제 UI 상태를 즉시 저장한다.
  // 다음 로드에서 오른쪽 패널의 열림/최대화/폭 상태가 바뀌지 않도록 한다.
  try { saveWorkspaceState(); } catch (e) { /* noop */ }
});

window.addEventListener('resize', () => {
  if (!document.body.classList.contains('right-panel-maximized')) {
    setPanelWidth();
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
