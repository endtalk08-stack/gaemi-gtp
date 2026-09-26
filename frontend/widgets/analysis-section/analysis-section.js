/* Analysis Section Widgets
   Each widget reads only the data it owns from GaemiGTPAnalysisData. */
(function () {
  'use strict';

  const SECTION_BY_WIDGET = {
    supply: 'supply',
    levels: 'levels',
    economic: 'calendar',
  };

  function escapeHtml(value) {
    return String(value || '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function empty(root, message) {
    root.innerHTML = `<div class="analysis-section-widget__empty">${escapeHtml(message)}</div>`;
  }

  function renderSection(root, section) {
    if (!section) {
      empty(root, '종목을 분석하면 이 위젯에 표시됩니다.');
      return;
    }
    root.innerHTML = `
      <div class="analysis-section-widget__title">${escapeHtml(section.title)}</div>
      <p class="analysis-section-widget__content">${escapeHtml(section.content)}</p>`;
  }

  function renderMaterials(root, data) {
    const items = [...data.newsItems, ...data.disclosures, ...data.usFilings].slice(0, 5);
    if (!items.length) {
      empty(root, '종목을 분석하면 관련 뉴스와 공시가 표시됩니다.');
      return;
    }
    root.innerHTML = `<div class="analysis-section-widget__list">${items.map(item => {
      const title = escapeHtml(item.title || item.description || '제목 확인 필요');
      const source = escapeHtml(item.source || (item.form ? 'SEC' : '출처 확인 필요'));
      return `<div class="analysis-section-widget__row"><strong>${title}</strong><span>${source}</span></div>`;
    }).join('')}</div>`;
  }

  function mount(widgetId, root) {
    if (!root) return;
    // 본문과 같은 고정 콘텐츠를 표시하며 분석 API 데이터는 사용하지 않는다.
    if (widgetId === 'why-up') {
      root.classList.add('analysis-section-widget__why-up');
      root.innerHTML = window.GaemiGTPWhyUpContent?.render?.('widget') || '';
      return;
    }
    const data = window.GaemiGTPAnalysisData?.get?.();
    if (!data) {
      empty(root, '분석 데이터를 준비하고 있습니다.');
      return;
    }
    if (widgetId === 'materials') {
      renderMaterials(root, data);
      return;
    }
    const sectionId = SECTION_BY_WIDGET[widgetId];
    if (sectionId) renderSection(root, data.sections[sectionId]);
  }

  window.GaemiGTPAnalysisWidgets = { mount };
}());
