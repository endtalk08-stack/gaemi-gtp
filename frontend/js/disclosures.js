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
                const row = document.createElement('div');
                row.className = 'space-y-1 text-sm text-[#475569] dark:text-[#d4d4d8]';

                const titleEl = document.createElement('div');
                titleEl.dataset.typingText = item.title || '공시 제목 확인 필요';
                titleEl.textContent = '';
                row.appendChild(titleEl);

                const metaEl = document.createElement('div');
                metaEl.className = 'flex items-baseline justify-between gap-3 text-xs font-bold text-[#64748b] dark:text-[#a1a1aa]';
                const metaLeft = document.createElement('span');
                metaLeft.dataset.typingText = [item.date || '', item.time || '', item.source || '공시'].filter(Boolean).join(' · ');
                metaLeft.textContent = '';
                metaEl.appendChild(metaLeft);
                row.appendChild(metaEl);

                const keywords = Array.isArray(item.keywords) ? item.keywords.filter(Boolean) : [];
                const keywordText = keywords.map((keyword) => `#${String(keyword).replace(/^#/, '')}`).join(' ');

                const holdings = Array.isArray(item.executive_shareholdings) ? item.executive_shareholdings : [];
                holdings.forEach((detail) => {
                  const person = String(detail.repror || '').trim();
                  const position = String(detail.isu_exctv_ofcps || '').trim();
                  const currentShares = String(detail.sp_stock_lmp_cnt || '').trim();
                  const shareDelta = String(detail.sp_stock_lmp_irds_cnt || '').trim();
                  const currentRate = String(detail.sp_stock_lmp_rate || '').trim();

                  const holdingSummary = [
                    currentShares ? `${currentShares}주` : '',
                    shareDelta ? `${shareDelta}주` : '',
                    currentRate ? `${currentRate}%` : ''
                  ].filter(Boolean).join(' · ');
                  if (holdingSummary) {
                    const metaRight = document.createElement('span');
                    metaRight.dataset.typingText = holdingSummary;
                    metaRight.textContent = '';
                    metaEl.appendChild(metaRight);
                  }

                  const personLine = document.createElement('div');
                  personLine.className = 'flex items-baseline justify-between gap-3 text-xs font-bold text-[#64748b] dark:text-[#a1a1aa]';
                  const personLeft = document.createElement('span');
                  personLeft.dataset.typingText = [person, position].filter(Boolean).join(' · ');
                  personLeft.textContent = '';
                  personLine.appendChild(personLeft);
                  if (keywordText) {
                    const keywordEl = document.createElement('span');
                    keywordEl.className = 'analysis-hashtag font-semibold text-[#db2777] dark:text-[#e889aa]';
                    keywordEl.dataset.typingText = keywordText;
                    keywordEl.textContent = '';
                    personLine.appendChild(keywordEl);
                  }
                  row.appendChild(personLine);
                });

                if (String(item.form || '').toUpperCase() === '4') {
                  const transactions = Array.isArray(item.transactions) ? item.transactions : [];
                  let totalShares = 0;
                  let totalValue = 0;
                  transactions.forEach((transaction) => {
                    const shares = Number(String(transaction.shares || '').replaceAll(',', ''));
                    const price = Number(String(transaction.price || '').replaceAll(',', ''));
                    if (Number.isFinite(shares)) totalShares += shares;
                    if (Number.isFinite(shares) && Number.isFinite(price)) totalValue += shares * price;
                  });
                  const totalValueText = totalValue >= 1000000
                    ? `약 $${(totalValue / 1000000).toLocaleString('en-US', { maximumFractionDigits: 2 })}M`
                    : (totalValue > 0 ? `약 $${Math.round(totalValue).toLocaleString('en-US')}` : '');
                  const transactionSummary = [
                    totalShares > 0 ? `총 ${Math.round(totalShares).toLocaleString('en-US')}주` : '',
                    totalValueText
                  ].filter(Boolean).join(' · ');
                  if (transactionSummary) {
                    const metaRight = document.createElement('span');
                    metaRight.dataset.typingText = transactionSummary;
                    metaRight.textContent = '';
                    metaEl.appendChild(metaRight);
                  }

                  const personLine = document.createElement('div');
                  personLine.className = 'flex items-baseline justify-between gap-3 text-xs font-bold text-[#64748b] dark:text-[#a1a1aa]';
                  const personLeft = document.createElement('span');
                  personLeft.dataset.typingText = [item.person || '', item.officer_title || ''].filter(Boolean).join(' · ');
                  personLeft.textContent = '';
                  personLine.appendChild(personLeft);
                  if (keywordText) {
                    const keywordEl = document.createElement('span');
                    keywordEl.className = 'analysis-hashtag font-semibold text-[#db2777] dark:text-[#e889aa]';
                    keywordEl.dataset.typingText = keywordText;
                    keywordEl.textContent = '';
                    personLine.appendChild(keywordEl);
                  }
                  row.appendChild(personLine);
                } else if (!holdings.length && keywordText) {
                  const keywordLine = document.createElement('div');
                  keywordLine.className = 'analysis-hashtag text-xs font-semibold text-[#db2777] dark:text-[#e889aa]';
                  keywordLine.dataset.typingText = keywordText;
                  keywordLine.textContent = '';
                  row.appendChild(keywordLine);
                }

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
};
