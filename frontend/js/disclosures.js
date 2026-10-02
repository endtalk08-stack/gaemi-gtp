// gaemiGTP - 공시 표시 전용
window.GaemiGTPDisclosures = window.GaemiGTPDisclosures || {};

window.GaemiGTPDisclosures.renderDisclosures = async function ({
  disclosures,
  articles,
  block,
  responseMessageClass,
  openExternalLinkModal,
  typeText
}) {
            if (disclosures.length) {
              const disclosureSection = document.createElement('section');
              disclosureSection.className = 'space-y-2';
              const disclosureTitle = Object.assign(document.createElement('p'), { className: responseMessageClass });
              disclosureSection.appendChild(disclosureTitle);
              block.appendChild(disclosureSection);
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
                await typeText(disclosureTitle, '관련 공시도 확인했어 📄');
                for (const row of disclosureRows) {
                  const parts = row.querySelectorAll('[data-typing-text]');
                  for (const part of parts) {
                    await typeText(part, part.dataset.typingText || '');
                  }
                }
              } else {
                disclosureTitle.textContent = '관련 공시도 확인했어 📄';
                disclosureRows.forEach((row) => {
                  row.querySelectorAll('[data-typing-text]').forEach((part) => {
                    part.textContent = part.dataset.typingText || '';
                  });
                });
              }
            }
};