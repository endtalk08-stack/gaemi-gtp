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
            const isActive = () => requestId === getActiveAnalysisRequestId() && mainContainer.isConnected;
            const loadingLine = document.createElement('p');
            loadingLine.className = `${responseMessageClass} font-semibold animate-pulse`;
            loadingLine.textContent = '생각중';
            loading.appendChild(loadingLine);

            try {
              await wait(5000);
              if (!isActive()) return;
            } finally {
              loading.remove();
            }
  
            const evidence = getWhyEvidence();
            const allNewsItems = Array.isArray(result.paired_news_items) ? result.paired_news_items : [];
            const allDisclosures = (Array.isArray(result.disclosures) && result.disclosures.length
              ? result.disclosures
              : (Array.isArray(result.us_filings) ? result.us_filings : []));
            const getTodayParts = (timeZone) => {
              const parts = new Intl.DateTimeFormat('en-CA', {
                timeZone,
                year: 'numeric',
                month: 'numeric',
                day: 'numeric'
              }).formatToParts(new Date());
              const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
              return {
                year: Number(values.year),
                month: Number(values.month),
                day: Number(values.day)
              };
            };
            const disclosures = allDisclosures.filter((item) => {
              const dateText = String(item?.date || '').trim();
              const match = dateText.match(/^(?:(\d{4})[-/.])?(\d{1,2})[-/.](\d{1,2})/);
              if (!match) return false;
              const isSec = String(item?.source || '').toUpperCase() === 'SEC'
                || String(item?.time_zone || '').toUpperCase() === 'ET';
              const today = getTodayParts(isSec ? 'America/New_York' : 'Asia/Seoul');
              const year = match[1] ? Number(match[1]) : today.year;
              return year === today.year
                && Number(match[2]) === today.month
                && Number(match[3]) === today.day;
            });
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
                keywordEl.className = 'analysis-hashtag gtp-chat-copy font-semibold';
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
                const stockEntitySet = new Set(
                  (Array.isArray(event.stock_entities) ? event.stock_entities : [])
                    .map((name) => String(name || '').trim())
                    .filter(Boolean)
                );
                const groundedLabels = (Array.isArray(event.grounded_tags) ? event.grounded_tags : [])
                  .map((tag) => String(tag || '').trim().replace(/^#/, ''))
                  .filter(Boolean);
                const makeTagParts = (labels, inheritEventTone = false) => labels.map((label) => {
                  const span = document.createElement('span');
                  span.className = inheritEventTone
                    ? (fallbackTone === 'negative' ? 'gtp-chat-copy font-medium text-[#38BDF8]' : 'gtp-chat-copy font-medium text-[#FF8DA1]')
                    : 'gtp-chat-copy font-medium';
                  span.dataset.typingText = '#' + label;
                  span.textContent = '';
                  return span;
                });
                const stockParts = makeTagParts(groundedLabels.filter((label) => stockEntitySet.has(label)));
                const infoParts = makeTagParts(groundedLabels.filter((label) => !stockEntitySet.has(label)), true);
                const detailsEl = document.createElement('div');
                detailsEl.className = 'mt-0.5 space-y-0.5';
                const appendTagLine = (parts) => {
                  if (!parts.length) return;
                  const line = document.createElement('div');
                  line.className = 'gtp-chat-copy font-medium';
                  parts.forEach((part, index) => {
                    if (index) line.appendChild(document.createTextNode('  '));
                    line.appendChild(part);
                  });
                  detailsEl.appendChild(line);
                };
                appendTagLine(infoParts);
                appendTagLine(stockParts);
                const contentEl = document.createElement('div');
                contentEl.appendChild(keywordEl);
                contentEl.appendChild(detailsEl);
                row.appendChild(timeEl);
                row.appendChild(contentEl);
                storyboardList.appendChild(row);
                storyboardRows.push({ timeEl, timeText, keywordParts, stockParts, infoParts });
              });
              block.appendChild(storyboardList);

              for (const { timeEl, timeText, keywordParts, stockParts, infoParts } of storyboardRows) {
                await typeText(timeEl, timeText);
                for (const part of keywordParts) {
                  await typeText(part, part.dataset.typingText || '');
                }
                for (const part of infoParts) {
                  await typeText(part, part.dataset.typingText || '');
                }
                for (const part of stockParts) {
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
                <button type="button" class="text-sm font-semibold text-[#db2777] transition hover:opacity-80 dark:text-[#e889aa]" data-why-followup="disclosure"></button>
              </div>`;
            (actions || block).insertAdjacentElement('afterend', followups);
            await typeText(followups.querySelector('p'), '하나만 찍어');
            await typeText(followups.querySelector('[data-why-followup="disclosure"]'), '#공시는_있어?');

            let disclosureFlowStarted = false;
            followups.addEventListener('click', async (event) => {
              const button = event.target.closest('[data-why-followup]');
              if (!button) return;
              if (button.dataset.whyFollowup === 'disclosure') {
                if (disclosureFlowStarted) return;
                disclosureFlowStarted = true;
                const disclosurePrompt = makeUserPrompt('공시는 있어?', 'disclosureFlow');
                followups.insertAdjacentElement('afterend', disclosurePrompt);
                followups.remove();

                const disclosureLoading = document.createElement('div');
                disclosureLoading.className = 'mt-5 space-y-2';
                disclosurePrompt.insertAdjacentElement('afterend', disclosureLoading);
                const disclosureLoadingLine = document.createElement('p');
                disclosureLoadingLine.className = `${responseMessageClass} font-semibold animate-pulse`;
                disclosureLoading.appendChild(disclosureLoadingLine);

                try {
                  for (const message of ['전자 공시 뒤지고 있습니다', '돋보기 가동중 🔍']) {
                    if (!isActive()) return;
                    disclosureLoadingLine.textContent = message;
                    await wait(4000);
                  }
                  if (!isActive()) return;
                } finally {
                  disclosureLoading.remove();
                }

                const disclosureBlock = document.createElement('section');
                disclosureBlock.className = 'mt-5 space-y-5 animate-fade';
                disclosurePrompt.insertAdjacentElement('afterend', disclosureBlock);
                await window.GaemiGTPDisclosures.renderDisclosures({
                  disclosures,
                  allDisclosures,
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
                  await typeText(emptyDisclosure, '꽝이야');
                  const noDisclosure = document.createElement('p');
                  noDisclosure.className = responseMessageClass;
                  disclosureBlock.appendChild(noDisclosure);
                  await typeText(noDisclosure, '없어');
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
                    <button type="button" class="text-sm font-semibold text-[#db2777] transition hover:opacity-80 dark:text-[#e889aa]">#오늘밤_무슨일_있어?</button>
                  </div>`;
                (disclosureActions || disclosureBlock).insertAdjacentElement('afterend', disclosureFollowups);
                await typeText(disclosureFollowups.querySelector('p'), '해시태그 하나만 클릭해');
                disclosureFollowups.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
              }
            });
            if (window.lucide) window.lucide.createIcons();
            followups.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
};
