// gaemiGTP - 공시 표시 전용
window.GaemiGTPDisclosures = window.GaemiGTPDisclosures || {};

window.GaemiGTPDisclosures.hydrateDartDetails = async function (items, limit = null) {
  const candidates = (Array.isArray(items) ? items : [])
    .filter((item) => String(item?.source || '').toUpperCase() === 'DART' && item?.receipt_no && item?.stock_code);
  const targets = Number.isFinite(limit) ? candidates.slice(0, Math.max(0, limit)) : candidates;
  if (!targets.length) return items;

  // Bound concurrent detail requests to avoid flooding the DART detail endpoint.
  // Keep all selected disclosures eligible; only change request concurrency.
  const concurrency = Math.min(2, targets.length);
  let nextIndex = 0;
  await Promise.all(Array.from({ length: concurrency }, async () => {
    while (nextIndex < targets.length) {
      const item = targets[nextIndex++];
      try {
        const params = new URLSearchParams({
          stock_code: String(item.stock_code || ''),
          receipt_no: String(item.receipt_no || ''),
          report: String(item.report || item.title || '')
        });
        const response = await fetch(`/disclosures/dart/detail?${params.toString()}`);
        if (!response.ok) continue;
        const payload = await response.json();
        const detail = payload && payload.ok && payload.detail ? payload.detail : null;
        if (!detail) continue;
        item.detail_fields = Array.isArray(detail.detail_fields) ? detail.detail_fields : [];
        item.executive_shareholdings = Array.isArray(detail.executive_shareholdings)
          ? detail.executive_shareholdings : [];
        item.major_shareholder_change = detail.major_shareholder_change || {};
        item.earnings_detail = detail.earnings_detail || {};
        item.supply_contract_detail = detail.supply_contract_detail || {};
        item.financing_detail = detail.financing_detail || {};
        item.treasury_stock_detail = detail.treasury_stock_detail || {};
        item.dividend_detail = detail.dividend_detail || {};
        item.corporate_action_detail = detail.corporate_action_detail || {};
        item.shareholding_change = detail.shareholding_change || item.shareholding_change || '';
        if (detail.shareholding_delta !== null && detail.shareholding_delta !== undefined) {
          item.shareholding_delta = detail.shareholding_delta;
        }
      } catch (error) {
        console.warn('[국내 공시 상세] 조회 실패:', error);
      }
    }
  }));
  return items;
};


window.GaemiGTPDisclosures.hydrateMissingSecDetails = async function (rows, isCurrent) {
  // Only fill empty Form 144/10-Q/10-K details in existing right-panel rows.
  // No new card, list fetch, storage or central-chat SEC wiring.
  if (!Array.isArray(rows) || !rows.length) return;
  let next = 0;
  const apiBase = window.location.hostname.endsWith('github.io')
    ? 'https://gaemi-gtp.onrender.com' : window.location.origin;
  await Promise.all(Array.from({ length: Math.min(2, rows.length) }, async () => {
    while (next < rows.length) {
      if (!isCurrent()) return;
      const { item, target } = rows[next++];
      if (!item?.link || !target) continue;
      try {
        const url = apiBase + '/disclosures/sec/detail?' +
          new URLSearchParams({ url: item.link }).toString();
        const response = await fetch(url);
        if (!response.ok) continue;
        const payload = await response.json();
        const detail = payload?.ok ? payload.detail : null;
        if (!detail || !isCurrent() || !target.isConnected) continue;
        const texts = [];
        (Array.isArray(detail.fields) ? detail.fields : []).slice(0, 12).forEach(field => {
          const label = String(field.label || '').trim();
          const value = String(field.value || '').trim();
          if (label && value) texts.push(label + ' · ' + value);
        });
        (Array.isArray(detail.metrics) ? detail.metrics : []).slice(0, 4).forEach(metric => {
          const value = Number(metric.value);
          if (!Number.isFinite(value)) return;
          const amount = '
  disclosures,
  allDisclosures,
  articles,
  block,
  responseMessageClass,
  openExternalLinkModal,
  typeText
}) {
            const domesticItems = (Array.isArray(disclosures) ? disclosures : []).filter(
              (item) => String(item?.source || '').toUpperCase() === 'DART'
            );
            // Only the central domestic disclosure uses the compact card. The right panel
            // continues rendering its complete independent list.
            const centralDomestic = domesticItems.length > 0;
            const centralCard = Array.isArray(disclosures) && disclosures.length > 0;
            const centralItems = centralCard ? disclosures.slice(0, 1) : disclosures;
            const disclosureSection = document.createElement('section');
            disclosureSection.className = 'space-y-2';
            if (centralCard) {
              disclosureSection.style.cssText = [
                'border:1px solid var(--gtp-border-strong, #3f3f46)',
                'border-radius:18px',
                'padding:18px',
                'display:flex',
                'flex-direction:column',
                'gap:14px',
                'font-family:Pretendard,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif',
                'color:var(--gtp-text, #e4e4e7)'
              ].join(';');
            }
            const disclosureTitle = Object.assign(document.createElement('p'), { className: responseMessageClass });
            disclosureSection.appendChild(disclosureTitle);
            block.appendChild(disclosureSection);
            if (typeof typeText === 'function') {
              await typeText(disclosureTitle, centralCard ? '오늘의 공식 공시' : '오늘 공시는?');
            } else {
              disclosureTitle.textContent = centralCard ? '오늘의 공식 공시' : '오늘 공시는?';
            }

            if (centralItems.length) {
              await window.GaemiGTPDisclosures.hydrateDartDetails(centralItems);

              const disclosureRows = [];
              centralItems.forEach((item) => {
                const row = document.createElement('div');
                row.className = 'space-y-1 text-[#475569] dark:text-[#d4d4d8]';
                row.style.fontSize = window.matchMedia('(min-width: 640px)').matches ? '1rem' : '14px';
                if (centralCard) row.style.cssText += ';display:flex;flex-direction:column;gap:10px';

                const titleEl = document.createElement('div');
                titleEl.dataset.typingText = item.title || '공시 제목 확인 필요';
                titleEl.textContent = '';
                row.appendChild(titleEl);
                if (centralCard) {
                  titleEl.style.cssText = 'font-size:var(--gtp-type-title,14px);font-weight:650;line-height:1.55;color:var(--gtp-text,#e4e4e7)';
                  const topMeta = document.createElement('span');
                  topMeta.style.cssText = 'font-size:var(--gtp-type-meta,12px);font-weight:500;color:var(--gtp-muted,#a1a1aa);white-space:nowrap;text-align:right';
                  topMeta.dataset.typingText = [item.source || (centralDomestic ? 'DART' : 'SEC'), item.date || '', item.time || ''].filter(Boolean).join(' · ');
                  topMeta.textContent = '';
                  const cardHeader = document.createElement('div');
                  cardHeader.style.cssText = 'display:flex;align-items:flex-start;justify-content:space-between;gap:10px';
                  disclosureSection.insertBefore(cardHeader, disclosureTitle);
                  cardHeader.append(disclosureTitle, topMeta);
                  disclosureTitle.style.cssText = 'font-size:var(--gtp-type-title,14px);font-weight:650;color:var(--gtp-text,#e4e4e7);margin:0';
                }

                const metaEl = document.createElement('div');
                metaEl.className = 'flex items-baseline justify-between gap-3 text-xs font-bold text-[#64748b] dark:text-[#a1a1aa]';
                const metaLeft = document.createElement('span');
                metaLeft.dataset.typingText = [item.date || '', item.time || '', item.source || '공시'].filter(Boolean).join(' · ');
                metaLeft.textContent = '';
                metaEl.appendChild(metaLeft);
                if (!centralCard) row.appendChild(metaEl);

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

                const actionDetail = item.corporate_action_detail && typeof item.corporate_action_detail === 'object'
                  ? item.corporate_action_detail : null;
                if (actionDetail && Object.keys(actionDetail).length) {
                  const amount = Number(actionDetail.amount);
                  const equityRatio = Number(actionDetail.equity_ratio);
                  const shares = Number(actionDetail.shares);
                  const ratio = Number(actionDetail.ratio);
                  [
                    ['구분', String(actionDetail.kind || '')],
                    ['상대회사', String(actionDetail.counterparty || '')],
                    ['거래금액', Number.isFinite(amount) ? Math.round(amount).toLocaleString('ko-KR') : ''],
                    ['지분율', Number.isFinite(equityRatio) ? `${equityRatio.toFixed(2)}%` : ''],
                    ['주식수', Number.isFinite(shares) ? `${Math.round(shares).toLocaleString('ko-KR')}주` : ''],
                    ['자기자본 대비', Number.isFinite(ratio) ? `${ratio.toFixed(2)}%` : ''],
                    ['목적', String(actionDetail.purpose || '')]
                  ].filter(([, value]) => value).slice(0, 4).forEach(([label, value]) => {
                    const detailLine = document.createElement('div');
                    detailLine.className = 'flex items-baseline justify-between gap-3 text-xs font-bold text-[#64748b] dark:text-[#a1a1aa]';
                    const left = document.createElement('span');
                    left.dataset.typingText = label;
                    left.textContent = '';
                    const right = document.createElement('span');
                    right.dataset.typingText = value;
                    right.textContent = '';
                    detailLine.append(left, right);
                    row.appendChild(detailLine);
                  });
                }

                const dividendDetail = item.dividend_detail && typeof item.dividend_detail === 'object'
                  ? item.dividend_detail : null;
                if (dividendDetail && Object.keys(dividendDetail).length) {
                  const perShare = Number(dividendDetail.dividend_per_share);
                  const rate = Number(dividendDetail.dividend_rate);
                  const total = Number(dividendDetail.total_amount);
                  [
                    ['주당배당금', Number.isFinite(perShare) ? `${Math.round(perShare).toLocaleString('ko-KR')}원` : ''],
                    ['시가배당률', Number.isFinite(rate) ? `${rate.toFixed(2)}%` : ''],
                    ['배당금총액', Number.isFinite(total) ? Math.round(total).toLocaleString('ko-KR') : ''],
                    ['배당기준일', String(dividendDetail.record_date || '')]
                  ].filter(([, value]) => value).forEach(([label, value]) => {
                    const detailLine = document.createElement('div');
                    detailLine.className = 'flex items-baseline justify-between gap-3 text-xs font-bold text-[#64748b] dark:text-[#a1a1aa]';
                    const left = document.createElement('span');
                    left.dataset.typingText = label;
                    left.textContent = '';
                    const right = document.createElement('span');
                    right.dataset.typingText = value;
                    right.textContent = '';
                    detailLine.append(left, right);
                    row.appendChild(detailLine);
                  });
                }

                const treasuryDetail = item.treasury_stock_detail && typeof item.treasury_stock_detail === 'object'
                  ? item.treasury_stock_detail : null;
                if (treasuryDetail && Object.keys(treasuryDetail).length) {
                  const shares = Number(treasuryDetail.shares);
                  const amount = Number(treasuryDetail.amount);
                  const price = Number(treasuryDetail.price);
                  [
                    ['구분', String(treasuryDetail.kind || '')],
                    ['예정주식수', Number.isFinite(shares) ? `${Math.round(shares).toLocaleString('ko-KR')}주` : ''],
                    ['예정금액', Number.isFinite(amount) ? Math.round(amount).toLocaleString('ko-KR') : ''],
                    ['1주당가액', Number.isFinite(price) ? Math.round(price).toLocaleString('ko-KR') : ''],
                    ['목적', String(treasuryDetail.purpose || '')],
                    ['방법', String(treasuryDetail.method || '')]
                  ].filter(([, value]) => value).slice(0, 4).forEach(([label, value]) => {
                    const detailLine = document.createElement('div');
                    detailLine.className = 'flex items-baseline justify-between gap-3 text-xs font-bold text-[#64748b] dark:text-[#a1a1aa]';
                    const left = document.createElement('span');
                    left.dataset.typingText = label;
                    left.textContent = '';
                    const right = document.createElement('span');
                    right.dataset.typingText = value;
                    right.textContent = '';
                    detailLine.append(left, right);
                    row.appendChild(detailLine);
                  });
                }

                const financingDetail = item.financing_detail && typeof item.financing_detail === 'object'
                  ? item.financing_detail : null;
                if (financingDetail && Object.keys(financingDetail).length) {
                  const amount = Number(financingDetail.amount);
                  const issuePrice = Number(financingDetail.issue_price);
                  const newShares = Number(financingDetail.new_shares);
                  [
                    ['조달유형', String(financingDetail.kind || '')],
                    ['조달금액', Number.isFinite(amount) ? Math.round(amount).toLocaleString('ko-KR') : ''],
                    ['발행가액', Number.isFinite(issuePrice) ? Math.round(issuePrice).toLocaleString('ko-KR') : ''],
                    ['신주수', Number.isFinite(newShares) ? `${Math.round(newShares).toLocaleString('ko-KR')}주` : ''],
                    ['방식', String(financingDetail.method || '')],
                    ['목적', String(financingDetail.purpose || '')]
                  ].filter(([, value]) => value).slice(0, 4).forEach(([label, value]) => {
                    const detailLine = document.createElement('div');
                    detailLine.className = 'flex items-baseline justify-between gap-3 text-xs font-bold text-[#64748b] dark:text-[#a1a1aa]';
                    const left = document.createElement('span');
                    left.dataset.typingText = label;
                    left.textContent = '';
                    const right = document.createElement('span');
                    right.dataset.typingText = value;
                    right.textContent = '';
                    detailLine.append(left, right);
                    row.appendChild(detailLine);
                  });
                }

                const supplyDetail = item.supply_contract_detail && typeof item.supply_contract_detail === 'object'
                  ? item.supply_contract_detail : null;
                if (supplyDetail && Object.keys(supplyDetail).length) {
                  const contractAmount = Number(supplyDetail.contract_amount);
                  const salesRatio = Number(supplyDetail.sales_ratio);
                  const contractRows = [
                    ['계약금액', Number.isFinite(contractAmount) ? Math.round(contractAmount).toLocaleString('ko-KR') : ''],
                    ['매출액 대비', Number.isFinite(salesRatio) ? `${salesRatio.toFixed(2)}%` : ''],
                    ['계약상대', String(supplyDetail.counterparty || '')],
                    ['계약내용', String(supplyDetail.contract_name || '')]
                  ].filter(([, value]) => value);
                  contractRows.slice(0, 4).forEach(([label, value]) => {
                    const detailLine = document.createElement('div');
                    detailLine.className = 'flex items-baseline justify-between gap-3 text-xs font-bold text-[#64748b] dark:text-[#a1a1aa]';
                    const left = document.createElement('span');
                    left.dataset.typingText = label;
                    left.textContent = '';
                    const right = document.createElement('span');
                    right.dataset.typingText = value;
                    right.textContent = '';
                    detailLine.append(left, right);
                    row.appendChild(detailLine);
                  });
                }

                const earningsDetail = item.earnings_detail && typeof item.earnings_detail === 'object'
                  ? item.earnings_detail : null;
                const earningsMetrics = Array.isArray(earningsDetail?.metrics) ? earningsDetail.metrics : [];
                earningsMetrics.slice(0, 3).forEach((metric) => {
                  const metricLine = document.createElement('div');
                  metricLine.className = 'flex items-baseline justify-between gap-3 text-xs font-bold text-[#64748b] dark:text-[#a1a1aa]';
                  const metricLeft = document.createElement('span');
                  metricLeft.dataset.typingText = String(metric.label || '');
                  metricLeft.textContent = '';
                  metricLine.appendChild(metricLeft);

                  const current = Number(metric.current);
                  const changeRate = Number(metric.change_rate);
                  const metricRight = document.createElement('span');
                  metricRight.dataset.typingText = [
                    Number.isFinite(current) ? Math.round(current).toLocaleString('ko-KR') : '',
                    Number.isFinite(changeRate) ? `${changeRate > 0 ? '+' : ''}${changeRate.toFixed(2)}%` : ''
                  ].filter(Boolean).join(' · ');
                  metricRight.textContent = '';
                  if (metricRight.dataset.typingText) metricLine.appendChild(metricRight);
                  row.appendChild(metricLine);
                });

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
                  if (centralDomestic) {
                    const parseShares = (value) => {
                      const text = String(value ?? '').replace(/,/g, '').trim();
                      return /^[-+]?\d+$/.test(text) ? Number(text) : NaN;
                    };
                    const after = parseShares(currentShares);
                    const delta = parseShares(shareDelta);
                    const before = after - delta;
                    if (Number.isSafeInteger(after) && Number.isSafeInteger(delta) && before >= 0) {
                      const comparison = document.createElement('div');
                      comparison.style.cssText = 'display:grid;gap:8px;margin:4px 0 8px';
                      const max = Math.max(before, after, 1);
                      [['변동 전', before], ['변동 후', after]].forEach(([label, value]) => {
                        const line = document.createElement('div');
                        line.style.cssText = 'display:grid;grid-template-columns:48px minmax(0,1fr) auto;gap:8px;align-items:center;font-size:12px;color:var(--gtp-text-2,#c4c4cc)';
                        const name = document.createElement('span');
                        name.textContent = label;
                        const track = document.createElement('div');
                        track.style.cssText = 'height:12px;border-radius:5px;background:var(--gtp-surface-2,#27272a);overflow:hidden';
                        const fill = document.createElement('div');
                        fill.style.cssText = 'height:100%;border-radius:5px;background:' +
                          (label === '변동 전' ? '#71717a' : (delta >= 0 ? '#d74b58' : '#478aca')) +
                          ';width:' + (value / max * 100).toFixed(2) + '%';
                        track.appendChild(fill);
                        const number = document.createElement('span');
                        number.textContent = value.toLocaleString('ko-KR') + '주';
                        line.append(name, track, number);
                        comparison.appendChild(line);
                      });
                      row.appendChild(comparison);
                    }
                  }
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
                  if (centralCard && transactions.length) {
                    const grouped = { P: 0, S: 0 };
                    transactions.forEach((transaction) => {
                      const code = String(transaction.code || '').toUpperCase().trim();
                      const qty = Number(String(transaction.shares ?? '').replaceAll(',', ''));
                      if ((code === 'P' || code === 'S') && Number.isFinite(qty) && qty > 0) {
                        grouped[code] += qty;
                      }
                    });
                    const maxQty = Math.max(grouped.P, grouped.S);
                    if (maxQty > 0) {
                      const bars = document.createElement('div');
                      bars.style.cssText = 'display:grid;gap:8px;margin:4px 0 8px';
                      [['P', '내부자 매수', '#d74b58'], ['S', '내부자 매도', '#478aca']].forEach(([code, label, color]) => {
                        if (!grouped[code]) return;
                        const line = document.createElement('div');
                        line.style.cssText = 'display:grid;grid-template-columns:72px minmax(0,1fr) auto;gap:8px;align-items:center;font-size:12px;color:var(--gtp-text-2,#c4c4cc)';
                        const name = document.createElement('span');
                        name.textContent = label;
                        const track = document.createElement('div');
                        track.style.cssText = 'height:12px;border-radius:5px;background:var(--gtp-surface-2,#27272a);overflow:hidden';
                        const fill = document.createElement('div');
                        fill.style.cssText = 'height:100%;border-radius:5px;background:' + color + ';width:' + (grouped[code] / maxQty * 100).toFixed(2) + '%';
                        track.appendChild(fill);
                        const number = document.createElement('span');
                        number.textContent = grouped[code].toLocaleString('ko-KR') + '주';
                        line.append(name, track, number);
                        bars.appendChild(line);
                      });
                      row.appendChild(bars);
                    }
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

                if (centralCard && !centralDomestic) {
                  const summaryParts = Array.from(metaEl.querySelectorAll('span')).slice(1)
                    .map((el) => el.dataset.typingText || '').filter(Boolean);
                  if (summaryParts.length) {
                    const summary = document.createElement('div');
                    summary.style.cssText = 'font-size:var(--gtp-type-meta,12px);color:var(--gtp-text-2,#c4c4cc);font-weight:500';
                    summary.dataset.typingText = summaryParts.join(' · ');
                    row.appendChild(summary);
                  }
                  const secLink = String(item.url || item.link || '').trim();
                  if (/^https:\/\/www\.sec\.gov\//i.test(secLink)) {
                    const original = document.createElement('a');
                    original.href = secLink;
                    original.target = '_blank';
                    original.rel = 'noopener noreferrer';
                    original.textContent = 'SEC 공시 원문 보기 ↗';
                    original.style.cssText = 'font-size:var(--gtp-type-meta,12px);color:var(--gtp-muted,#a1a1aa);text-decoration:none;margin-top:4px';
                    row.appendChild(original);
                  }
                }
                if (centralDomestic && /^\d{14}$/.test(String(item.receipt_no || ''))) {
                  const original = document.createElement('a');
                  original.href = 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=' + item.receipt_no;
                  original.target = '_blank';
                  original.rel = 'noopener noreferrer';
                  original.textContent = '공시 원문 보기 ↗';
                  original.style.cssText = 'font-size:var(--gtp-type-meta,12px);color:var(--gtp-muted,#a1a1aa);text-decoration:none;margin-top:4px';
                  row.appendChild(original);
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
 + value.toLocaleString('en-US', {
            maximumFractionDigits: metric.unit === 'USD/shares' ? 2 : 0
          });
          texts.push([metric.label, amount, metric.period_end].filter(Boolean).join(' · '));
        });
        for (const text of texts) {
          const line = document.createElement('div');
          line.className = 'right-panel-disclosures__line';
          line.textContent = text;
          target.appendChild(line);
        }
      } catch (error) {
        console.warn('[SEC 상세] 오른쪽 패널 조회 실패:', error);
      }
    }
  }));
};

window.GaemiGTPDisclosures.secFilingTitle = function (item) {
  if (String(item?.source || '').toUpperCase() !== 'SEC') return item?.title || '공시 제목 확인 필요';
  const original = String(item.title || '').trim();
  const form = String(item.form || '').toUpperCase();
  const generic = !original || original === 'SEC 공식 공시' ||
    /^SEC\s+(?:144|10-Q|10-K|4\/A)\s*공시$/i.test(original) ||
    /^FORM\s+4\/A$/i.test(original);
  if (!generic) return original;
  const titles = {
    '4/A': '내부자 거래 정정 공시',
    '144': '증권 매도 예정 신고',
    '10-Q': '분기 실적보고서',
    '10-K': '연간 실적보고서',
    '6-K': '외국기업 수시보고서',
    '20-F': '외국기업 연차보고서',
    'SC 13D': '대량 지분 보유 신고',
    'SC 13G': '대량 지분 보유 신고',
    'S-1': '증권 등록신고서',
    'S-3': '증권 등록신고서',
    '424B5': '증권 발행 투자설명서'
  };
  return titles[form] || original || 'SEC ' + form + ' 공시';
};

window.GaemiGTPDisclosures.renderDisclosures = async function ({
  disclosures,
  allDisclosures,
  articles,
  block,
  responseMessageClass,
  openExternalLinkModal,
  typeText
}) {
            const domesticItems = (Array.isArray(disclosures) ? disclosures : []).filter(
              (item) => String(item?.source || '').toUpperCase() === 'DART'
            );
            // Only the central domestic disclosure uses the compact card. The right panel
            // continues rendering its complete independent list.
            const centralDomestic = domesticItems.length > 0;
            const centralCard = Array.isArray(disclosures) && disclosures.length > 0;
            const centralItems = centralCard ? disclosures.slice(0, 1) : disclosures;
            const disclosureSection = document.createElement('section');
            disclosureSection.className = 'space-y-2';
            if (centralCard) {
              disclosureSection.style.cssText = [
                'border:1px solid var(--gtp-border-strong, #3f3f46)',
                'border-radius:18px',
                'padding:18px',
                'display:flex',
                'flex-direction:column',
                'gap:14px',
                'font-family:Pretendard,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif',
                'color:var(--gtp-text, #e4e4e7)'
              ].join(';');
            }
            const disclosureTitle = Object.assign(document.createElement('p'), { className: responseMessageClass });
            disclosureSection.appendChild(disclosureTitle);
            block.appendChild(disclosureSection);
            if (typeof typeText === 'function') {
              await typeText(disclosureTitle, centralCard ? '오늘의 공식 공시' : '오늘 공시는?');
            } else {
              disclosureTitle.textContent = centralCard ? '오늘의 공식 공시' : '오늘 공시는?';
            }

            if (centralItems.length) {
              await window.GaemiGTPDisclosures.hydrateDartDetails(centralItems);

              const disclosureRows = [];
              centralItems.forEach((item) => {
                const row = document.createElement('div');
                row.className = 'space-y-1 text-[#475569] dark:text-[#d4d4d8]';
                row.style.fontSize = window.matchMedia('(min-width: 640px)').matches ? '1rem' : '14px';
                if (centralCard) row.style.cssText += ';display:flex;flex-direction:column;gap:10px';

                const titleEl = document.createElement('div');
                titleEl.dataset.typingText = item.title || '공시 제목 확인 필요';
                titleEl.textContent = '';
                row.appendChild(titleEl);
                if (centralCard) {
                  titleEl.style.cssText = 'font-size:var(--gtp-type-title,14px);font-weight:650;line-height:1.55;color:var(--gtp-text,#e4e4e7)';
                  const topMeta = document.createElement('span');
                  topMeta.style.cssText = 'font-size:var(--gtp-type-meta,12px);font-weight:500;color:var(--gtp-muted,#a1a1aa);white-space:nowrap;text-align:right';
                  topMeta.dataset.typingText = [item.source || (centralDomestic ? 'DART' : 'SEC'), item.date || '', item.time || ''].filter(Boolean).join(' · ');
                  topMeta.textContent = '';
                  const cardHeader = document.createElement('div');
                  cardHeader.style.cssText = 'display:flex;align-items:flex-start;justify-content:space-between;gap:10px';
                  disclosureSection.insertBefore(cardHeader, disclosureTitle);
                  cardHeader.append(disclosureTitle, topMeta);
                  disclosureTitle.style.cssText = 'font-size:var(--gtp-type-title,14px);font-weight:650;color:var(--gtp-text,#e4e4e7);margin:0';
                }

                const metaEl = document.createElement('div');
                metaEl.className = 'flex items-baseline justify-between gap-3 text-xs font-bold text-[#64748b] dark:text-[#a1a1aa]';
                const metaLeft = document.createElement('span');
                metaLeft.dataset.typingText = [item.date || '', item.time || '', item.source || '공시'].filter(Boolean).join(' · ');
                metaLeft.textContent = '';
                metaEl.appendChild(metaLeft);
                if (!centralCard) row.appendChild(metaEl);

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

                const actionDetail = item.corporate_action_detail && typeof item.corporate_action_detail === 'object'
                  ? item.corporate_action_detail : null;
                if (actionDetail && Object.keys(actionDetail).length) {
                  const amount = Number(actionDetail.amount);
                  const equityRatio = Number(actionDetail.equity_ratio);
                  const shares = Number(actionDetail.shares);
                  const ratio = Number(actionDetail.ratio);
                  [
                    ['구분', String(actionDetail.kind || '')],
                    ['상대회사', String(actionDetail.counterparty || '')],
                    ['거래금액', Number.isFinite(amount) ? Math.round(amount).toLocaleString('ko-KR') : ''],
                    ['지분율', Number.isFinite(equityRatio) ? `${equityRatio.toFixed(2)}%` : ''],
                    ['주식수', Number.isFinite(shares) ? `${Math.round(shares).toLocaleString('ko-KR')}주` : ''],
                    ['자기자본 대비', Number.isFinite(ratio) ? `${ratio.toFixed(2)}%` : ''],
                    ['목적', String(actionDetail.purpose || '')]
                  ].filter(([, value]) => value).slice(0, 4).forEach(([label, value]) => {
                    const detailLine = document.createElement('div');
                    detailLine.className = 'flex items-baseline justify-between gap-3 text-xs font-bold text-[#64748b] dark:text-[#a1a1aa]';
                    const left = document.createElement('span');
                    left.dataset.typingText = label;
                    left.textContent = '';
                    const right = document.createElement('span');
                    right.dataset.typingText = value;
                    right.textContent = '';
                    detailLine.append(left, right);
                    row.appendChild(detailLine);
                  });
                }

                const dividendDetail = item.dividend_detail && typeof item.dividend_detail === 'object'
                  ? item.dividend_detail : null;
                if (dividendDetail && Object.keys(dividendDetail).length) {
                  const perShare = Number(dividendDetail.dividend_per_share);
                  const rate = Number(dividendDetail.dividend_rate);
                  const total = Number(dividendDetail.total_amount);
                  [
                    ['주당배당금', Number.isFinite(perShare) ? `${Math.round(perShare).toLocaleString('ko-KR')}원` : ''],
                    ['시가배당률', Number.isFinite(rate) ? `${rate.toFixed(2)}%` : ''],
                    ['배당금총액', Number.isFinite(total) ? Math.round(total).toLocaleString('ko-KR') : ''],
                    ['배당기준일', String(dividendDetail.record_date || '')]
                  ].filter(([, value]) => value).forEach(([label, value]) => {
                    const detailLine = document.createElement('div');
                    detailLine.className = 'flex items-baseline justify-between gap-3 text-xs font-bold text-[#64748b] dark:text-[#a1a1aa]';
                    const left = document.createElement('span');
                    left.dataset.typingText = label;
                    left.textContent = '';
                    const right = document.createElement('span');
                    right.dataset.typingText = value;
                    right.textContent = '';
                    detailLine.append(left, right);
                    row.appendChild(detailLine);
                  });
                }

                const treasuryDetail = item.treasury_stock_detail && typeof item.treasury_stock_detail === 'object'
                  ? item.treasury_stock_detail : null;
                if (treasuryDetail && Object.keys(treasuryDetail).length) {
                  const shares = Number(treasuryDetail.shares);
                  const amount = Number(treasuryDetail.amount);
                  const price = Number(treasuryDetail.price);
                  [
                    ['구분', String(treasuryDetail.kind || '')],
                    ['예정주식수', Number.isFinite(shares) ? `${Math.round(shares).toLocaleString('ko-KR')}주` : ''],
                    ['예정금액', Number.isFinite(amount) ? Math.round(amount).toLocaleString('ko-KR') : ''],
                    ['1주당가액', Number.isFinite(price) ? Math.round(price).toLocaleString('ko-KR') : ''],
                    ['목적', String(treasuryDetail.purpose || '')],
                    ['방법', String(treasuryDetail.method || '')]
                  ].filter(([, value]) => value).slice(0, 4).forEach(([label, value]) => {
                    const detailLine = document.createElement('div');
                    detailLine.className = 'flex items-baseline justify-between gap-3 text-xs font-bold text-[#64748b] dark:text-[#a1a1aa]';
                    const left = document.createElement('span');
                    left.dataset.typingText = label;
                    left.textContent = '';
                    const right = document.createElement('span');
                    right.dataset.typingText = value;
                    right.textContent = '';
                    detailLine.append(left, right);
                    row.appendChild(detailLine);
                  });
                }

                const financingDetail = item.financing_detail && typeof item.financing_detail === 'object'
                  ? item.financing_detail : null;
                if (financingDetail && Object.keys(financingDetail).length) {
                  const amount = Number(financingDetail.amount);
                  const issuePrice = Number(financingDetail.issue_price);
                  const newShares = Number(financingDetail.new_shares);
                  [
                    ['조달유형', String(financingDetail.kind || '')],
                    ['조달금액', Number.isFinite(amount) ? Math.round(amount).toLocaleString('ko-KR') : ''],
                    ['발행가액', Number.isFinite(issuePrice) ? Math.round(issuePrice).toLocaleString('ko-KR') : ''],
                    ['신주수', Number.isFinite(newShares) ? `${Math.round(newShares).toLocaleString('ko-KR')}주` : ''],
                    ['방식', String(financingDetail.method || '')],
                    ['목적', String(financingDetail.purpose || '')]
                  ].filter(([, value]) => value).slice(0, 4).forEach(([label, value]) => {
                    const detailLine = document.createElement('div');
                    detailLine.className = 'flex items-baseline justify-between gap-3 text-xs font-bold text-[#64748b] dark:text-[#a1a1aa]';
                    const left = document.createElement('span');
                    left.dataset.typingText = label;
                    left.textContent = '';
                    const right = document.createElement('span');
                    right.dataset.typingText = value;
                    right.textContent = '';
                    detailLine.append(left, right);
                    row.appendChild(detailLine);
                  });
                }

                const supplyDetail = item.supply_contract_detail && typeof item.supply_contract_detail === 'object'
                  ? item.supply_contract_detail : null;
                if (supplyDetail && Object.keys(supplyDetail).length) {
                  const contractAmount = Number(supplyDetail.contract_amount);
                  const salesRatio = Number(supplyDetail.sales_ratio);
                  const contractRows = [
                    ['계약금액', Number.isFinite(contractAmount) ? Math.round(contractAmount).toLocaleString('ko-KR') : ''],
                    ['매출액 대비', Number.isFinite(salesRatio) ? `${salesRatio.toFixed(2)}%` : ''],
                    ['계약상대', String(supplyDetail.counterparty || '')],
                    ['계약내용', String(supplyDetail.contract_name || '')]
                  ].filter(([, value]) => value);
                  contractRows.slice(0, 4).forEach(([label, value]) => {
                    const detailLine = document.createElement('div');
                    detailLine.className = 'flex items-baseline justify-between gap-3 text-xs font-bold text-[#64748b] dark:text-[#a1a1aa]';
                    const left = document.createElement('span');
                    left.dataset.typingText = label;
                    left.textContent = '';
                    const right = document.createElement('span');
                    right.dataset.typingText = value;
                    right.textContent = '';
                    detailLine.append(left, right);
                    row.appendChild(detailLine);
                  });
                }

                const earningsDetail = item.earnings_detail && typeof item.earnings_detail === 'object'
                  ? item.earnings_detail : null;
                const earningsMetrics = Array.isArray(earningsDetail?.metrics) ? earningsDetail.metrics : [];
                earningsMetrics.slice(0, 3).forEach((metric) => {
                  const metricLine = document.createElement('div');
                  metricLine.className = 'flex items-baseline justify-between gap-3 text-xs font-bold text-[#64748b] dark:text-[#a1a1aa]';
                  const metricLeft = document.createElement('span');
                  metricLeft.dataset.typingText = String(metric.label || '');
                  metricLeft.textContent = '';
                  metricLine.appendChild(metricLeft);

                  const current = Number(metric.current);
                  const changeRate = Number(metric.change_rate);
                  const metricRight = document.createElement('span');
                  metricRight.dataset.typingText = [
                    Number.isFinite(current) ? Math.round(current).toLocaleString('ko-KR') : '',
                    Number.isFinite(changeRate) ? `${changeRate > 0 ? '+' : ''}${changeRate.toFixed(2)}%` : ''
                  ].filter(Boolean).join(' · ');
                  metricRight.textContent = '';
                  if (metricRight.dataset.typingText) metricLine.appendChild(metricRight);
                  row.appendChild(metricLine);
                });

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
                  if (centralDomestic) {
                    const parseShares = (value) => {
                      const text = String(value ?? '').replace(/,/g, '').trim();
                      return /^[-+]?\d+$/.test(text) ? Number(text) : NaN;
                    };
                    const after = parseShares(currentShares);
                    const delta = parseShares(shareDelta);
                    const before = after - delta;
                    if (Number.isSafeInteger(after) && Number.isSafeInteger(delta) && before >= 0) {
                      const comparison = document.createElement('div');
                      comparison.style.cssText = 'display:grid;gap:8px;margin:4px 0 8px';
                      const max = Math.max(before, after, 1);
                      [['변동 전', before], ['변동 후', after]].forEach(([label, value]) => {
                        const line = document.createElement('div');
                        line.style.cssText = 'display:grid;grid-template-columns:48px minmax(0,1fr) auto;gap:8px;align-items:center;font-size:12px;color:var(--gtp-text-2,#c4c4cc)';
                        const name = document.createElement('span');
                        name.textContent = label;
                        const track = document.createElement('div');
                        track.style.cssText = 'height:12px;border-radius:5px;background:var(--gtp-surface-2,#27272a);overflow:hidden';
                        const fill = document.createElement('div');
                        fill.style.cssText = 'height:100%;border-radius:5px;background:' +
                          (label === '변동 전' ? '#71717a' : (delta >= 0 ? '#d74b58' : '#478aca')) +
                          ';width:' + (value / max * 100).toFixed(2) + '%';
                        track.appendChild(fill);
                        const number = document.createElement('span');
                        number.textContent = value.toLocaleString('ko-KR') + '주';
                        line.append(name, track, number);
                        comparison.appendChild(line);
                      });
                      row.appendChild(comparison);
                    }
                  }
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
                  if (centralCard && transactions.length) {
                    const grouped = { P: 0, S: 0 };
                    transactions.forEach((transaction) => {
                      const code = String(transaction.code || '').toUpperCase().trim();
                      const qty = Number(String(transaction.shares ?? '').replaceAll(',', ''));
                      if ((code === 'P' || code === 'S') && Number.isFinite(qty) && qty > 0) {
                        grouped[code] += qty;
                      }
                    });
                    const maxQty = Math.max(grouped.P, grouped.S);
                    if (maxQty > 0) {
                      const bars = document.createElement('div');
                      bars.style.cssText = 'display:grid;gap:8px;margin:4px 0 8px';
                      [['P', '내부자 매수', '#d74b58'], ['S', '내부자 매도', '#478aca']].forEach(([code, label, color]) => {
                        if (!grouped[code]) return;
                        const line = document.createElement('div');
                        line.style.cssText = 'display:grid;grid-template-columns:72px minmax(0,1fr) auto;gap:8px;align-items:center;font-size:12px;color:var(--gtp-text-2,#c4c4cc)';
                        const name = document.createElement('span');
                        name.textContent = label;
                        const track = document.createElement('div');
                        track.style.cssText = 'height:12px;border-radius:5px;background:var(--gtp-surface-2,#27272a);overflow:hidden';
                        const fill = document.createElement('div');
                        fill.style.cssText = 'height:100%;border-radius:5px;background:' + color + ';width:' + (grouped[code] / maxQty * 100).toFixed(2) + '%';
                        track.appendChild(fill);
                        const number = document.createElement('span');
                        number.textContent = grouped[code].toLocaleString('ko-KR') + '주';
                        line.append(name, track, number);
                        bars.appendChild(line);
                      });
                      row.appendChild(bars);
                    }
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

                if (centralCard && !centralDomestic) {
                  const summaryParts = Array.from(metaEl.querySelectorAll('span')).slice(1)
                    .map((el) => el.dataset.typingText || '').filter(Boolean);
                  if (summaryParts.length) {
                    const summary = document.createElement('div');
                    summary.style.cssText = 'font-size:var(--gtp-type-meta,12px);color:var(--gtp-text-2,#c4c4cc);font-weight:500';
                    summary.dataset.typingText = summaryParts.join(' · ');
                    row.appendChild(summary);
                  }
                  const secLink = String(item.url || item.link || '').trim();
                  if (/^https:\/\/www\.sec\.gov\//i.test(secLink)) {
                    const original = document.createElement('a');
                    original.href = secLink;
                    original.target = '_blank';
                    original.rel = 'noopener noreferrer';
                    original.textContent = 'SEC 공시 원문 보기 ↗';
                    original.style.cssText = 'font-size:var(--gtp-type-meta,12px);color:var(--gtp-muted,#a1a1aa);text-decoration:none;margin-top:4px';
                    row.appendChild(original);
                  }
                }
                if (centralDomestic && /^\d{14}$/.test(String(item.receipt_no || ''))) {
                  const original = document.createElement('a');
                  original.href = 'https://dart.fss.or.kr/dsaf001/main.do?rcpNo=' + item.receipt_no;
                  original.target = '_blank';
                  original.rel = 'noopener noreferrer';
                  original.textContent = '공시 원문 보기 ↗';
                  original.style.cssText = 'font-size:var(--gtp-type-meta,12px);color:var(--gtp-muted,#a1a1aa);text-decoration:none;margin-top:4px';
                  row.appendChild(original);
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
