// gaemiGTP - '왜 움직였나?' 흐름 전용
window.GaemiGTPWhyFlow = window.GaemiGTPWhyFlow || {};

window.GaemiGTPWhyFlow.appendWhy = async function ({
  mainContainer,
  requestId,
  getActiveAnalysisRequestId,
  result,
  choices,
  whyState,
  makeUserPrompt,
  getWhyEvidence,
  appendFollowupChoices,
  typeText,
  responseMessageClass,
  stockName
}) {
  
            if (mainContainer.querySelector('[data-why-flow]')) return;
            const prompt = makeUserPrompt(whyState.label, 'whyFlow');
            choices.insertAdjacentElement('afterend', prompt);
            choices.remove();
  
            const loading = document.createElement('div');
            loading.className = 'mt-5 space-y-2';
            prompt.insertAdjacentElement('afterend', loading);
            const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
            for (const message of ['뉴스를 확인합니다', '생각중', '내용을 정리중입니다']) {
              if (requestId !== getActiveAnalysisRequestId() || !mainContainer.isConnected) return;
              const line = document.createElement('p');
              line.className = `${responseMessageClass} font-semibold animate-pulse`;
              line.textContent = message;
              loading.appendChild(line);
              await wait(4000);
            }
            if (requestId !== getActiveAnalysisRequestId() || !mainContainer.isConnected) return;
            loading.remove();
  
            const evidence = getWhyEvidence();
            const allNewsItems = Array.isArray(result.news_items) ? result.news_items : [];
            const disclosures = (Array.isArray(result.disclosures) && result.disclosures.length
              ? result.disclosures
              : (Array.isArray(result.us_filings) ? result.us_filings : [])).slice(0, 3);
            const storyboard = Array.isArray(result.keyword_storyboard) ? result.keyword_storyboard : [];
            const block = document.createElement('section');
            block.className = 'mt-5 space-y-5 animate-fade';
            const signalTitle = document.createElement('p');
            signalTitle.className = responseMessageClass;
            const signalTitleText = evidence.signals.length || storyboard.length || disclosures.length ? '오늘 눈에 띄는 흐름 👀' : '오늘은 흐름 없음 ☁️';
            block.appendChild(signalTitle);
            // 타이핑이 실제 화면에서 보이도록 결과 블록을 먼저 붙인다.
            prompt.insertAdjacentElement('afterend', block);
            await typeText(signalTitle, signalTitleText);

            if (storyboard.length) {
              const storyboardList = document.createElement('div');
              storyboardList.className = 'space-y-2';
              const storyboardRows = [];
              storyboard.forEach((event) => {
                const row = document.createElement('div');
                row.className = 'flex items-baseline gap-3';
                const timeEl = document.createElement('span');
                timeEl.className = 'shrink-0 text-xs font-bold text-[#64748b] dark:text-[#a1a1aa]';
                const timeText = event.time || '';
                timeEl.textContent = '';
                const keywordEl = document.createElement('span');
                keywordEl.className = 'analysis-hashtag font-semibold';
                const keywordTones = event.keyword_tones && typeof event.keyword_tones === 'object' ? event.keyword_tones : {};
                const eventToneValues = Object.values(keywordTones);
                // 방향성이 명시되지 않은 키워드도 흐름 안에서는 같은 색 체계를 사용한다.
                // 같은 이벤트에 악재가 하나라도 있으면 파랑, 그 외에는 핑크를 기본으로 한다.
                const fallbackTone = eventToneValues.includes('negative') ? 'negative' : 'positive';
                const keywordParts = (Array.isArray(event.keywords) ? event.keywords : []).map((keyword) => {
                  const label = String(keyword).replace(/^#/, '');
                  const tone = keywordTones[keyword] || keywordTones[label] || fallbackTone;
                  const span = document.createElement('span');
                  span.className = tone === 'negative'
                    ? 'text-[#38BDF8]'
                    : 'text-[#FF8DA1]';
                  span.dataset.typingText = `#${label}`;
                  span.textContent = '';
                  return span;
                });
                keywordParts.forEach((part, index) => {
                  if (index) keywordEl.appendChild(document.createTextNode(' '));
                  keywordEl.appendChild(part);
                });
                row.appendChild(timeEl);
                row.appendChild(keywordEl);
                storyboardList.appendChild(row);
                storyboardRows.push({ timeEl, timeText, keywordParts });
              });
              block.appendChild(storyboardList);

              for (const { timeEl, timeText, keywordParts } of storyboardRows) {
                await typeText(timeEl, timeText);
                for (const part of keywordParts) {
                  await typeText(part, part.dataset.typingText || '');
                }
              }
            }
  
            const articles = await window.GaemiGTPNews.renderArticles({
              evidence: { ...evidence, articles: allNewsItems, matchedArticles: evidence.articles },
              block,
              responseMessageClass,
              openExternalLinkModal: window.GaemiGTPExternalLinkModal.openExternalLinkModal,
              typeText
            });
  
            if (!articles.length && !disclosures.length) {
              const empty = document.createElement('p');
              empty.className = `${responseMessageClass} whitespace-pre-line`;
              empty.textContent = '기사에서 딱히 잡히는 재료도 없고,\n오늘은 시장 흐름을 조금 더 지켜보자 ☕';
              block.appendChild(empty);
            }
  
            window.GaemiGTPRelatedStocks.renderRelatedStocks({
              articles,
              stockName,
              block,
              responseMessageClass
            });
  
            const actions = window.GaemiGTPFirstReplyActions.appendFirstReplyActions(block, `${prompt.innerText}\n${block.innerText}`, 'why', stockName);

            const followups = document.createElement('section');
            followups.dataset.whyFollowupChoices = 'true';
            followups.className = 'mt-6 space-y-2 animate-fade text-right';
            followups.innerHTML = `
              <p class="${responseMessageClass}"></p>
              <div class="flex flex-wrap items-center justify-end gap-x-3 gap-y-1.5">
                <button type="button" class="text-sm font-semibold text-[#3b82f6] transition hover:text-[#2563eb] dark:text-[#7aa2e3] dark:hover:text-[#9ab8ee]" data-why-followup="big-money"></button>
                <button type="button" class="text-sm font-semibold text-[#db2777] transition hover:opacity-80 dark:text-[#e889aa]" data-why-followup="disclosure"></button>
              </div>`;
            (actions || block).insertAdjacentElement('afterend', followups);
            await typeText(followups.querySelector('p'), '하나만 찍어');
            await typeText(followups.querySelector('[data-why-followup="big-money"]'), '#큰손은_뭐해?');
            await typeText(followups.querySelector('[data-why-followup="disclosure"]'), '#공시는_있어?');

            followups.addEventListener('click', async (event) => {
              const button = event.target.closest('[data-why-followup]');
              if (!button) return;
              if (button.dataset.whyFollowup === 'disclosure') {
                const disclosurePrompt = makeUserPrompt('공시는 있어?', 'disclosureFlow');
                followups.insertAdjacentElement('afterend', disclosurePrompt);
                followups.remove();

                const disclosureLoading = document.createElement('div');
                disclosureLoading.className = 'mt-5 space-y-2';
                disclosurePrompt.insertAdjacentElement('afterend', disclosureLoading);
                for (const message of ['뉴스를 확인합니다', '생각중', '내용을 정리중입니다']) {
                  if (requestId !== getActiveAnalysisRequestId() || !mainContainer.isConnected) return;
                  const line = document.createElement('p');
                  line.className = `${responseMessageClass} font-semibold animate-pulse`;
                  line.textContent = message;
                  disclosureLoading.appendChild(line);
                  await wait(4000);
                }
                disclosureLoading.remove();

                const disclosureBlock = document.createElement('section');
                disclosureBlock.className = 'mt-5 space-y-5 animate-fade';
                disclosurePrompt.insertAdjacentElement('afterend', disclosureBlock);
                await window.GaemiGTPDisclosures.renderDisclosures({
                  disclosures,
                  articles: [],
                  block: disclosureBlock,
                  responseMessageClass,
                  openExternalLinkModal: window.GaemiGTPExternalLinkModal.openExternalLinkModal,
                  typeText
                });
                if (!disclosures.length) {
                  const emptyDisclosure = document.createElement('p');
                  emptyDisclosure.className = responseMessageClass;
                  disclosureBlock.appendChild(emptyDisclosure);
                  await typeText(emptyDisclosure, '오늘 확인된 공시는 없어 ㅠㅠ');
                }
                const disclosureReplyText = `${disclosurePrompt.innerText}\n${disclosureBlock.innerText}`;
                const disclosureActions = window.GaemiGTPFirstReplyActions.appendFirstReplyActions(
                  disclosureBlock,
                  disclosureReplyText,
                  'disclosure',
                  stockName
                );

                const disclosureFollowups = document.createElement('section');
                disclosureFollowups.dataset.disclosureFollowupChoices = 'true';
                disclosureFollowups.className = 'mt-6 space-y-2 animate-fade text-right';
                disclosureFollowups.innerHTML = `
                  <p class="${responseMessageClass}"></p>
                  <div class="flex flex-wrap items-center justify-end gap-x-3 gap-y-1.5">
                    <button type="button" class="text-sm font-semibold text-[#3b82f6] transition hover:text-[#2563eb] dark:text-[#7aa2e3] dark:hover:text-[#9ab8ee]">#큰손은_뭐해</button>
                    <button type="button" class="text-sm font-semibold text-[#db2777] transition hover:opacity-80 dark:text-[#e889aa]">#오늘밤_무슨일_있어?</button>
                  </div>`;
                (disclosureActions || disclosureBlock).insertAdjacentElement('afterend', disclosureFollowups);
                await typeText(disclosureFollowups.querySelector('p'), '해시태그 하나만 클릭해');
                disclosureFollowups.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
              }
            });
            if (window.lucide) window.lucide.createIcons();
            block.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
};
