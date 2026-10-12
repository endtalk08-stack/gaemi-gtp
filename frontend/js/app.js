// Frontend is served by GitHub Pages; analysis API runs on Render.
const BACKEND_URL = window.location.hostname.endsWith('github.io')
  ? 'https://gaemi-gtp.onrender.com'
  : window.location.origin;
    let activeAnalysisController = null;
    let activeStock = '삼성전자';
    let activeAnalysisRequestId = 0;
    let currentAppMode = 'gaemi';

    window.GaemiGTPAppState = {
      getActiveStock: () => activeStock,
      getCurrentAppMode: () => currentAppMode,
      setCurrentAppMode: (mode) => { currentAppMode = mode; },
      setActiveStock: (stock) => { activeStock = stock; }
    };

    let activeChatSession = null;
    let nextChatSessionId = 0;
    let nextChatMessageId = 0;
    let activeQuestionController = null;
    let pendingQuestionSessionId = null;
    let pendingAnalysis = null;

    // One active conversation in the existing central chat; no separate chat UI.
    function beginChatSession(stock = null) {
      activeQuestionController?.abort();
      activeQuestionController = null;
      pendingQuestionSessionId = null;
      pendingAnalysis = null;
      const area = document.getElementById('chatArea');
      if (!area) return null;
      activeChatSession = { id: ++nextChatSessionId, stock, messages: [] };
      area.replaceChildren();
      area.scrollTop = 0;
      return activeChatSession;
    }

    function appendChatMessage(role, text, kind, sessionId) {
      if (!activeChatSession || activeChatSession.id !== sessionId) return null;
      const area = document.getElementById('chatArea');
      if (!area) return null;
      const message = { id: ++nextChatMessageId, role, kind, text: String(text) };
      const row = document.createElement('div');
      row.dataset.chatMessageId = String(message.id);
      if (role === 'user') {
        row.className = 'flex justify-end animate-fade';
        const bubble = document.createElement('div');
        bubble.className = 'bg-[#f1f5f9] dark:bg-[#1e1f24] text-[#0f172a] gtp-dark-text gtp-chat-user px-5 py-3 rounded-2xl border border-[#cbd5e1] dark:border-[#3f3f46]';
        bubble.textContent = message.text;
        row.appendChild(bubble);
      } else {
        row.className = 'gtp-chat-copy whitespace-pre-line animate-fade';
        row.textContent = message.text;
      }
      area.appendChild(row);
      activeChatSession.messages.push(message);
      return row;
    }

    function submitQuestion(question, { newConversation = false } = {}) {
      const text = String(question || '').trim();
      if (!text) return false;
      if (!newConversation && pendingQuestionSessionId === activeChatSession?.id) return false;
      if (newConversation || !activeChatSession) {
        activeAnalysisController?.abort();
        activeAnalysisController = null;
        ++activeAnalysisRequestId;
        if (!beginChatSession()) return false;
      }
      const sessionId = activeChatSession.id;
      const history = activeChatSession.messages
        .filter((message) => message.kind === 'question' || message.kind === 'answer')
        .slice(-6)
        .map(({ role, text }) => ({ role, text: text.slice(0, 240) }));
      const row = appendChatMessage('user', text, 'question', sessionId);
      if (!row) return false;
      window.GaemiGTPSidebarHome?.recordRecent?.('question', text);
      row.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      void requestChatAnswer(text, sessionId, history);
      return true;
    }

    // AI response renderer and provider flow live in the central-chat module.
    const aiChat = window.GaemiGTPCenterAIChat.create({
      backendUrl: BACKEND_URL,
      getSession: () => activeChatSession,
      getPendingAnalysis: () => pendingAnalysis,
      getActiveQuestionController: () => activeQuestionController,
      setActiveQuestionController: (value) => { activeQuestionController = value; },
      getPendingQuestionSessionId: () => pendingQuestionSessionId,
      setPendingQuestionSessionId: (value) => { pendingQuestionSessionId = value; },
      setStock: (value) => { activeStock = value; },
      appendChatMessage
    });
    const { requestChatAnswer, appendChatReply } = aiChat;

    function getChatState() {
      if (!activeChatSession) return null;
      return {
        id: activeChatSession.id, stock: activeChatSession.stock,
        messages: activeChatSession.messages.map((message) => ({
          ...message,
          ...(message.sections ? { sections: message.sections.map((section) => ({ ...section })) } : {})
        }))
      };
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
      window.GaemiGTPWorkspaceShellState?.save?.();

      const session = beginChatSession(stockName);
      if (!session) return;
      // 새 종목 조회 중 이전 종목의 뉴스·공시를 공유 데이터로 노출하지 않는다.
      // 새 수집 없이 기존 결과 저장소의 스냅샷만 초기화한다.
      window.GaemiGTPAnalysisData?.set?.(stockName, {});
      const chatArea = document.getElementById('chatArea');
      appendChatMessage('user', stockName, 'stock', session.id);

      const loadingDiv = document.createElement('div');
      loadingDiv.className = 'analysis-loading-sequence';
      loadingDiv.innerHTML = `<div class="gtp-chat-copy font-semibold animate-pulse" aria-live="polite">시세를 조회중입니다</div>`;
      chatArea.appendChild(loadingDiv);

      const controller = activeAnalysisController;
      const fetchPromise = window.GaemiGTPAnalysisAPI.fetchAnalysisFromBackend(stockName, controller.signal);
      pendingAnalysis = { stock: stockName, promise: fetchPromise };
      const loadingDelayPromise = new Promise(resolve => setTimeout(resolve, 4000));
      const [result] = await Promise.all([fetchPromise, loadingDelayPromise]);
      if (pendingAnalysis?.promise === fetchPromise) pendingAnalysis = null;
      if (requestId !== activeAnalysisRequestId || result.aborted) {
        loadingDiv.remove();
        return;
      }
      loadingDiv.remove();
      const sections = result.sections || [];

      if (activeAnalysisController === controller) activeAnalysisController = null;

      if (!result.ok || sections.length === 0) {
        const notFoundSection = sections.find((section) => section?.id === 'analysis-error');
        if (notFoundSection) {
          const state = document.createElement('div');
          state.className = 'animate-fade gtp-chat-copy';
          state.innerHTML = `
            <div class="font-semibold gtp-dark-text">${notFoundSection.title || '종목을 찾을 수 없습니다.'}</div>
            <div class="mt-3 text-[#64748b] dark:text-[#a1a1aa]">${notFoundSection.content || `${stockName} 종목을 확인하지 못했습니다. 종목명이나 티커를 다시 확인해주세요.`}</div>
          `;
          chatArea.appendChild(state);
        } else {
          window.GaemiGTPAnalysisStatus.renderAnalysisStatus(chatArea, stockName, result.ok);
        }
        chatArea.scrollTop = 0;
        return;
      }

      // 유효한 종목 분석이 완료된 경우에만 최근 검색에 추가한다.
      window.GaemiGTPSidebarHome?.recordRecent?.('stock', stockName);

      // 채팅과 플러그인 위젯이 같은 분석 응답을 공유한다.
      // 위젯은 제목 문자열이 아니라 백엔드의 고정 section id를 사용한다.
      window.GaemiGTPAnalysisData?.set?.(stockName, result);

      chatArea.scrollTop = 0;
      if (requestId !== activeAnalysisRequestId || activeChatSession?.id !== session.id) return;
      activeChatSession.messages.push({
        id: ++nextChatMessageId, role: 'assistant', kind: 'analysis',
        sections: sections.map(({ id, title, content }) => ({ id, title, content }))
      });
      startTypewriterFlow(stockName, sections, result, requestId);
    }


    const { startTypewriterFlow } = window.GaemiGTPCenterAnalysisFlow.create({
      getActiveAnalysisRequestId: () => activeAnalysisRequestId
    });

window.addEventListener('pagehide', () => {
  // 페이지를 떠나거나 새로고침할 때 마지막 실제 UI 상태를 즉시 저장한다.
  // 다음 로드에서 오른쪽 패널의 열림/최대화/폭 상태가 바뀌지 않도록 한다.
  try { window.GaemiGTPWorkspaceShellState?.save?.(); } catch (e) { /* noop */ }
});

window.addEventListener('resize', () => {
  if (!document.body.classList.contains('right-panel-maximized')) {
    window.GaemiGTPRightPanelShell?.setPanelWidth?.();
  }
  window.GaemiGTPWorkspaceShellState?.apply?.();
});

window.GaemiGTPApp = { requestStock, submitQuestion, appendChatReply, getChatState };

document.addEventListener("DOMContentLoaded", () => {
  try {
    window.GaemiGTPWorkspaceInitializer?.initialize?.();
  } catch (e) {
    console.warn('[gaemiGTP] workspace initialization warning:', e);
  }
  if (window.lucide) lucide.createIcons();
});
