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
  stockName,
  inline = false
}) {
  
            const existing = mainContainer.querySelector('[data-inline-ai-issues]');
            if (existing) {
              if (!inline) existing.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
              return;
            }
            if (mainContainer.querySelector('[data-why-flow]')) return;
            const prompt = inline
              ? document.createElement('div')
              : makeUserPrompt(whyState.label, 'whyFlow');
            prompt.classList.remove('animate-fade');
            if (inline) {
              choices.insertAdjacentElement('beforebegin', prompt);
            } else {
              choices.insertAdjacentElement('afterend', prompt);
              choices.remove();
            }

            const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
            const isActive = () => requestId === getActiveAnalysisRequestId() && mainContainer.isConnected;
            if (!inline) {
              const loading = document.createElement('div');
              loading.className = 'mt-5 space-y-2';
              prompt.insertAdjacentElement('afterend', loading);
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
            // 미국 중앙 이슈는 오른쪽 뉴스와 동일한 기사 목록/정렬/중복 제거를 사용한다.
            // 각 기사의 기존 storyboard_keywords를 그대로 표시하며 재선별하지 않는다.
            const useUsPanelNews = result.price_snapshot?.currency === 'USD';
            const storyboard = useUsPanelNews
              ? (window.GaemiGTPRightPanelTabs?.getSelectedNews?.() || [])
              : (Array.isArray(result.issue_briefs) ? result.issue_briefs : []);
            const typeWhyText = (element, text) => typeText(element, text, { chunkSize: 1 });
            const block = document.createElement('section');
            block.className = 'mt-5 space-y-5';
            if (inline) {
              block.dataset.inlineAiIssues = 'true';
              const reason = result.price_reason;
              if (reason && reason.headline && reason.summary) {
                const reasonTitle = document.createElement('p');
                reasonTitle.className = `${responseMessageClass} font-semibold`;
                reasonTitle.textContent = String(reason.headline);
                const reasonText = document.createElement('p');
                reasonText.className = `${responseMessageClass} whitespace-pre-line`;
                reasonText.textContent = String(reason.summary);
                block.append(reasonTitle, reasonText);
              }
            }
            // Keep the existing news section visible even when no fresh,
            // cited issue is available; never fabricate an issue.
            const signalTitle = document.createElement('p');
            signalTitle.className = responseMessageClass;
            const signalTitleText = inline
              ? '오늘 눈에 띄는 흐름 👀'
              : evidence.signals.length || storyboard.length || disclosures.length
                ? '오늘 눈에 띄는 흐름 👀' : '눈에 띄는 흐름 없음 ☁️';
            block.appendChild(signalTitle);
            prompt.insertAdjacentElement('afterend', block);
            if (inline) prompt.remove();
            await typeWhyText(signalTitle, signalTitleText);

            if (storyboard.length) {
              const storyboardList = document.createElement('div');
              storyboardList.className = 'space-y-7';
              const storyboardRows = [];
              storyboard.forEach((event) => {
                const article = document.createElement('article');
                article.className = 'space-y-2';

                const newsUrl = useUsPanelNews ? String(event.url || event.link || '').trim() : '';
                const headline = document.createElement(newsUrl ? 'button' : 'p');
                headline.className = `${responseMessageClass} font-semibold${newsUrl ? ' text-left block hover:underline' : ''}`;
                if (newsUrl) {
                  headline.type = 'button';
                  headline.addEventListener('click', () => window.GaemiGTPExternalLinkModal?.openExternalLinkModal?.(event));
                }
                const timeEl = document.createElement('span');
                timeEl.className = 'mr-2 text-xs font-bold text-[#64748b] dark:text-[#a1a1aa]';
                const titleEl = document.createElement('span');
                if (useUsPanelNews) headline.append(titleEl);
                else headline.append(timeEl, titleEl);

                const descriptionEl = document.createElement('p');
                descriptionEl.className = `${responseMessageClass} whitespace-pre-line`;

                const keywordEl = document.createElement('p');
                keywordEl.className = 'analysis-hashtag gtp-chat-copy font-semibold';
                const rawKeywords = useUsPanelNews ? event.storyboard_keywords : event.tags;
                const keywords = (Array.isArray(rawKeywords) ? rawKeywords : [])
                  .map((keyword) => String(keyword || '').trim().replace(/^#/, ''))
                  .filter(Boolean)
                  .slice(0, 3);
                const keywordParts = keywords.map((label) => {
                  const keyword = document.createElement('span');
                  keyword.className = 'text-[#94a3b8] dark:text-[#d4d4d8]';
                  keyword.dataset.typingText = label;
                  return keyword;
                });
                keywordParts.forEach((part, index) => {
                  if (index) keywordEl.appendChild(document.createTextNode('  '));
                  keywordEl.appendChild(part);
                });

                const stockNames = [...new Set((!useUsPanelNews && Array.isArray(event.stock_names) ? event.stock_names : [])
                  .map((name) => String(name || '').trim())
                  .filter(Boolean))].slice(0, 3);
                const finiteOrNull = (value) => {
                  if (value === null || value === undefined || value === '') return null;
                  const number = Number(value);
                  return Number.isFinite(number) ? number : null;
                };
                const reactions = (Array.isArray(event.stock_reactions) ? event.stock_reactions : [])
                  .map((item) => ({
                    name: String(item?.name || '').trim(),
                    lowPct: finiteOrNull(item?.low_pct),
                    highPct: finiteOrNull(item?.high_pct),
                  }))
                  .filter((item) => item.name && item.lowPct !== null && item.highPct !== null)
                  .slice(0, 3);
                const reactionByName = new Map(reactions.map((item) => [item.name, item]));
                const displayNames = stockNames.length ? stockNames : reactions.map((item) => item.name);
                const direction = (value) => value > 0 ? 'up' : value < 0 ? 'down' : 'flat';
                const formatPct = (value) => `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
                let reactionsEl = null;
                if (displayNames.length) {
                  reactionsEl = document.createElement('div');
                  reactionsEl.className = 'news-reaction';
                  reactionsEl.hidden = true;

                  const reactionTitle = document.createElement('p');
                  reactionTitle.className = 'news-reaction__title';
                  reactionTitle.textContent = '관련 종목 · 이슈 이후 움직임';
                  reactionsEl.appendChild(reactionTitle);

                  displayNames.forEach((name) => {
                    const item = reactionByName.get(name);
                    const row = document.createElement('div');
                    row.className = item ? 'news-reaction__row' : 'news-reaction__row news-reaction__row--name-only';

                    const nameEl = document.createElement('span');
                    nameEl.className = 'news-reaction__name';
                    nameEl.textContent = name;

                    if (!item) {
                      row.appendChild(nameEl);
                      reactionsEl.appendChild(row);
                      return;
                    }

                    const lowEl = document.createElement('span');
                    lowEl.className = `news-reaction__value news-reaction__value--${direction(item.lowPct)}`;
                    lowEl.textContent = `${formatPct(item.lowPct)}${item.lowPct < 0 ? ' ↘' : item.lowPct > 0 ? ' ↗' : ''}`;

                    const barEl = document.createElement('span');
                    barEl.className = 'news-reaction__bar';

                    const highEl = document.createElement('span');
                    highEl.className = `news-reaction__value news-reaction__value--${direction(item.highPct)}`;
                    highEl.textContent = `${formatPct(item.highPct)}${item.highPct > 0 ? ' ↗' : item.highPct < 0 ? ' ↘' : ''}`;

                    row.append(nameEl, lowEl, barEl, highEl);
                    reactionsEl.appendChild(row);
                  });
                }

                const articleSummary = useUsPanelNews
                  ? String(event.description || event.summary || '기사 내용이 없습니다.').trim()
                  : String(event.summary || '').trim();
                article.append(headline);
                if (articleSummary) article.append(descriptionEl);
                if (useUsPanelNews) {
                  const sourceEl = document.createElement('p');
                  sourceEl.className = 'text-xs text-[#64748b] dark:text-[#a1a1aa]';
                  sourceEl.textContent = [event.source || '뉴스', event.storyboard_date, event.storyboard_time]
                    .filter(Boolean).join(' · ');
                  article.append(sourceEl);
                }
                if (keywordParts.length) article.append(keywordEl);
                if (reactionsEl) article.append(reactionsEl);
                storyboardList.appendChild(article);
                storyboardRows.push({
                  timeEl,
                  timeText: useUsPanelNews ? '' : (event.time || ''),
                  titleEl,
                  titleText: String((useUsPanelNews ? event.title : event.headline) || '').trim(),
                  descriptionEl,
                  descriptionText: articleSummary,
                  keywordParts,
                  reactionsEl,
                });
              });
              block.appendChild(storyboardList);

              for (const row of storyboardRows) {
                if (useUsPanelNews) {
                  row.titleEl.textContent = row.titleText;
                  row.descriptionEl.textContent = row.descriptionText;
                  for (const part of row.keywordParts) part.textContent = part.dataset.typingText || '';
                  continue;
                }
                await typeWhyText(row.timeEl, row.timeText);
                await typeWhyText(row.titleEl, row.titleText);
                if (row.descriptionText) await typeWhyText(row.descriptionEl, row.descriptionText);
                for (const part of row.keywordParts) {
                  await typeWhyText(part, part.dataset.typingText || '');
                }
                if (row.reactionsEl) {
                  row.reactionsEl.hidden = false;
                }
              }
            }
  
            // The initial answer already has its own action buttons and choices.
            if (inline) return;
            const actions = window.GaemiGTPFirstReplyActions.appendFirstReplyActions(block, `${prompt.innerText}\n${block.innerText}`, 'why', stockName);

            const followups = document.createElement('section');
            followups.dataset.whyFollowupChoices = 'true';
            followups.className = 'mt-6 space-y-2 text-right';
            followups.innerHTML = `
              <p class="${responseMessageClass}"></p>
              <div class="flex flex-wrap items-center justify-end gap-x-3 gap-y-1.5">
                <button type="button" class="text-sm font-semibold text-[#db2777] transition hover:opacity-80 dark:text-[#e889aa]" data-why-followup="disclosure"></button>
              </div>`;
            (actions || block).insertAdjacentElement('afterend', followups);
            await typeWhyText(followups.querySelector('p'), '하나만 찍어');
            await typeWhyText(followups.querySelector('[data-why-followup="disclosure"]'), '#공시는_있어?');

            let disclosureFlowStarted = false;
            followups.addEventListener('click', async (event) => {
              const button = event.target.closest('[data-why-followup]');
              if (!button) return;
              if (button.dataset.whyFollowup === 'disclosure') {
                if (disclosureFlowStarted) return;
                disclosureFlowStarted = true;
                const disclosurePrompt = makeUserPrompt('공시는 있어?', 'disclosureFlow');
                disclosurePrompt.classList.remove('animate-fade');
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
                disclosureBlock.className = 'mt-5 space-y-5';
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
                disclosureFollowups.className = 'mt-6 space-y-2 text-right';
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
