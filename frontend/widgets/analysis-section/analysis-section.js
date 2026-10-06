/* Analysis Section Widgets
   Each widget reads only the data it owns from GaemiGTPAnalysisData. */
(function () {
  'use strict';

  const SECTION_BY_WIDGET = { supply: 'supply', levels: 'levels', economic: 'calendar' };

  function escapeHtml(value) {
    return String(value || '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#039;');
  }
  function empty(root, message) { root.innerHTML = `<div class="analysis-section-widget__empty">${escapeHtml(message)}</div>`; }
  function renderSection(root, section) {
    if (!section) { empty(root, '종목을 분석하면 이 위젯에 표시됩니다.'); return; }
    root.innerHTML = `<div class="analysis-section-widget__title">${escapeHtml(section.title)}</div><p class="analysis-section-widget__content">${escapeHtml(section.content)}</p>`;
  }
  function renderMaterials(root, data) {
    const items = [...data.newsItems, ...data.disclosures, ...data.usFilings].slice(0, 5);
    if (!items.length) { empty(root, '종목을 분석하면 관련 뉴스와 공시가 표시됩니다.'); return; }
    root.innerHTML = `<div class="analysis-section-widget__list">${items.map(item => {
      const title = escapeHtml(item.title || item.description || '제목 확인 필요');
      const source = escapeHtml(item.source || (item.form ? 'SEC' : '출처 확인 필요'));
      return `<div class="analysis-section-widget__row"><strong>${title}</strong><span>${source}</span></div>`;
    }).join('')}</div>`;
  }
  function mount(widgetId, root) {
    if (!root) return;
    if (widgetId === 'why-up') {
      root.classList.add('analysis-section-widget__why-up');
      root.innerHTML = window.GaemiGTPWhyUpContent?.render?.('widget') || '';
      return;
    }
    const data = window.GaemiGTPAnalysisData?.get?.();
    if (!data) { empty(root, '분석 데이터를 준비하고 있습니다.'); return; }
    if (widgetId === 'materials') { renderMaterials(root, data); return; }
    const sectionId = SECTION_BY_WIDGET[widgetId];
    if (sectionId) renderSection(root, data.sections[sectionId]);
  }
  window.GaemiGTPAnalysisWidgets = { mount };
}());

/* Analysis loading presentation
   Only changes the sequence before the existing first result is typed. */
(function () {
  'use strict';

  const STAGE_MS = 4000;
  const NEWS_FLOW_URL = 'https://gaemi-gtp.onrender.com/news/stock-flow';

  function getPriceState(sections) {
    const why = Array.isArray(sections) ? sections.find(section => section?.id === 'why-up') : null;
    const match = String(why?.content || '').match(/([+-]\d+(?:\.\d+)?)%/);
    const change = match ? Number(match[1]) : 0;
    if (change >= 0.5) return 'positive';
    if (change <= -0.5) return 'negative';
    return 'mixed';
  }

  function prepareCentralNewsFlow(items, flow, priceState) {
    const rows = Array.isArray(items) ? items.map(item => ({ ...item })) : [];
    const ranked = Array.isArray(flow?.top_signals) ? flow.top_signals : [];
    const scoreByLabel = new Map(ranked.map(signal => [String(signal?.label || '').trim(), Number(signal?.evidence_score || 0)]));

    const tonePriority = (tone) => {
      if (priceState === 'positive') return tone === 'positive' ? 0 : tone === 'negative' ? 2 : 1;
      if (priceState === 'negative') return tone === 'negative' ? 0 : tone === 'positive' ? 2 : 1;
      return tone === 'positive' || tone === 'negative' ? 0 : 1;
    };

    rows.forEach((item) => {
      const signals = Array.isArray(item.movement_signals) ? [...item.movement_signals] : [];
      signals.sort((a, b) => {
        const toneGap = tonePriority(a?.tone) - tonePriority(b?.tone);
        if (toneGap) return toneGap;
        return (scoreByLabel.get(String(b?.label || '').trim()) || 0) - (scoreByLabel.get(String(a?.label || '').trim()) || 0);
      });
      item.movement_signals = signals;
      const matching = signals.filter(signal => {
        if (priceState === 'positive') return signal?.tone === 'positive';
        if (priceState === 'negative') return signal?.tone === 'negative';
        return signal?.tone === 'positive' || signal?.tone === 'negative';
      });
      item._whyMatch = matching.length ? 1 : 0;
      item._whyEvidence = matching.reduce((best, signal) => Math.max(best, scoreByLabel.get(String(signal?.label || '').trim()) || 0), 0);
    });

    rows.sort((a, b) => (b._whyMatch - a._whyMatch) || (b._whyEvidence - a._whyEvidence) || ((b.flow_score || 0) - (a.flow_score || 0)));
    rows.forEach(item => { delete item._whyMatch; delete item._whyEvidence; });
    return rows;
  }

  async function loadCentralNewsFlow(stockName, result, sections) {
    if (!result || !stockName) return;
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 6500);
      const response = await fetch(`${NEWS_FLOW_URL}?stock=${encodeURIComponent(stockName)}`, { signal: controller.signal, cache: 'no-store' });
      clearTimeout(timeout);
      if (!response.ok) return;
      const payload = await response.json();
      const priceState = getPriceState(sections);
      const flowItems = prepareCentralNewsFlow(payload?.items, payload?.flow, priceState);
      if (flowItems.length) result.news_items = flowItems;
      if (payload?.flow && typeof payload.flow === 'object') {
        result.news_flow = { ...payload.flow, price_state: priceState };
      }
    } catch (_) {
      // 흐름 API가 늦거나 실패하면 기존 /analyze 결과로 그대로 진행한다.
    }
  }

  window.GaemiGTPLoadCentralNewsFlow = loadCentralNewsFlow;
}());