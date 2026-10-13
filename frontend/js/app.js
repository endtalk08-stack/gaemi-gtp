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

    // Persist only completed conversation content; no additional AI or market requests.
    const CHAT_HISTORY_KEY = 'gaemiGTP_chat_history_v1';
    let nextConversationKey = 0;
    function newConversationKey() {
      return 'conversation:' + Date.now().toString(36) + '-' + (++nextConversationKey).toString(36) + '-' + Math.random().toString(36).slice(2, 9);
    }
    function readChatHistory() {
      try {
        const value = JSON.parse(localStorage.getItem(CHAT_HISTORY_KEY) || '{}');
        return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
      } catch (_) { return {}; }
    }
    function saveChatHistory() {
      if (!activeChatSession?.recentId || activeChatSession.restoring) return;
      const history = readChatHistory();
      const id = activeChatSession.recentId;
      history[id] = {
        stock: activeChatSession.stock || null,
        messages: activeChatSession.messages.map(({ role, kind, text, sections }) => ({
          role, kind, text: String(text || ''),
          ...(Array.isArray(sections) ? { sections: sections.map(({ id, title, content }) => ({ id, title, content })) } : {})
        }))
      };
      const recentIds = window.GaemiGTPSidebarHome?.getRecentIds?.() || [];
      if (recentIds.length) {
        for (const key of Object.keys(history)) {
          if (key.startsWith('conversation:') && !recentIds.includes(key)) delete history[key];
        }
      }
      try { localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(history)); } catch (_) { /* storage unavailable */ }
    }
    function linkRecentConversation(type, value) {
      if (!activeChatSession) return;
      if (activeChatSession.recentId) return;
      const id = newConversationKey();
      activeChatSession.recentId = window.GaemiGTPSidebarHome?.recordRecent?.(type, value, id) || null;
      saveChatHistory();
    }
    function restoreRecentConversation(recentId) {
      const saved = readChatHistory()[recentId];
      if (!saved || !Array.isArray(saved.messages)) return false;
      activeAnalysisController?.abort();
      activeAnalysisController = null;
      ++activeAnalysisRequestId;
      const session = beginChatSession(saved.stock || null);
      if (!session) return false;
      session.recentId = recentId;
      if (saved.stock) {
        if (window.GaemiGTPAnalysisData?.get?.()?.stockName !== saved.stock) {
          window.GaemiGTPAnalysisData?.set?.(saved.stock, {});
        }
        activeStock = saved.stock;
        window.GaemiGTPActiveStock = saved.stock;
      }
      // Restore must not write partially rebuilt messages over the saved conversation.
      session.restoring = true;
      for (const message of saved.messages) {
        if (message.kind === 'analysis' && Array.isArray(message.sections)) {
          session.messages.push({ id: ++nextChatMessageId, role: 'assistant', kind: 'analysis', sections: message.sections });
          const area = document.getElementById('chatArea');
          for (const section of message.sections) {
            const row = document.createElement('div');
            row.className = 'gtp-chat-copy whitespace-pre-line';
            const title = document.createElement('strong');
            title.textContent = section.title || '';
            const body = document.createElement('p');
            body.textContent = section.content || '';
            row.append(title, body);
            area.appendChild(row);
          }
        } else if (['user', 'assistant'].includes(message.role)) {
          appendChatMessage(message.role, message.text || '', message.kind || 'answer', session.id);
        }
      }
      session.restoring = false;
      return true;
    }

    // One active conversation in the existing central chat; no separate chat UI.
    function beginChatSession(stock = null) {
      activeQuestionController?.abort();
      activeQuestionController = null;
      pendingQuestionSessionId = null;
      pendingAnalysis = null;
      const area = document.getElementById('chatArea');
      if (!area) return null;
      saveChatHistory();
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
      saveChatHistory();
      return row;
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
      appendChatMessage,
      beginChatSession,
      abortAnalysis: () => {
        activeAnalysisController?.abort();
        activeAnalysisController = null;
        ++activeAnalysisRequestId;
      }
    });
    const { submitQuestion, appendChatReply } = aiChat;

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

    const { requestStock } = window.GaemiGTPCenterAnalysisFlow.create({
      getActiveAnalysisRequestId: () => activeAnalysisRequestId,
      nextAnalysisRequestId: () => ++activeAnalysisRequestId,
      getAnalysisController: () => activeAnalysisController,
      setAnalysisController: (value) => { activeAnalysisController = value; },
      getActiveStock: () => activeStock,
      setActiveStock: (value) => { activeStock = value; },
      getPendingAnalysis: () => pendingAnalysis,
      setPendingAnalysis: (value) => { pendingAnalysis = value; },
      getSession: () => activeChatSession,
      beginChatSession,
      appendChatMessage,
      nextChatMessageId: () => ++nextChatMessageId
    });

window.addEventListener('pagehide', () => {
  saveChatHistory();
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

window.GaemiGTPApp = { requestStock, submitQuestion, appendChatReply, getChatState, linkRecentConversation, restoreRecentConversation, saveChatHistory };

document.addEventListener("DOMContentLoaded", () => {
  try {
    window.GaemiGTPWorkspaceInitializer?.initialize?.();
  } catch (e) {
    console.warn('[gaemiGTP] workspace initialization warning:', e);
  }
  if (window.lucide) lucide.createIcons();
});
