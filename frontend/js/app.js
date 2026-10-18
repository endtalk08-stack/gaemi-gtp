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
      setCurrentAppMode: (mode) => switchChatMode(mode),
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
    const MODE_RECENTS_KEY = 'gaemiGTP_mode_last_conversation_v1';
    const CHAT_MODES = ['gaemi', 'info', 'pro'];
    // Each mode owns its live session and its DOM without a second chat UI.
    const sessionsByMode = { gaemi: null, info: null, pro: null };
    const viewsByMode = { gaemi: null, info: null, pro: null };
    function readModeRecents() {
      try {
        const value = JSON.parse(localStorage.getItem(MODE_RECENTS_KEY) || '{}');
        return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
      } catch (_) { return {}; }
    }
    function rememberModeRecent(mode, recentId) {
      if (!CHAT_MODES.includes(mode)) return;
      const entries = readModeRecents();
      if (recentId) entries[mode] = recentId;
      else delete entries[mode];
      try { localStorage.setItem(MODE_RECENTS_KEY, JSON.stringify(entries)); } catch (_) { /* storage unavailable */ }
    }
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
      const snapshot = window.GaemiGTPAnalysisData?.get?.();
      // Keep the restored conversation's existing analysis data without another fetch.
      // Only attach data for the same stock; never carry a different stock's snapshot.
      const analysisData = snapshot?.stockName === activeChatSession.stock
        ? {
            sections: Object.values(snapshot.sections || {}),
            paired_news_items: (snapshot.newsItems || []).slice(0, 20),
            issue_briefs: (snapshot.issueBriefs || []).slice(0, 3),
            disclosures: (snapshot.disclosures || []).slice(0, 20),
            us_filings: (snapshot.usFilings || []).slice(0, 20)
          }
        : history[id]?.analysisData;
      history[id] = {
        mode: activeChatSession.mode || currentAppMode,
        stock: activeChatSession.stock || null,
        ...(activeChatSession.marketSelection ? { marketSelection: activeChatSession.marketSelection } : {}),
        ...(analysisData ? { analysisData } : {}),
        messages: activeChatSession.messages.map(({ role, kind, text, sections, issue_briefs }) => ({
          role, kind, text: String(text || ''),
          ...(Array.isArray(sections) ? { sections: sections.map(({ id, title, content }) => ({ id, title, content })) } : {}),
          ...(Array.isArray(issue_briefs) ? { issue_briefs: issue_briefs.slice(0, 3) } : {})
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
      activeChatSession.recentId = window.GaemiGTPSidebarHome?.recordRecent?.(type, value, id, activeChatSession.mode) || null;
      if (activeChatSession.recentId) rememberModeRecent(activeChatSession.mode, activeChatSession.recentId);
      saveChatHistory();
    }

    // Preserve only display fields. Neon remains the authoritative issue source.
    function cleanIssueBriefs(items) {
      return (Array.isArray(items) ? items : []).filter(item => item && String(item.headline || '').trim())
        .slice(0, 3).map(item => ({
          headline: String(item.headline || ''), summary: String(item.summary || ''),
          tags: Array.isArray(item.tags) ? item.tags.slice(0, 3) : [],
          time: String(item.time || ''), generated_at: String(item.generated_at || ''),
          stock_names: Array.isArray(item.stock_names) ? item.stock_names.slice(0, 3) : [],
          stock_reactions: Array.isArray(item.stock_reactions) ? item.stock_reactions.slice(0, 3) : []
        }));
    }

    function renderStoredIssueBriefs(target, items) {
      target.replaceChildren();
      target.className = 'mt-5 space-y-5';
      target.dataset.restoredAiIssues = 'true';
      const heading = document.createElement('p');
      heading.className = 'gtp-chat-copy font-semibold';
      heading.textContent = '오늘 눈에 띄는 흐름 👀';
      target.appendChild(heading);
      for (const item of cleanIssueBriefs(items)) {
        const article = document.createElement('article');
        article.className = 'space-y-2';
        const title = document.createElement('p');
        title.className = 'gtp-chat-copy font-semibold';
        if (item.time) {
          const time = document.createElement('span');
          time.className = 'mr-2 text-xs font-bold text-[#64748b] dark:text-[#a1a1aa]';
          time.textContent = item.time;
          title.appendChild(time);
        }
        const headline = document.createElement('span');
        headline.textContent = item.headline;
        title.appendChild(headline);
        article.appendChild(title);
        if (item.summary) {
          const summary = document.createElement('p');
          summary.className = 'gtp-chat-copy whitespace-pre-line';
          summary.textContent = item.summary;
          article.appendChild(summary);
        }
        if (item.tags.length) {
          const tags = document.createElement('p');
          tags.className = 'analysis-hashtag gtp-chat-copy font-semibold';
          tags.textContent = item.tags.map(tag => '#' + String(tag).replace(/^#/, '')).join('  ');
          article.appendChild(tags);
        }
        target.appendChild(article);
      }
    }

    function recordIssueBriefs(stockName, items) {
      if (!activeChatSession || activeChatSession.restoring || activeChatSession.stock !== stockName) return;
      const briefs = cleanIssueBriefs(items);
      if (!briefs.length) return;
      const previous = activeChatSession.messages.find(message => message.kind === 'ai_issues');
      if (previous) previous.issue_briefs = briefs;
      else activeChatSession.messages.push({
        id: ++nextChatMessageId, role: 'assistant', kind: 'ai_issues', issue_briefs: briefs
      });
      saveChatHistory();
    }

    // Restoring a saved conversation reads Neon without running analysis or AI.
    // A temporary read error never clears the previously visible issue text.
    async function refreshRestoredIssues(session, stock, cached, existingTarget) {
      let latest = [];
      try {
        const response = await fetch(BACKEND_URL + '/api/stock/ai-issues?stock=' + encodeURIComponent(stock));
        if (response.ok) {
          const data = await response.json();
          if (data.ok === true) latest = cleanIssueBriefs(data.items);
        }
      } catch (_) { /* retain cached issues */ }
      if (activeChatSession !== session || session.restoring) return;
      const area = document.getElementById('chatArea');
      if (!area) return;
      const oldIssues = cleanIssueBriefs(cached);
      if (latest.length && oldIssues.length) {
        latest = latest.map(issue => {
          const old = oldIssues.find(c => c.headline === issue.headline && c.generated_at === issue.generated_at);
          return old ? { ...issue, stock_reactions: old.stock_reactions } : issue;
        });
      }
      const chosen = latest.length ? latest : oldIssues;
      if (!chosen.length) return;
      let target = existingTarget;
      if (!target || !target.isConnected) {
        target = document.createElement('section');
        area.appendChild(target);
      }
      renderStoredIssueBriefs(target, chosen);
      const previous = session.messages.find(message => message.kind === 'ai_issues');
      if (previous) previous.issue_briefs = chosen;
      else session.messages.push({
        id: ++nextChatMessageId, role: 'assistant', kind: 'ai_issues', issue_briefs: chosen
      });
      saveChatHistory();
    }
    function restoreRecentConversation(recentId) {
      const saved = readChatHistory()[recentId];
      if (!saved || !Array.isArray(saved.messages)) return false;
      // Saved conversations reopen in the mode that originally created them;
      // older mode-less history remains available in the selected mode.
      if (CHAT_MODES.includes(saved.mode) && saved.mode !== currentAppMode) {
        window.GaemiGTPCenterChatSearch?.selectAppMode?.(saved.mode);
        if (currentAppMode !== saved.mode) switchChatMode(saved.mode);
      }
      activeAnalysisController?.abort();
      activeAnalysisController = null;
      ++activeAnalysisRequestId;
      const session = beginChatSession(saved.stock || null);
      if (!session) return false;
      session.recentId = recentId;
      rememberModeRecent(currentAppMode, recentId);
      if (saved.marketSelection?.name === saved.stock) session.marketSelection = saved.marketSelection;
      if (saved.stock) {
        // Restore the original analysis snapshot when present; old history remains compatible.
        window.GaemiGTPAnalysisData?.set?.(saved.stock, saved.analysisData || {});
        activeStock = saved.stock;
        window.GaemiGTPActiveStock = saved.stock;
      }
      // Restore must not write partially rebuilt messages over the saved conversation.
      session.restoring = true;
      let restoredIssueTarget = null;
      let restoredIssueCache = [];
      for (const message of saved.messages) {
        if (message.kind === 'analysis' && Array.isArray(message.sections)) {
          session.messages.push({ id: ++nextChatMessageId, role: 'assistant', kind: 'analysis', sections: message.sections });
          const area = document.getElementById('chatArea');
          // Live analysis currently displays only its first section.
          // Restore that same visible scope, not hidden legacy sections.
          const section = message.sections[0];
          if (section && area) {
            const row = document.createElement('div');
            row.className = 'gtp-chat-copy whitespace-pre-line';
            if (section.id !== 'why-up' && section.title) {
              const title = document.createElement('strong');
              title.textContent = section.title;
              row.appendChild(title);
            }
            const body = document.createElement('p');
            body.textContent = String(section.content || '')
              .replace(/이런 뉴스 재료와 기업 공시가 나오면서 시장이 반응하고 있는 거야/g, '')
              .replace(/(^|\n)\s*[📰📌][^\n]*(?=\n|$)/g, '$1')
              .replace(/\n{3,}/g, '\n\n')
              .trim();
            row.appendChild(body);
            area.appendChild(row);
          }
        } else if (message.kind === 'ai_issues' && Array.isArray(message.issue_briefs)) {
          restoredIssueCache = cleanIssueBriefs(message.issue_briefs);
          if (restoredIssueCache.length) {
            restoredIssueTarget = document.createElement('section');
            document.getElementById('chatArea')?.appendChild(restoredIssueTarget);
            renderStoredIssueBriefs(restoredIssueTarget, restoredIssueCache);
          }
          session.messages.push({
            id: ++nextChatMessageId, role: 'assistant', kind: 'ai_issues',
            issue_briefs: restoredIssueCache
          });
        } else if (['user', 'assistant'].includes(message.role)) {
          appendChatMessage(message.role, message.text || '', message.kind || 'answer', session.id);
        }
      }
      session.restoring = false;
      if (saved.stock) {
        const initial = restoredIssueCache.length ? restoredIssueCache
          : cleanIssueBriefs(saved.analysisData?.issue_briefs);
        if (initial.length && !restoredIssueTarget) {
          restoredIssueTarget = document.createElement('section');
          document.getElementById('chatArea')?.appendChild(restoredIssueTarget);
          renderStoredIssueBriefs(restoredIssueTarget, initial);
        }
        void refreshRestoredIssues(session, saved.stock, initial, restoredIssueTarget);
      }
      return true;
    }

    // Switch the single visible chat surface between three isolated transcripts.
    function switchChatMode(mode) {
      if (!CHAT_MODES.includes(mode)) return false;
      if (mode === currentAppMode && activeChatSession) return true;
      const area = document.getElementById('chatArea');
      if (!area) { currentAppMode = mode; return true; }
      if (activeChatSession && mode !== currentAppMode) {
        saveChatHistory();
        activeQuestionController?.abort();
        activeQuestionController = null;
        pendingQuestionSessionId = null;
        activeAnalysisController?.abort();
        activeAnalysisController = null;
        ++activeAnalysisRequestId;
        pendingAnalysis = null;
        // Do not leave a half-typed reply or spinner in the previous mode.
        for (const row of area.querySelectorAll('.gaemi-ai-reply-format')) {
          if (!row.querySelector('.typing-cursor')) continue;
          const original = activeChatSession.messages.find(
            message => String(message.id) === row.dataset.chatMessageId
          );
          if (original) row.textContent = original.text;
          row.classList.remove('gaemi-ai-reply-format');
        }
        for (const loading of area.querySelectorAll('.analysis-loading-sequence')) loading.remove();
        // Invalidate in-flight callbacks even if the user returns immediately.
        activeChatSession.id = ++nextChatSessionId;
        sessionsByMode[currentAppMode] = activeChatSession;
        const fragment = document.createDocumentFragment();
        while (area.firstChild) fragment.appendChild(area.firstChild);
        viewsByMode[currentAppMode] = fragment;
      }
      currentAppMode = mode;
      window.GaemiGTPSidebarHome?.renderRecent?.();
      if (sessionsByMode[mode]) {
        activeChatSession = sessionsByMode[mode];
        area.replaceChildren();
        if (viewsByMode[mode]) area.appendChild(viewsByMode[mode]);
        area.scrollTop = 0;
        return true;
      }
      activeChatSession = null;
      area.replaceChildren();
      const lastId = readModeRecents()[mode];
      const saved = lastId && readChatHistory()[lastId];
      if (saved && (!saved.mode || saved.mode === mode) &&
          restoreRecentConversation(lastId)) return true;
      if (lastId) rememberModeRecent(mode, null);
      area.scrollTop = 0;
      return true;
    }

    // Beginning a new conversation replaces only the current mode's session.
    function beginChatSession(stock = null, marketSelection = null) {
      activeQuestionController?.abort();
      activeQuestionController = null;
      pendingQuestionSessionId = null;
      pendingAnalysis = null;
      const area = document.getElementById('chatArea');
      if (!area) return null;
      saveChatHistory();
      activeChatSession = {
        id: ++nextChatSessionId, stock, mode: currentAppMode,
        marketSelection: marketSelection?.name === stock ? { ...marketSelection } : null,
        messages: []
      };
      sessionsByMode[currentAppMode] = activeChatSession;
      viewsByMode[currentAppMode] = null;
      rememberModeRecent(currentAppMode, null);
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
        id: activeChatSession.id, mode: activeChatSession.mode, stock: activeChatSession.stock,
        marketSelection: activeChatSession.marketSelection ? { ...activeChatSession.marketSelection } : null,
        messages: activeChatSession.messages.map((message) => ({
          ...message,
          ...(message.sections ? { sections: message.sections.map((section) => ({ ...section })) } : {})
        }))
      };
    }

    const { requestStock } = window.GaemiGTPCenterAnalysisFlow.create({
      backendUrl: BACKEND_URL,
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

window.GaemiGTPApp = { requestStock, submitQuestion, appendChatReply, getChatState, linkRecentConversation, restoreRecentConversation, recordIssueBriefs, saveChatHistory, switchChatMode };

document.addEventListener("DOMContentLoaded", () => {
  try {
    window.GaemiGTPWorkspaceInitializer?.initialize?.();
  } catch (e) {
    console.warn('[gaemiGTP] workspace initialization warning:', e);
  }
  if (window.lucide) lucide.createIcons();
});
