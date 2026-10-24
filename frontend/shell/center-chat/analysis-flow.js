/* Existing central stock-analysis display flow. Moved without changing rendering logic. */
(function () {
  'use strict';
  // The left sidebar passes its displayed change_pct with the stock selection.
  // Technical-indicator percentages in analysis prose must not affect this label.
  function whyChoiceFromChange(rawChange) {
    if (rawChange === null || rawChange === undefined || rawChange === '' ||
        typeof rawChange === 'boolean') {
      return { label: '왜 움직였을까?', tag: '#왜_움직였을까?', color: '#94A3B8' };
    }
    const change = Number(rawChange);
    if (!Number.isFinite(change)) {
      return { label: '왜 움직였을까?', tag: '#왜_움직였을까?', color: '#94A3B8' };
    }
    if (change > 0) return { label: '왜 빨간불일까?', tag: '#왜_빨간불일까?', color: '#FF8DA1' };
    if (change < 0) return { label: '왜 파란불일까?', tag: '#왜_파란불일까?', color: '#38BDF8' };
    return { label: '왜 보합일까?', tag: '#왜_보합일까?', color: '#94A3B8' };
  }
  // Stretch only the existing 52-week marker bar; preserve the source percentages.
  function stretch52WeekBar(markup) {
    const lines = markup.split('\n');
    const index = lines.findIndex(line =>
      line.includes('52주') && line.includes('저가') && line.includes('고가') &&
      line.includes('├') && line.includes('┤')
    );
    if (index < 0 || index + 2 >= lines.length) return markup;
    const bar = lines[index].match(/├(█*●─*)┤/)?.[1];
    if (!bar || !lines[index + 1].includes('현재')) return markup;
    const gapMarkup = lines[index + 2].replace(/^[\s\u00a0]+/g, '').trim();
    if (!/^(신고가까지|52주 신고가)/.test(gapMarkup)) return markup;
    const position = 100 * bar.indexOf('●') / Math.max(1, bar.length - 1);
    const marker = position.toFixed(2);
    const label = Math.max(4, Math.min(96, position)).toFixed(2);
    lines.splice(index, 3, `<span data-gaemi-52w-range="true" style="display:block;width:100%;max-width:100%;white-space:normal;margin-top:8px;"><span style="display:flex;align-items:flex-start;gap:10px;width:100%;"><span style="white-space:nowrap;">52주 저가</span><span style="position:relative;display:block;flex:1 1 0%;min-width:0;height:34px;padding-top:7px;"><span style="display:block;width:100%;height:9px;border-radius:999px;background:rgba(148,163,184,.25);overflow:hidden;"><span style="display:block;width:${marker}%;height:100%;background:#a1a1aa;"></span></span><span style="position:absolute;left:${marker}%;top:11.5px;transform:translate(-50%,-50%);width:13px;height:13px;border-radius:50%;background:#d4d4d8;border:2px solid #71717a;"></span><span style="position:absolute;left:${label}%;top:18px;transform:translateX(-50%);font-size:12px;white-space:nowrap;">현재</span></span><span style="white-space:nowrap;">고가</span></span><span style="display:block;text-align:center;margin-top:3px;">${gapMarkup}</span></span>`);
    return lines.join('\n');
  }

  function create(ctx) {
    let kiwoomQuoteTimer = null;
    function stopKiwoomQuoteTimer() {
      if (kiwoomQuoteTimer !== null) clearInterval(kiwoomQuoteTimer);
      kiwoomQuoteTimer = null;
    }

    function quoteIntro(name, change) {
      if (!Number.isFinite(change)) return [name + ' 키움 실시간 현재가 확인 중', '', ''];
      const pct = (change >= 0 ? '+' : '') + change.toFixed(2) + '%';
      if (change >= 5) return ['오!! ' + name + ' ', pct, ' 상승중이야'];
      if (change >= 0.5) return ['스멀스멀 ', pct, ' 우상향 중이야'];
      if (change > -0.5) return ['하아.. ' + name + ' ', pct, '로 완전 눈치싸움 중이네'];
      if (change > -5) return ['아이고 ' + name + ' ', pct, ' 파란불 켜져서 속 쓰리겠다'];
      return ['헐... ' + name + ' ', pct, ' 무섭게 빠지네'];
    }

    // Reuse the exact in-memory Kiwoom quote feed used by the left sidebar.
    // Historical indicators remain the analysis-time snapshot.
    function startKiwoomQuoteTimer(name, result, requestId, firstParagraph) {
      const snapshot = result?.price_snapshot || {};
      const ticker = String(snapshot.ticker_symbol || '').toUpperCase();
      if (!String(snapshot.quote_source || '').startsWith('kiwoom-') ||
          !/^[A-Z0-9][A-Z0-9.\-]{0,19}$/.test(ticker)) return;
      const intro = firstParagraph.querySelector('[data-kiwoom-intro]');
      const current = firstParagraph.querySelector('[data-kiwoom-current]');
      if (!intro || !current) return;
      stopKiwoomQuoteTimer();
      let inFlight = false;
      const refresh = async () => {
        if (requestId !== ctx.getActiveAnalysisRequestId() || !firstParagraph.isConnected) {
          stopKiwoomQuoteTimer();
          return;
        }
        if (document.visibilityState !== 'visible' || inFlight) return;
        inFlight = true;
        try {
          const response = await fetch(BACKEND_URL + '/market/us-live-quotes', { cache: 'no-store' });
          if (!response.ok) return;
          const body = await response.json();
          if (!body || !Array.isArray(body.items)) return;
          const quote = body.items.find((item) => item.symbol === ticker && !item.stale);
          if (!quote || !Number.isFinite(quote.price) || quote.price <= 0 ||
              requestId !== ctx.getActiveAnalysisRequestId()) return;
          current.textContent = '현재 주가는 $' +
            quote.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) +
            ' 기록 중!';
          const change = Number.isFinite(quote.change_pct) ? quote.change_pct : null;
          const [before, percent, after] = quoteIntro(name, change);
          if (percent) {
            const span = document.createElement('span');
            span.className = 'font-bold';
            span.style.color = change >= 0 ? '#FF8DA1' : '#38BDF8';
            span.textContent = percent;
            intro.replaceChildren(document.createTextNode(before), span, document.createTextNode(after));
          } else {
            intro.textContent = before;
          }
        } catch (_) {
          // Keep the last confirmed quote on a transient connection failure.
        } finally {
          inFlight = false;
        }
      };
      void refresh();
      kiwoomQuoteTimer = setInterval(refresh, 3000);
    }

    function startTypewriterFlow(stockName, sections, result, requestId) {
      if (requestId !== ctx.getActiveAnalysisRequestId()) return;
      const chatArea = document.getElementById('chatArea');
      const wrapperId = 'stream-' + Date.now();

      const mainContainer = document.createElement('div');
      mainContainer.id = wrapperId;
      mainContainer.className = "space-y-7 py-2";
      chatArea.appendChild(mainContainer);

      // 첫 답변의 본문 크기·색상·반응형 규칙을 안내/연출 멘트의 공통 기준으로 쓴다.
      const responseMessageClass = 'gtp-chat-copy';

      let secIdx = 0;

      function appendNextAnalysisChoices(anchor) {
        if (!anchor || anchor.parentElement?.querySelector('[data-next-analysis-choices]')) return;

        // Only the selected sidebar's quote controls red/blue/flat prompts.
        const whyState = whyChoiceFromChange(ctx.getSession()?.marketSelection?.change_pct);

        const makeUserPrompt = (text, dataName) => {
          const prompt = document.createElement('div');
          if (dataName) prompt.dataset[dataName] = 'true';
          prompt.className = 'flex justify-end animate-fade';
          const bubble = document.createElement('div');
          bubble.className = 'bg-[#f1f5f9] dark:bg-[#1e1f24] text-[#0f172a] gtp-dark-text gtp-chat-user px-5 py-3 rounded-2xl border border-[#cbd5e1] dark:border-[#3f3f46]';
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

          const articles = Array.isArray(result.storyboard_news_items) ? result.storyboard_news_items : [];
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
          followups.className = 'mt-6 space-y-2';
          followups.innerHTML = `
            <p class="${responseMessageClass}">더 살펴볼래?</p>
            <div class="flex flex-wrap items-center gap-x-3 gap-y-1.5">
            </div>`;
          after.insertAdjacentElement('afterend', followups);
          return followups;
        };

        const choices = document.createElement('section');
        choices.dataset.nextAnalysisChoices = 'true';
        choices.className = 'mt-6 space-y-2 text-right';
        choices.innerHTML = `
          <p class="${responseMessageClass}"></p>
          <div class="flex flex-wrap items-center justify-end gap-x-3 gap-y-1.5">
            <button type="button" class="text-sm font-semibold text-[#3b82f6] transition hover:text-[#2563eb] dark:text-[#7aa2e3] dark:hover:text-[#9ab8ee]" data-next-analysis="us-market"></button>
            <button type="button" class="text-sm font-semibold transition hover:opacity-80" style="color:${whyState.color}" data-next-analysis="why"></button>
            <button type="button" class="text-sm font-semibold text-[#8f7aa8] transition hover:text-[#9d87b8] dark:text-[#a995bd] dark:hover:text-[#b7a4c9]" data-next-analysis="fortune"></button>
          </div>`;

        const isGaemiMode = () => ctx.getSession()?.mode === 'gaemi';
        const appendUsMarketPrompt = async () => {
          // US-close is a deterministic gaemi follow-up, never an info/pro model route.
          if (!isGaemiMode() || mainContainer.querySelector('[data-us-market-prompt]')) return;
          const prompt = makeUserPrompt('미국장 어땠어?', 'usMarketPrompt');
          prompt.classList.remove('animate-fade');
          choices.insertAdjacentElement('afterend', prompt);
          prompt.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

          // Exactly the '왜 올랐어?' five-second loading / typewriter flow.
          const loading = document.createElement('div');
          loading.className = 'mt-5 space-y-2';
          const loadingLine = document.createElement('p');
          loadingLine.className = responseMessageClass + ' font-semibold animate-pulse';
          loadingLine.textContent = '생각중';
          loading.appendChild(loadingLine);
          prompt.insertAdjacentElement('afterend', loading);
          const isActive = () => isGaemiMode() && requestId === ctx.getActiveAnalysisRequestId() && prompt.isConnected;
          const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
          let replyText = '';
          let verifiedContent = '';
          let presentation = null;
          try {
            const [{ response, result }] = await Promise.all([
              fetch(ctx.backendUrl + '/api/market/us-close', {
                method: 'GET', credentials: 'same-origin'
              }).then(async response => ({ response, result: await response.json() })),
              wait(5000)
            ]);
            if (!isActive()) return;
            if (!response.ok || !result?.ok) {
              replyText = '미국장 마감시황을 불러오지 못했어.';
            } else if (!result.available || !result.content) {
              replyText = '해당 거래일의 미국장 마감시황이 아직 준비되지 않았어.';
            } else {
              // Never discard the verified Neon editorial when optional
              // index-table formatting or client typewriting fails.
              verifiedContent = String(result.content).trim();
              replyText = verifiedContent;
              const structured = window.GaemiGTPUSCloseReply?.normalize?.(result.presentation);
              if (structured) {
                const formattedText = window.GaemiGTPUSCloseReply?.plainText?.(structured);
                if (typeof formattedText === 'string' && formattedText.trim()) {
                  presentation = structured;
                  replyText = formattedText;
                }
              }
            }
          } catch (error) {
            if (!isActive()) return;
            console.warn('[gaemi us-close] request/format failed:', error?.name || 'unknown');
            presentation = null;
            replyText = verifiedContent || '미국장 마감시황을 불러오지 못했어.';
          } finally {
            loading.remove();
          }
          if (!isActive()) return;
          const answer = document.createElement('div');
          answer.className = responseMessageClass + ' mt-4';
          prompt.insertAdjacentElement('afterend', answer);
          try {
            if (presentation) {
              const complete = await window.GaemiGTPUSCloseReply.render(answer, presentation, {
                isActive: () => isActive() && answer.isConnected,
                typeText: (element, text) => typeText(element, text, { chunkSize: 1 })
              });
              if (!complete && isActive()) throw new Error('us_close_renderer_incomplete');
              if (!complete) return;
            } else {
              await typeText(answer, replyText, { chunkSize: 1 });
            }
          } catch (error) {
            // Recovery must show the actual saved editorial, not a generic
            // 'could not display' message after the five-second wait.
            if (!isActive()) return;
            console.warn('[gaemi us-close] presentation failed:', error?.name || 'unknown');
            answer.classList.remove('typing-cursor');
            answer.textContent = verifiedContent || replyText || '미국장 마감시황을 불러오지 못했어.';
          }
          if (!isActive() || !answer.isConnected) return;
          // Reuse the displayed result for actions: Markdown/table rendering
          // must not leak raw formatting tokens into copy/share/speech.
          const visibleReplyText = (answer.innerText || answer.textContent || replyText).trim();
          window.GaemiGTPFirstReplyActions?.appendFirstReplyActions?.(
            answer, visibleReplyText, 'us-market-followup', stockName
          );
          answer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        };

        const appendRemainingChoices = (after, completed = []) => {
          if (!after || !after.isConnected) return;
          const remaining = [
            ...(isGaemiMode() ? [{ key: 'us-market', label: '#미국장_어땠어?', className: 'text-[#3b82f6] dark:text-[#7aa2e3]' }] : []),
            { key: 'why', label: whyState.tag, color: whyState.color },
            { key: 'fortune', label: '#떡상운세', className: 'text-[#8f7aa8] hover:text-[#9d87b8] dark:text-[#a995bd] dark:hover:text-[#b7a4c9]' }
          ].filter((item) => !completed.includes(item.key));
          if (!remaining.length) return;

          const followup = document.createElement('section');
          followup.dataset.nextAnalysisChoices = 'true';
          followup.className = 'mt-6 space-y-2 text-right';
          followup.innerHTML = `
            <p class="${responseMessageClass}">더 볼래?</p>
            <div class="flex flex-wrap items-center justify-end gap-x-3 gap-y-1.5"></div>`;
          const row = followup.querySelector('div');
          remaining.forEach((item) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.dataset.nextAnalysis = item.key;
            button.className = `text-sm font-semibold transition hover:opacity-80 ${item.className || ''}`;
            if (item.color) button.style.color = item.color;
            button.textContent = item.label;
            button.addEventListener('click', handleNextAnalysisChoice);
            row.appendChild(button);
          });
          after.insertAdjacentElement('afterend', followup);
          return followup;
        };

        const appendFortunePrompt = async () => {
          if (mainContainer.querySelector('[data-fortune-prompt]')) return;

          // 1) 떡상운세 사용자 말풍선을 먼저 표시한다.
          const prompt = makeUserPrompt('떡상운세', 'fortunePrompt');
          choices.insertAdjacentElement('afterend', prompt);
          prompt.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

          // 2) 말풍선 다음에 로딩 연출 멘트를 정확히 4초 동안 보여준다.
          const loading = document.createElement('div');
          loading.dataset.fortuneLoading = 'true';
          loading.className = 'analysis-loading-sequence animate-fade';
          loading.innerHTML = `
            <div class="analysis-loading-message is-visible" aria-live="polite">
              동쪽에서 밀려오는 떡상 기운을 측정하고 있습니다
            </div>`;
          const loadingMessage = loading.querySelector('.analysis-loading-message');
          prompt.insertAdjacentElement('afterend', loading);
          requestAnimationFrame(() => {
            if (loading.isConnected) loadingMessage?.classList.add('is-shimmer');
          });

          try {
            await new Promise((resolve) => setTimeout(resolve, 4000));
            if (requestId !== ctx.getActiveAnalysisRequestId() || !mainContainer.isConnected) return;
          } finally {
            loading.remove();
          }

          // 3) 로딩이 끝난 뒤 운세 결과만 타이핑 효과로 출력한다.
          const fortune = document.createElement('div');
          fortune.dataset.fortuneResult = 'true';
          fortune.className = 'space-y-3 animate-fade';
          const fortuneText = window.GaemiGTPDailyFortune.buildDailyFortune();
          const resultText = document.createElement('p');
          resultText.className = `${responseMessageClass} whitespace-pre-line`;
          fortune.appendChild(resultText);
          prompt.insertAdjacentElement('afterend', fortune);
          await typeText(resultText, fortuneText, { chunkSize: 3 });

          // 기존 첫 답변과 같은 액션 버튼을 운세 하단에도 붙인다.
          // 복사/공유는 운세 텍스트만 대상으로 하고, 좋아요/싫어요는 같은 UI 동작을 재사용한다.
          const fortuneActions = window.GaemiGTPFirstReplyActions.appendFirstReplyActions(resultText, fortuneText, 'fortune', stockName);
          // 액션 모듈은 기본적으로 첫 답변용 그룹만 렌더링하므로,
          // fortune 그룹을 별도로 넘기지 않고 기존 검증된 액션 UI를 그대로 재사용한다.
          if (!fortuneActions) window.GaemiGTPFirstReplyActions.appendFirstReplyActions(resultText, fortuneText, 'first', stockName);
          // 액션 버튼은 resultText의 형제로 붙으므로 운세 컨테이너의 마지막 요소 뒤에
          // 남은 선택지를 연결해야 액션 모듈의 중복 검사에 막히지 않는다.
          const fortuneTail = fortune.lastElementChild || resultText;
          appendRemainingChoices(fortuneTail, ['fortune']);
          fortune.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        };

        const appendMaterials = async (choiceAnchor = choices) => {
          return window.GaemiGTPMaterialsFlow.appendMaterials({
            mainContainer,
            requestId,
            getActiveAnalysisRequestId: () => ctx.getActiveAnalysisRequestId(),
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
            if (requestId !== ctx.getActiveAnalysisRequestId() || !mainContainer.isConnected) return;
            const chunk = text.substr(charIndex, chunkSize);
            element.textContent += chunk;
            charIndex += chunk.length;
            const pause = /[.!?…]$/.test(chunk) ? 180 : (/\n$/.test(chunk) ? 120 : 40);
            await new Promise((resolve) => setTimeout(resolve, pause));
          }
          element.classList.remove('typing-cursor');
        };

        const appendWhy = async (inline = false) => {
          return window.GaemiGTPWhyFlow.appendWhy({
            inline,
            mainContainer,
            requestId,
            getActiveAnalysisRequestId: () => ctx.getActiveAnalysisRequestId(),
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

        async function handleNextAnalysisChoice(event) {
          const button = event.currentTarget;
          const choiceSection = button.closest('[data-next-analysis-choices]');
          if (button.dataset.nextAnalysis === 'us-market') {
            if (!isGaemiMode()) return;
            // 미국장 흐름도 최초 choices 객체를 기준으로 말풍선을 붙이므로
            // 운세 뒤 follow-up에서 누른 경우 원본 앵커를 현재 위치에 복원한다.
            if (choiceSection && choiceSection !== choices) {
              choiceSection.replaceWith(choices);
            }
            appendUsMarketPrompt();
            choices.remove();
            return;
          }
          if (button.dataset.nextAnalysis === 'why') {
            // 기존 why-flow는 최초 choices 객체를 직접 참조한다.
            // 최초 choices는 운세 시작 때 DOM에서 제거됐으므로, 현재 follow-up 위치에
            // 그 동일한 객체를 다시 붙인 뒤 why-flow를 실행한다.
            if (choiceSection && choiceSection !== choices) {
              choiceSection.replaceWith(choices);
            }
            await appendWhy();
            return;
          }
          if (button.dataset.nextAnalysis === 'fortune') {
            // Follow-up buttons must restore the original anchor before the
            // existing fortune flow inserts its user prompt.
            if (choiceSection && choiceSection !== choices) {
              choiceSection.replaceWith(choices);
            }
            const fortuneFlow = appendFortunePrompt();
            choices.remove();
            await fortuneFlow;
            return;
          }
          if (button.dataset.nextAnalysis === 'materials') await appendMaterials();
        }
        if (!isGaemiMode()) choices.querySelector('[data-next-analysis="us-market"]')?.remove();
        choices.querySelectorAll('[data-next-analysis]').forEach((button) => {
          button.addEventListener('click', handleNextAnalysisChoice);
        });

        anchor.insertAdjacentElement('afterend', choices);
        // Only the new sourced AI reason triggers the requested initial reason/issues layout.
        // Existing replies and their buttons remain unchanged if none is available.
        if (result.price_reason?.headline && result.price_reason?.summary) {
          void appendWhy(true);
        }

        const typeInitialChoices = async () => {
          const sequence = [
            [choices.querySelector('p'), '뭐가 궁금해?'],
            [choices.querySelector('[data-next-analysis="us-market"]'), '#미국장_어땠어?'],
            [choices.querySelector('[data-next-analysis="why"]'), whyState.tag],
            [choices.querySelector('[data-next-analysis="fortune"]'), '#떡상운세']
          ];
          for (const [element, text] of sequence) {
            if (requestId !== ctx.getActiveAnalysisRequestId() || !choices.isConnected) return;
            if (!element) continue;
            await typeText(element, text, { chunkSize: 1 });
          }
        };
        typeInitialChoices();
      }

      function typeNextSection() {
        if (requestId !== ctx.getActiveAnalysisRequestId()) return;
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
        const headingMarkup = dynamicTitle
          ? `<div class="flex items-center gap-2.5"><h4 class="gtp-chat-section-title text-[#0f172a] gtp-dark-text">${dynamicTitle}</h4></div>`
          : '';
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
        const firstAnswerTagMatch = sec.id === 'why-up'
          ? text.match(/(?:^|\n\n)([^\n]*#[^\n]*)$/)
          : null;
        const firstAnswerTagStart = firstAnswerTagMatch
          ? text.lastIndexOf(firstAnswerTagMatch[1])
          : -1;
        const risingFirstAnswerTags = new Set([
          '#고가갱신', '#고가권', '#당일고가권', '#단기상승', '#상승우위', '#장기상승구간',
          '#가즈아', '#불기둥', '#우상향', '#야금야금'
        ]);
        const fallingFirstAnswerTags = new Set([
          '#저가갱신', '#저가권', '#당일저가권', '#단기하락', '#하락우위', '#장기하락구간',
          '#숨고르기', '#버터보자', '#버텨보자', '#투매금지', '#멘탈관리'
        ]);
        const firstAnswerTagColor = (tag) => {
          const value = String(tag || '').trim();
          if (value.includes('+') || risingFirstAnswerTags.has(value)) return '#FF8DA1';
          if (value.includes('-') || fallingFirstAnswerTags.has(value)) return '#38BDF8';
          return '#94A3B8';
        };
        let activeTagSpan = null;
        let activePercentSpan = null;
        let activePercentLength = 0;

        const appendTypingChunk = (chunk, chunkStart) => {
          for (let offset = 0; offset < chunk.length; offset++) {
            const char = chunk[offset];
            const absoluteIndex = chunkStart + offset;
            // 등락률은 완성 뒤에 한꺼번에 칠하지 않는다. 부호가 출력되는 순간
            // span을 만들어서 타이핑되는 숫자 전체가 처음부터 같은 색을 유지한다.
            if (!activePercentSpan && (char === '+' || char === '-')) {
              const fullPercent = (text.slice(absoluteIndex).match(/^[+-]\d+(?:\.\d+)?%/) || [null])[0];
              if (fullPercent) {
                activePercentSpan = document.createElement('span');
                activePercentSpan.className = 'font-bold';
                activePercentSpan.style.color = fullPercent.startsWith('+') ? '#FF8DA1' : '#38BDF8';
                activePercentLength = fullPercent.length;
                pEl.appendChild(activePercentSpan);
              }
            }
            if (activePercentSpan) {
              activePercentSpan.textContent += char;
              activePercentLength -= 1;
              if (activePercentLength === 0) activePercentSpan = null;
              continue;
            }
            if (firstAnswerTagStart >= 0 && absoluteIndex >= firstAnswerTagStart) {
              if (char === '#') {
                const fullTag = (text.slice(absoluteIndex).match(/^#[^\s]+/) || ['#'])[0];
                activeTagSpan = document.createElement('span');
                activeTagSpan.className = 'font-bold first-answer-hashtag';
                activeTagSpan.style.color = firstAnswerTagColor(fullTag);
                pEl.appendChild(activeTagSpan);
              }
              if (activeTagSpan && !/\s/.test(char)) {
                activeTagSpan.textContent += char;
                continue;
              }
              if (/\s/.test(char)) activeTagSpan = null;
            }
            pEl.appendChild(document.createTextNode(char));
          }
        };

        // 첫 답변의 마지막 해시태그 줄은 최종 색상을 유지한 채 타이핑한다.
        function typeChunk() {
          if (requestId !== ctx.getActiveAnalysisRequestId()) return;
          if (charIdx < text.length) {
            const chunkStart = charIdx;
            const chunk = text.substr(charIdx, chunkSize);
            appendTypingChunk(chunk, chunkStart);
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

              // 5. 첫 답변 해시태그는 상승/중립/하락 상태별 색을 독립 적용한다.
              if (formatted.includes('#') && !formatted.includes('캘린더')) {
                let lines = formatted.split('\n\n');
                if (lines.length > 0) {
                  let lastLine = lines[lines.length - 1];
                  if (lastLine.includes('#')) {
                    let rawText = lastLine;
                    if (lastLine.includes('<span')) {
                      const tempDiv = document.createElement('div');
                      tempDiv.innerHTML = lastLine;
                      rawText = tempDiv.textContent || tempDiv.innerText || '';
                    }
                    const words = rawText.split(/\s+/);
                    const newWords = words.map((word) => {
                      if (!word.startsWith('#')) return word;
                      const color = firstAnswerTagColor(word);
                      return `<span class="font-bold" style="color: ${color};">${word}</span>`;
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
            // 실제 뉴스/공시는 window.GaemiGTPSourceLists.renderSourceLists()에서 한 번만 표시한다.
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

            if (secIdx === 0 && String(result?.price_snapshot?.quote_source || '').startsWith('kiwoom-')) {
              formatted = formatted.replace(/^([^\n]+)/, '<span data-kiwoom-intro>$1</span>');
              formatted = formatted.replace(
                /현재 주가는 \$[\d,.]+ 기록 중!|현재 키움 실시간 시세 수신 대기 중/,
                () => '<span data-kiwoom-current>' + (result.price_snapshot.current > 0
                  ? '현재 주가는 $' + Number(result.price_snapshot.current).toLocaleString('en-US',
                      { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' 기록 중!'
                  : '현재 키움 실시간 시세 수신 대기 중') + '</span>'
              );
            }
            if (secIdx === 0) formatted = stretch52WeekBar(formatted);
            pEl.innerHTML = formatted;
            if (secIdx === 0) startKiwoomQuoteTimer(stockName, result, requestId, pEl);

            // 첫 번째 분석 문장 아래에 뉴스·공시를 독립된 클릭형 목록으로 표시한다.
            // 본문 안의 📰/📌 텍스트 파싱은 더 이상 사용하지 않는다.
            if (secIdx === 0) {
              const actions = window.GaemiGTPFirstReplyActions.appendFirstReplyActions(pEl, pEl.innerText, 'first', stockName);
              appendNextAnalysisChoices(actions);
              return;
            }

            secIdx++;
            if (requestId === ctx.getActiveAnalysisRequestId()) {
              setTimeout(typeNextSection, 50);
            }
          }
        }
        typeChunk();
      }

      typeNextSection();
    }

    async function requestStock(stockName, marketSelection = null) {
      if (!stockName || !stockName.trim()) return;
      stockName = stockName.trim();
      stopKiwoomQuoteTimer();

      // 새 종목을 누르면 이전 분석 HTTP 요청을 즉시 끊어 브라우저가 오래된 응답을 기다리지 않게 한다.
      // 서버에서도 같은 종목의 중복 외부 호출은 백엔드 캐시/single-flight가 막는다.
      if (ctx.getAnalysisController()) {
        ctx.getAnalysisController().abort();
      }
      ctx.setAnalysisController(new AbortController());

      const requestId = ctx.nextAnalysisRequestId();
      ctx.setActiveStock(stockName);
      window.GaemiGTPActiveStock = ctx.getActiveStock();
      window.GaemiGTPWorkspaceShellState?.save?.();

      const session = ctx.beginChatSession(stockName, marketSelection);
      if (!session) return;
      // 새 종목 조회 중 이전 종목의 뉴스·공시를 공유 데이터로 노출하지 않는다.
      // 새 수집 없이 기존 결과 저장소의 스냅샷만 초기화한다.
      window.GaemiGTPAnalysisData?.set?.(stockName, {});
      const chatArea = document.getElementById('chatArea');
      ctx.appendChatMessage('user', stockName, 'stock', session.id);

      const loadingDiv = document.createElement('div');
      loadingDiv.className = 'analysis-loading-sequence';
      loadingDiv.innerHTML = `<div class="gtp-chat-copy font-semibold animate-pulse" aria-live="polite">시세를 조회중입니다</div>`;
      chatArea.appendChild(loadingDiv);

      const controller = ctx.getAnalysisController();
      const fetchPromise = window.GaemiGTPAnalysisAPI.fetchAnalysisFromBackend(stockName, controller.signal, session.marketSelection);
      ctx.setPendingAnalysis({ stock: stockName, promise: fetchPromise });
      const loadingDelayPromise = new Promise(resolve => setTimeout(resolve, 4000));
      const [result] = await Promise.all([fetchPromise, loadingDelayPromise]);
      if (ctx.getPendingAnalysis()?.promise === fetchPromise) ctx.setPendingAnalysis(null);
      if (requestId !== ctx.getActiveAnalysisRequestId() || result.aborted) {
        loadingDiv.remove();
        return;
      }
      loadingDiv.remove();
      const sections = result.sections || [];

      if (ctx.getAnalysisController() === controller) ctx.setAnalysisController(null);

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
      window.GaemiGTPApp?.linkRecentConversation?.('stock', stockName);

      // 채팅과 플러그인 위젯이 같은 분석 응답을 공유한다.
      // 위젯은 제목 문자열이 아니라 백엔드의 고정 section id를 사용한다.
      window.GaemiGTPAnalysisData?.set?.(stockName, result);

      // The backend has finished saving new issue briefs. Refresh only the
      // matching sidebar title from the same stored source, without recollection.
      if (Array.isArray(result.issue_briefs) && result.issue_briefs.length > 0) {
        window.dispatchEvent(new CustomEvent('gaemi:analysis-issues-ready', {
          detail: {
            name: session.marketSelection?.name || stockName,
            market: session.marketSelection?.market || null,
            symbol: session.marketSelection?.symbol || null
          }
        }));
      }

      chatArea.scrollTop = 0;
      if (requestId !== ctx.getActiveAnalysisRequestId() || ctx.getSession()?.id !== session.id) return;
      ctx.getSession().messages.push({
        id: ctx.nextChatMessageId(), role: 'assistant', kind: 'analysis',
        sections: sections.map(({ id, title, content }) => ({ id, title, content }))
      });
      window.GaemiGTPApp?.saveChatHistory?.();
      startTypewriterFlow(stockName, sections, result, requestId);
    }



    return { startTypewriterFlow, requestStock };
  }
  window.GaemiGTPCenterAnalysisFlow = { create, whyChoiceFromChange };
}());
