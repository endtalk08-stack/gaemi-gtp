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
        '.gaemi-ai-reply-format { white-space: normal; overflow-wrap: break-word; }',
        '.gaemi-ai-reply-format .ai-reply-block { margin: 0 0 0.8em; line-height: 1.76; white-space: pre-wrap; font-size: 1em; font-weight: 400; }',
        '.gaemi-ai-reply-format .ai-reply-heading { display: block; font-size: 1.06em; font-weight: 750; line-height: 1.5; letter-spacing: -0.015em; margin: 1.2em 0 0.48em; padding: 0; white-space: normal; }',
        '.gaemi-ai-reply-format > .ai-reply-heading:first-child { margin-top: 0; }',
        '.gaemi-ai-reply-format .ai-reply-list { padding-left: 0; margin: 0 0 0.85em; list-style-position: inside; white-space: normal; }',
        '.gaemi-ai-reply-format .ai-reply-list li { margin: 0.32em 0; line-height: 1.72; white-space: pre-wrap; }',
        '.gaemi-ai-reply-format strong { font-weight: 730; }',
        '.gaemi-ai-reply-format .ai-reply-heading + .ai-reply-block { margin-top: 0; }',
        '.gaemi-ai-reply-format > .ai-reply-block:last-child, .gaemi-ai-reply-format > .ai-reply-list:last-child { margin-bottom: 0; }'
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
        const markdownHeading = line.match(/^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$/);
        const boldHeading = line.match(/^\s*\*\*(.{2,65}?)\*\*\s*[:：]?\s*$/);
        const item = line.match(/^\s{0,3}([-*+]|\d+[.)])\s+(.+)$/);
        if (markdownHeading || boldHeading) {
          flushParagraph();
          flushList();
          blocks.push({ type: 'heading', text: markdownHeading ? markdownHeading[1] : boldHeading[1] });
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
        // Put the blinking caret on the currently typed inline text, not on
        // the outer response row (which places it after all block elements).
        const previousCaret = row.querySelector('.typing-cursor');
        previousCaret?.classList.remove('typing-cursor');
        const target = document.createElement(segment.bold ? 'strong' : 'span');
        target.classList.add('typing-cursor');
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
    async function appendChatReply(answer, sessionId, presentation = null) {
      const structured = window.GaemiGTPUSCloseReply?.normalize?.(presentation) || null;
      const text = structured ? window.GaemiGTPUSCloseReply.plainText(structured) : String(answer || '').trim();
      if (!text || ctx.getSession()?.id !== sessionId) return false;
      const row = ctx.appendChatMessage('assistant', text, 'answer', sessionId);
      if (!row) return false;
      row.textContent = '';
      const typed = structured
        ? await window.GaemiGTPUSCloseReply.render(row, structured, {
            isActive: () => ctx.getSession()?.id === sessionId && row.isConnected,
            typeText: (element, value) => typeReplyText(element, value, row, sessionId)
          })
        : await typeStructuredReply(row, text, sessionId);
      // Cleanup on both completed and interrupted responses.
      row.querySelector('.typing-cursor')?.classList.remove('typing-cursor');
      if (!typed) return false;
      if (ctx.getSession()?.id !== sessionId || !row.isConnected) return false;
      // The display renderer consumes Markdown markers (headings, bold, lists).
      // Copy/share/read must receive what the user actually sees, not the
      // original AI text kept for conversation history and model context.
      const visibleReplyText = (row.innerText || row.textContent || text).trim();
      const actions = window.GaemiGTPFirstReplyActions?.appendFirstReplyActions?.(
        row, visibleReplyText, 'ai-' + row.dataset.chatMessageId, ctx.getSession().stock || ''
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

    // The daily US market-close question is served from Neon without a new AI call.
    function isUsMarketCloseQuestion(question) {
      const compact = String(question || '').replace(/\s+/g, '');
      return compact.length <= 35 &&
        /^(미국장|미장|미국증시|뉴욕증시)/.test(compact) &&
        /(어땠|마감|시황|요약|정리)/.test(compact);
    }

    // A factual issue question uses stored article briefs; movement-cause
    // questions still use the existing AI chat/model path below.
    function isArticleIssueQuestion(question) {
      const q = String(question || '').replace(/\s+/g, '');
      return q.length <= 60
        && /(이슈|뉴스|소식|재료|기사)/.test(q)
        && /(있어|있나|있니|뭐야|뭔데|알려|보여|정리|최근|오늘|핵심)/.test(q)
        && !/(왜|원인|이유|때문|영향으로|올랐|떨어졌|하락했|상승했)/.test(q);
    }

    async function requestChatAnswer(question, sessionId, history) {
      // Freeze mode at the moment the question was sent, not after
      // asynchronous stock analysis or a later mode dropdown change.
      const appMode = ['gaemi', 'info', 'pro'].includes(
        window.GaemiGTPAppState?.getCurrentAppMode?.()
      ) ? window.GaemiGTPAppState.getCurrentAppMode() : 'gaemi';
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
        ai_test_not_configured: '아직 답변을 준비하지 못했어.',
        ai_mode_disabled: 'gaemi는 AI 질문을 사용하지 않아. info 또는 pro를 선택해 줘.',
        unsupported_mode: '분석 모드를 다시 선택해 줘.',
        groq_rate_limit: 'AI 제공사 사용량 한도에 도달했어. 잠시 뒤에 다시 시도해 줘.'
      };
      // 기존 중앙 채팅 로딩 스타일을 그대로 사용한다. 별도 AI 아이콘은 표시하지 않는다.
      const thinkingStartedAt = Date.now();
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
        if (appMode === 'gaemi' && !mentionedStock && isUsMarketCloseQuestion(question)) {
          // Reuse the '왜 올랐어?' 5-second thinking rhythm; fetch in parallel.
          loadingText.textContent = '생각중';
          loadingText.classList.add('animate-pulse');
          const response = await fetch(ctx.backendUrl + '/api/market/us-close', {
            method: 'GET', credentials: 'same-origin', signal: controller.signal
          });
          const result = await response.json();
          const remaining = 5000 - (Date.now() - thinkingStartedAt);
          if (remaining > 0) await new Promise(resolve => setTimeout(resolve, remaining));
          if (controller.signal.aborted || ctx.getSession()?.id !== sessionId) return;
          stopThinking();
          if (!response.ok || !result.ok) {
            appendChatError('미국장 마감시황을 불러오지 못했어.', sessionId);
          } else if (!result.available || !result.content) {
            await appendChatReply('해당 거래일의 미국장 마감시황이 아직 준비되지 않았어.', sessionId);
          } else {
            await appendChatReply(result.content, sessionId, result.presentation);
          }
          return;
        }
        if (appMode === 'gaemi' && stock && isArticleIssueQuestion(question)) {
          // Never spend AI tokens just to display the existing source-verified
          // article issue feed. Do not guess why a stock moved.
          const issueParams = new URLSearchParams({
            stock, market: marketSelection?.market === 'kr' ? 'kr' : 'us',
            issue_mode: 'code', question
          });
          if (marketSelection?.symbol) issueParams.set('symbol', marketSelection.symbol);
          const response = await fetch(ctx.backendUrl + '/api/news/issues?' + issueParams, {
            method: 'GET', credentials: 'same-origin', signal: controller.signal
          });
          const news = await response.json();
          if (controller.signal.aborted || ctx.getSession()?.id !== sessionId) return;
          stopThinking();
          if (!response.ok || !news?.ok) {
            appendChatError('뉴스 이슈를 불러오지 못했어.', sessionId);
            return;
          }
          const briefs = Array.isArray(news.issue_briefs) ? news.issue_briefs : [];
          if (!briefs.length) {
            await appendChatReply('확인된 기사 팩트 이슈가 아직 없어.', sessionId);
            return;
          }
          const text = briefs.map((item) => {
            const sources = (Array.isArray(item.source_articles) ? item.source_articles : [])
              .filter(source => /^https?:\/\//.test(String(source?.url || '')))
              .slice(0, 1);
            return [
              '**' + String(item.headline || '기사 이슈') + '**',
              String(item.summary || '').trim(),
              (Array.isArray(item.tags) ? item.tags : []).slice(0, 3)
                .map(tag => '#' + String(tag).replace(/^#/, '')).join('  '),
              sources.length ? '원문: ' + sources[0].url : ''
            ].filter(Boolean).join('\n');
          }).join('\n\n');
          await appendChatReply(text, sessionId);
          return;
        }
        const response = await fetch(ctx.backendUrl + '/api/ai-test/chat', {
          method: 'POST',
          credentials: 'same-origin',
          signal: controller.signal,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            app_mode: appMode, stock, question, history,
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
