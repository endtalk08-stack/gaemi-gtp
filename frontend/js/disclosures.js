// gaemiGTP - 공시 표시 전용
window.GaemiGTPDisclosures = window.GaemiGTPDisclosures || {};

window.GaemiGTPDisclosures.renderDisclosures = async function ({
  disclosures,
  allDisclosures,
  articles,
  block,
  responseMessageClass,
  openExternalLinkModal,
  typeText
}) {
            const disclosureSection = document.createElement('section');
            disclosureSection.className = 'space-y-2';
            const disclosureTitle = Object.assign(document.createElement('p'), { className: responseMessageClass });
            disclosureSection.appendChild(disclosureTitle);
            block.appendChild(disclosureSection);
            if (typeof typeText === 'function') {
              await typeText(disclosureTitle, '오늘 공시는?');
            } else {
              disclosureTitle.textContent = '오늘 공시는?';
            }

            if (disclosures.length) {
              const disclosureRows = [];
              disclosures.forEach((item) => {
                const row = document.createElement('button');
                row.type = 'button';
                row.className = 'block w-full text-left text-sm text-[#475569] hover:text-[#0f172a] dark:text-[#d4d4d8] dark:hover:text-white';
                const keywords = Array.isArray(item.keywords) ? item.keywords.filter(Boolean) : [];
                const dateText = String(item.date || '').trim();
                const timeText = String(item.time || '').trim();
                const disclosureDateTime = [dateText, timeText].filter(Boolean).join(' ');
                if (disclosureDateTime || keywords.length) {
                  const metaEl = document.createElement('div');
                  metaEl.className = 'flex items-baseline gap-3 mb-1 flex-wrap';

                  if (disclosureDateTime) {
                    const dateTimeEl = document.createElement('span');
                    dateTimeEl.className = 'text-xs font-bold text-[#64748b] dark:text-[#a1a1aa]';
                    dateTimeEl.dataset.typingText = disclosureDateTime;
                    dateTimeEl.textContent = '';
                    metaEl.appendChild(dateTimeEl);
                  }

                  if (keywords.length) {
                    const keywordEl = document.createElement('span');
                    keywordEl.className = 'analysis-hashtag font-semibold text-[#db2777] dark:text-[#e889aa]';
                    keywordEl.dataset.typingText = keywords.map(keyword => `#${String(keyword).replace(/^#/, '')}`).join(' ');
                    keywordEl.textContent = '';
                    metaEl.appendChild(keywordEl);
                  }

                  row.appendChild(metaEl);
                }

                const titleEl = document.createElement('div');
                titleEl.className = 'mt-2';
                titleEl.dataset.typingText = item.title || '공시 제목 확인 필요';
                titleEl.textContent = '';
                row.appendChild(titleEl);

                const linkEl = document.createElement('div');
                linkEl.className = 'mt-2 text-xs font-medium text-[#64748b] dark:text-[#a1a1aa]';
                linkEl.dataset.typingText = '공시 원문 보기';
                linkEl.textContent = '';
                row.appendChild(linkEl);

                row.addEventListener('click', () => openExternalLinkModal(item));
                disclosureSection.appendChild(row);
                disclosureRows.push(row);
              });
              if (typeof typeText === 'function') {
                for (const row of disclosureRows) {
                  const parts = row.querySelectorAll('[data-typing-text]');
                  for (const part of parts) {
                    await typeText(part, part.dataset.typingText || '');
                  }
                }
              } else {
                disclosureRows.forEach((row) => {
                  row.querySelectorAll('[data-typing-text]').forEach((part) => {
                    part.textContent = part.dataset.typingText || '';
                  });
                });
              }
            }

            const monthItems = Array.isArray(allDisclosures) ? allDisclosures : disclosures;
            if (monthItems.length) {
              const more = document.createElement('button');
              more.type = 'button';
              more.className = 'news-source-chip';
              more.style.marginTop = '12px';
              more.setAttribute('aria-label', '더보기');
              const label = document.createElement('span');
              label.className = 'news-source-chip__label';
              label.textContent = '더보기';
              more.appendChild(label);
              more.addEventListener('click', () => {
                window.GaemiGTPRightPanelTabs?.showRelatedDisclosures?.(monthItems);
              });
              block.appendChild(more);
            }
};