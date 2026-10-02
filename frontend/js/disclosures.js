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
                row.className = 'space-y-1 text-[#475569] dark:text-[#d4d4d8]';
                row.style.fontSize = window.matchMedia('(min-width: 640px)').matches ? '1rem' : '13px';

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

                const majorChange = item.major_shareholder_change && typeof item.major_shareholder_change === 'object'
                  ? item.major_shareholder_change : null;
                if (majorChange) {
                  const shareDelta = Number(majorChange.share_delta);
                  const currentRate = Number(majorChange.current_rate);
                  const rateDelta = Number(majorChange.rate_delta);
                  const summaryRight = document.createElement('span');
                  summaryRight.dataset.typingText = [
                    Number.isFinite(shareDelta) ? `총 ${shareDelta > 0 ? '+' : ''}${Math.round(shareDelta).toLocaleString('ko-KR')}주` : '',
                    Number.isFinite(currentRate) ? `지분율 ${currentRate.toFixed(2)}%` : '',
                    Number.isFinite(rateDelta) && rateDelta !== 0 ? `(${rateDelta > 0 ? '+' : ''}${rateDelta.toFixed(2)}%p)` : (Number.isFinite(currentRate) ? '유지' : '')
                  ].filter(Boolean).join(' · ');
                  summaryRight.textContent = '';
                  if (summaryRight.dataset.typingText) metaEl.appendChild(summaryRight);

                  const detailChanges = Array.isArray(majorChange.detail_changes) ? majorChange.detail_changes : [];
                  detailChanges.forEach((detail) => {
                    const detailLine = document.createElement('div');
                    detailLine.className = 'flex items-baseline justify-between gap-3 text-xs font-bold text-[#64748b] dark:text-[#a1a1aa]';
                    const detailLeft = document.createElement('span');
                    detailLeft.dataset.typingText = [detail.name || '', detail.relation || '', detail.reason || ''].filter(Boolean).join(' · ');
                    detailLeft.textContent = '';
                    detailLine.appendChild(detailLeft);
                    const delta = Number(detail.share_delta);
                    if (Number.isFinite(delta)) {
                      const detailRight = document.createElement('span');
                      detailRight.dataset.typingText = `${delta > 0 ? '+' : ''}${Math.round(delta).toLocaleString('ko-KR')}주`;
                      detailRight.textContent = '';
                      detailLine.appendChild(detailRight);
                    }
                    row.appendChild(detailLine);
                  });
                }

                if (String(item.form || '').toUpperCase() === '8-K') {
                  const keyPoints = Array.isArray(item.key_points_ko) ? item.key_points_ko.filter(Boolean).slice(0, 3) : [];
                  keyPoints.forEach((point) => {
                    const parts = String(point).split(' · ').map((part) => part.trim()).filter(Boolean);
                    const pointLine = document.createElement('div');
                    pointLine.className = 'flex items-baseline justify-between gap-3 font-bold text-[#64748b] dark:text-[#a1a1aa]';
                    pointLine.style.fontSize = window.matchMedia('(min-width: 640px)').matches ? '1rem' : '13px';

                    const pointLeft = document.createElement('span');
                    pointLeft.dataset.typingText = parts[0] || '';
                    pointLeft.textContent = '';
                    pointLine.appendChild(pointLeft);

                    if (parts.length > 1) {
                      const pointRight = document.createElement('span');
                      pointRight.className = 'text-right';
                      pointRight.dataset.typingText = parts.slice(1).join(' · ');
                      pointRight.textContent = '';
                      pointLine.appendChild(pointRight);
                    }

                    row.appendChild(pointLine);
                  });
                }

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
                  if (String(item.form || '').toUpperCase() === '8-K') {
                    keywordLine.style.width = '100%';
                    keywordLine.style.textAlign = 'right';
                  }
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
