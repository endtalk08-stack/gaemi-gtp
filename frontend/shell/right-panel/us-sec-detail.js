// Read-only SEC disclosure details for the existing right-hand 30-day panel only.
(function () {
  'use strict';

  const baseUrl = () => window.location.hostname.endsWith('github.io')
    ? 'https://gaemi-gtp.onrender.com' : window.location.origin;
  const el = (tag, className, value) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (value !== undefined && value !== null) node.textContent = String(value);
    return node;
  };
  const numberText = (value, unit) => {
    if (value === null || value === undefined || !Number.isFinite(Number(value))) return '확인되지 않음';
    const n = Number(value);
    if (unit === 'USD/shares') return '$' + n.toLocaleString('en-US', { maximumFractionDigits: 2 });
    const abs = Math.abs(n);
    const div = abs >= 1e9 ? 1e9 : abs >= 1e6 ? 1e6 : 1;
    const suffix = div === 1e9 ? 'B' : div === 1e6 ? 'M' : '';
    return (n < 0 ? '-' : '') + '$' + (abs / div).toLocaleString('en-US', { maximumFractionDigits: 2 }) + suffix;
  };
  const kv = (root, label, value) => {
    if (value === null || value === undefined || String(value).trim() === '') return;
    const row = el('div', 'flex flex-wrap items-baseline gap-2 text-sm py-1');
    row.append(el('span', 'text-[#64748b] dark:text-[#a1a1aa]', label));
    row.append(el('span', 'gtp-dark-text font-semibold', value));
    root.appendChild(row);
  };
  const paragraph = (root, text) => {
    if (!String(text || '').trim()) return;
    root.appendChild(el('p', 'text-sm leading-relaxed whitespace-pre-wrap gtp-dark-text', text));
  };
  const metricChart = (root, metric) => {
    const data = [{ label: '이번 보고기간', value: metric.current, end: metric.period_end }];
    if (metric.previous !== null && metric.previous !== undefined) {
      data.unshift({ label: '전년 비교기간', value: metric.previous, end: metric.previous_period_end });
    }
    const title = el('div', 'font-semibold text-sm gtp-dark-text mb-2', metric.label);
    root.appendChild(title);
    const max = Math.max(1, ...data.map(v => Math.abs(Number(v.value) || 0)));
    data.forEach(({ label, value, end }) => {
      const line = el('div', 'grid gap-1 mb-3');
      const summary = el('div', 'flex flex-wrap justify-between gap-1 text-xs gtp-dark-text');
      summary.append(el('span', '', label + (end ? ' · ' + end : '')));
      summary.append(el('strong', '', numberText(value, metric.unit)));
      line.appendChild(summary);
      const track = el('div', 'rounded-md overflow-hidden bg-[#e2e8f0] dark:bg-[#303035]');
      track.style.height = '12px';
      const fill = el('div', 'h-full rounded-md');
      fill.style.width = (Math.abs(Number(value) || 0) / max * 100).toFixed(2) + '%';
      fill.style.background = label === '이번 보고기간' ? '#3b82f6' : '#94a3b8';
      track.appendChild(fill);
      line.appendChild(track);
      root.appendChild(line);
    });
  };

  function detailCard(item) {
    const card = el('section', 'mt-3 p-4 rounded-xl border border-[#cbd5e1] dark:border-[#3f3f46] grid gap-3');
    const form = String(item.form || '').toUpperCase();
    const head = el('h4', 'font-semibold gtp-dark-text', form + ' · ' + (item.title || '공시 상세'));
    card.appendChild(head);
    kv(card, 'SEC 공시일', item.date);
    kv(card, '접수번호', item.accession);
    if (form === '8-K') {
      kv(card, '주요 사건', item.event_title);
      const points = item.key_points_ko?.length ? item.key_points_ko : item.key_points || [];
      points.forEach(point => paragraph(card, '• ' + point));
      if (!points.length) paragraph(card, '원문에서 구조화된 핵심 내용을 확인하지 못했어.');
    } else if (form === '4') {
      kv(card, '거래 신고자', item.person);
      kv(card, '직책', item.officer_title);
      const transactions = Array.isArray(item.transactions) ? item.transactions : [];
      transactions.forEach(tx => {
        const code = String(tx.code || '').toUpperCase();
        const name = { P: '매수', S: '매도', M: '옵션 행사', A: '취득', D: '처분', F: '세금 지급', G: '증여' }[code] || '거래 ' + (code || '종류 미확인');
        kv(card, name, [
          tx.shares ? Number(String(tx.shares).replaceAll(',', '')).toLocaleString('en-US') + '주' : '',
          tx.price ? '주당 $' + tx.price : '',
          tx.derivative ? '(파생증권)' : ''
        ].filter(Boolean).join(' · '));
      });
      if (!transactions.length) paragraph(card, '거래 상세정보가 아직 추출되지 않았어.');
    } else if (form === '10-Q' || form === '10-K') {
      const metrics = Array.isArray(item.metrics) ? item.metrics : [];
      if (!metrics.length) paragraph(card, 'SEC 재무 데이터에서 이번 공시와 일치하는 수치를 확인하지 못했어.');
      metrics.forEach(metric => metricChart(card, metric));
      if (metrics.length) paragraph(card, 'SEC XBRL 공식 제출 수치. 전년 비교값이 없는 항목은 이번 보고기간만 표시해.');
    } else {
      paragraph(card, '이 공시 유형은 아직 상세 숫자 추출을 지원하지 않아. 원문에서 확인할 수 있어.');
    }
    if (item.detail_status === 'partial') {
      paragraph(card, '일부 상세정보를 확인하지 못했어. 원문을 함께 확인해 줘.');
    }
    const link = item.original_document_url || item.url;
    if (link && /^https:\/\/www\.sec\.gov\//.test(link)) {
      const a = el('a', 'text-sm underline text-blue-600 dark:text-blue-400', 'SEC 원문 열기 ↗');
      a.href = link;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      card.appendChild(a);
    }
    return card;
  }

  async function expand(anchor, item) {
    const adjacent = anchor.nextElementSibling;
    if (adjacent?.dataset.secDetail === 'true') {
      adjacent.hidden = !adjacent.hidden;
      return;
    }
    const box = el('div', 'mt-2');
    box.dataset.secDetail = 'true';
    box.appendChild(el('p', 'text-sm text-[#64748b] dark:text-[#a1a1aa]', 'SEC 상세정보 확인 중…'));
    anchor.insertAdjacentElement('afterend', box);
    const stock = item.ticker || item.stock || item.symbol || window.GaemiGTPAnalysisData?.get?.()?.stockName;
    if (!stock || !item.accession) {
      box.replaceChildren(el('p', 'text-sm', '공시 상세 식별정보가 없어 원문을 확인해야 해.'));
      return;
    }
    try {
      const params = new URLSearchParams({ stock, accession: item.accession });
      const response = await fetch(baseUrl() + '/disclosures/sec/detail?' + params.toString(), {
        credentials: 'same-origin'
      });
      const result = await response.json();
      if (!response.ok || !result.ok || !result.detail) throw new Error('detail_unavailable');
      if (box.isConnected) box.replaceChildren(detailCard(result.detail));
    } catch (_) {
      if (box.isConnected) box.replaceChildren(el('p', 'text-sm', '공시 상세정보를 불러오지 못했어. SEC 원문에서 확인해 줘.'));
    }
  }

  window.GaemiGTPUSSecRightPanel = { expand };
})();
