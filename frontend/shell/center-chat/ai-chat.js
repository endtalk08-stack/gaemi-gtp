/* Central AI chat: API replies, typing and safe bold rendering. Existing session is owned by app.js. */
(function () {
  'use strict';
  function create(ctx) {
    function submitQuestion(question, { newConversation = false } = {}) {
      const text = String(question || '').trim();
      if (!text) return false;
      if (!newConversation && ctx.getPendingQuestionSessionId() === ctx.getSession()?.id) return false;
      if (newConversation || !ctx.getSession()) {
        ctx.abortAnalysis();
        if (!ctx.beginChatSession()) return false;
      }
      const sessionId = ctx.getSession().id;
      const history = ctx.getSession().messages
        .filter((message) => message.kind === 'question' || message.kind === 'answer')
        .slice(-6)
        .map(({ role, text }) => ({ role, text: text.slice(0, 240) }));
      const row = ctx.appendChatMessage('user', text, 'question', sessionId);
      if (!row) return false;
      window.GaemiGTPApp?.linkRecentConversation?.('question', text);
      row.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      void requestChatAnswer(text, sessionId, history);
      return true;
    }

    // Keep the original AI text for history/actions, but render safe structured DOM.
    // No HTML from a model response is ever evaluated.
    function getChatBoldSegments(text) {
      const segments = [];
      const boldPattern = /\*\*([^*\n]+)\*\*/g;
      let lastIndex = 0;
      for (const match of text.matchAll(boldPattern)) {
        if (match.index > lastIndex) segments.push({ text: text.slice(lastIndex, match.index), bold: false });
        segments.push({ text: match[1], bold: true });
        lastIndex = match.index + match[0].length;
      }
      if (lastIndex < text.length) segments.push({ text: text.slice(lastIndex), bold: false });
      return segments;
    }

    function ensureReplyStyles() {
      if (document.getElementById('gaemi-ai-reply-format-css')) return;
      const style = document.createElement('style');
      style.id = 'gaemi-ai-reply-format-css';
      style.textContent = [
        '.gaemi-ai-reply-format { white-space: normal; overflow-wrap: anywhere; }',
        '.gaemi-ai-reply-format .ai-reply-block { margin: 0 0 0.7em; line-height: 1.7; white-space: pre-wrap; }',
        '.gaemi-ai-reply-format .ai-reply-block:last-of-type { margin-bottom: 0; }',
        '.gaemi-ai-reply-format .ai-reply-heading { font-size: 1.05em; font-weight: 700; line-height: 1.5; margin-top: 0.95em; }',
        '.gaemi-ai-reply-format .ai-reply-heading:first-child { margin-top: 0; }',
        '.gaemi-ai-reply-format .ai-reply-list { padding-left: 1.4em; margin: 0 0 0.7em; white-space: normal; }',
        '.gaemi-ai-reply-format .ai-reply-list li { margin: 0.2em 0; line-height: 1.65; white-space: pre-wrap; }',
        '.gaemi-ai-reply-format strong { font-weight: 700; }'
      ].join('\n');
      document.head.appendChild(style);
    }

    function parseReplyBlocks(text) {
      const lines = text.replace(/\r\n?/g, '\n').split('\n');
      const blocks = [];
      let paragraph = [];
      let list = null;
      const flushParagraph = () => {
        if (paragraph.length) blocks.push({ type: 'paragraph', text: paragraph.join('\n') });
        paragraph = [];
      };
      const flushList = () => {
        if (list) blocks.push(list);
        list = null;
      };
      for (const line of lines) {
        if (!line.trim()) {
          flushParagraph();
          flushList();
          continue;
        }
        const heading = line.match(/^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$/);
        const item = line.match(/^\s{0,3}([-*+]|\d+[.)])\s+(.+)$/);
        if (heading) {
          flushParagraph();
          flushList();
          blocks.push({ type: 'heading', text: heading[1] });
        } else if (item) {
          flushParagraph();
          const ordered = /^\d/.test(item[1]);
          if (!list || list.ordered !== ordered) {
            flushList();
            list = { type: 'list', ordered, start: ordered ? Number.parseInt(item[1], 10) : 1, items: [] };
          }
          list.items.push(item[2]);
        } else {
          flushList();
          paragraph.push(line);
        }
      }
      flushParagraph();
      flushList();
      return blocks;
    }

    async function typeReplyText(node, text, row, sessionId) {
      for (const segment of getChatBoldSegments(text)) {
        const target = segment.bold ? document.createElement('strong') : document.createTextNode('');
        node.appendChild(target);
        for (let index = 0; index < segment.text.length; index += 3) {
          if (ctx.getSession()?.id !== sessionId || !row.isConnected) return false;
          target.textContent += segment.text.slice(index, index + 3);
          row.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          await new Promise((resolve) => setTimeout(resolve, 40));
        }
      }
      return true;
    }

    async function typeStructuredReply(row, text, sessionId) {
      ensureReplyStyles();
      row.classList.add('gaemi-ai-reply-format');
      for (const block of parseReplyBlocks(text)) {
        if (ctx.getSession()?.id !== sessionId || !row.isConnected) return false;
        if (block.type === 'list') {
          const listNode = document.createElement(block.ordered ? 'ol' : 'ul');
          listNode.className = 'ai-reply-list';
          if (block.ordered && block.start > 1) listNode.start = block.start;
          row.appendChild(listNode);
          for (const item of block.items) {
            const li = document.createElement('li');
            listNode.appendChild(li);
            if (!await typeReplyText(li, item, row, sessionId)) return false;
          }
        } else {
          const node = document.createElement(block.type === 'heading' ? 'div' : 'p');
          node.className = 'ai-reply-block' + (block.type === 'heading' ? ' ai-reply-heading' : '');
          row.appendChild(node);
          if (!await typeReplyText(node, block.text, row, sessionId)) return false;
        }
      }
      return true;
    }

    // The five existing response actions are attached only after typing ends.
    async function appendChatReply(answer, sessionId) {
      const text = String(answer || '').trim();
      if (!text || ctx.getSession()?.id !== sessionId) return false;
      const row = ctx.appendChatMessage('assistant', text, 'answer', sessionId);
      if (!row) return false;
      row.textContent = '';
      row.classList.add('typing-cursor');
      if (!await typeStructuredReply(row, text, sessionId)) return false;
      row.classList.remove('typing-cursor');
      if (ctx.getSession()?.id !== sessionId || !row.isConnected) return false;
      const actions = window.GaemiGTPFirstReplyActions?.appendFirstReplyActions?.(
        row, text, 'ai-' + row.dataset.chatMessageId, ctx.getSession().stock || ''
      );
      // AI 답변의 타이핑 흐름을 마지막 '싫어요' 아이콘까지 이어간다.
      // 기존 공통 액션 생성/클릭 로직은 그대로 재사용한다.
      if (actions) {
        const buttons = [...actions.querySelectorAll('[data-first-reply-action]')];
        buttons.forEach((button) => {
          button.style.visibility = 'hidden';
          button.style.pointerEvents = 'none';
        });
        for (const button of buttons) {
          if (ctx.getSession()?.id !== sessionId || !row.isConnected) return false;
          button.style.visibility = '';
          button.style.pointerEvents = '';
          button.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
          await new Promise((resolve) => setTimeout(resolve, 90));
        }
      }
      return true;
    }

    function appendChatError(text, sessionId) {
      if (ctx.getSession()?.id !== sessionId) return;
      const row = ctx.appendChatMessage('assistant', text, 'error', sessionId);
      row?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    async function requestChatAnswer(question, sessionId, history) {
      const controller = new AbortController();
      ctx.setActiveQuestionController(controller);
      ctx.setPendingQuestionSessionId(sessionId);
      const mentionedStock = window.GaemiGTPCenterChatSearch?.resolveStockMention?.(question) || '';
      const stock = mentionedStock || ctx.getSession()?.stock || '';
      const marketSelection = !mentionedStock || mentionedStock === ctx.getSession()?.stock
        ? ctx.getSession()?.marketSelection : null;
      const errors = {
        stock_data_unavailable: '종목 데이터를 확인하지 못했어.',
        invalid_input: '종목명을 함께 입력해 줘.',
        minute_limit: '잠시 뒤에 다시 물어봐.',
        model_daily_limit: '오늘은 더 답변하기 어려워.',
        total_daily_limit: '오늘은 더 답변하기 어려워.',
        private_access_required: '로그인이 필요해.',
        ai_test_not_configured: '아직 답변을 준비하지 못했어.'
      };
      // 기존 중앙 채팅 로딩 스타일을 그대로 사용한다. 별도 AI 아이콘은 표시하지 않는다.
      const loading = document.createElement('div');
      loading.className = 'analysis-loading-sequence animate-fade';
      loading.setAttribute('role', 'status');
      loading.setAttribute('aria-live', 'polite');
      const loadingText = document.createElement('p');
      loadingText.className = 'analysis-loading-message is-visible is-shimmer';
      loadingText.textContent = '생각 중';
      loading.appendChild(loadingText);
      document.getElementById('chatArea')?.appendChild(loading);

      const updateWaiting = (message) => {
        if (ctx.getSession()?.id === sessionId && !controller.signal.aborted && loading.isConnected) {
          loadingText.textContent = message;
        }
      };
      const waitingTimers = [
        setTimeout(() => updateWaiting('조금 더 걸리고 있어'), 10000),
        setTimeout(() => updateWaiting('응답이 지연되고 있어. 잠시만 기다려줘'), 20000)
      ];
      const stopThinking = () => {
        waitingTimers.forEach(clearTimeout);
        loading.remove();
      };
      try {
        // If the first stock analysis is in flight, wait for its shared
        // server-side result instead of collecting the same data twice.
        if (ctx.getPendingAnalysis()?.stock === stock) await ctx.getPendingAnalysis().promise;
        if (controller.signal.aborted || ctx.getSession()?.id !== sessionId) return;
        const response = await fetch(ctx.backendUrl + '/api/ai-test/chat', {
          method: 'POST',
          credentials: 'same-origin',
          signal: controller.signal,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            role: 'cloudflare', stock, question, history,
            ...(marketSelection ? { market_selection: {
              market: marketSelection.market, menu: marketSelection.menu,
              symbol: marketSelection.symbol,
              sort: marketSelection.sort === 'change_pct' ? 'change_pct' : 'source'
            } } : {})
          })
        });
        const result = await response.json();
        if (controller.signal.aborted || ctx.getSession()?.id !== sessionId) return;
        if (!response.ok || !result.ok || !result.answer) {
          stopThinking();
          appendChatError(errors[result.error] || '지금 답변을 가져오지 못했어.', sessionId);
          return;
        }
        if (result.stock) {
          // AI가 다른 종목을 답했다면 이전 종목의 뉴스·공시 결과를 새 종목에 연결하지 않는다.
          const snapshotStock = window.GaemiGTPAnalysisData?.get?.()?.stockName;
          if (snapshotStock && snapshotStock !== result.stock) {
            window.GaemiGTPAnalysisData?.set?.(result.stock, {});
          }
          if (ctx.getSession().marketSelection?.name !== result.stock) ctx.getSession().marketSelection = null;
          ctx.getSession().stock = result.stock;
          ctx.setStock(result.stock);
          window.GaemiGTPActiveStock = result.stock;
          window.GaemiGTPWorkspaceShellState?.save?.();
        }
        stopThinking();
        await appendChatReply(result.answer, sessionId);
      } catch (error) {
        if (error?.name !== 'AbortError' && ctx.getSession()?.id === sessionId) {
          appendChatError('지금 답변을 가져오지 못했어.', sessionId);
        }
      } finally {
        stopThinking();
        if (ctx.getActiveQuestionController() === controller) ctx.setActiveQuestionController(null);
        if (ctx.getPendingQuestionSessionId() === sessionId) ctx.setPendingQuestionSessionId(null);
      }
    }

    return { submitQuestion, requestChatAnswer, appendChatReply };
  }
  window.GaemiGTPCenterAIChat = { create };
}());
