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

/* Analysis loading presentation
   Only changes the sequence before the existing first result is typed. */
(function () {
  'use strict';

  const STAGE_MS = 4000;

  function installLoadingPresentation() {
    const originalRequestStock = window.requestStock;
    const originalStartTypewriterFlow = window.startTypewriterFlow;
    if (typeof originalRequestStock !== 'function' || typeof originalStartTypewriterFlow !== 'function') return;
    if (window.__gaemiLoadingPresentationInstalled) return;
    window.__gaemiLoadingPresentationInstalled = true;

    const style = document.createElement('style');
    style.textContent = `
      #surpriseAntPopup { display: none !important; }
      .analysis-loading-sequence {
        width: 100%; min-height: 92px; display: flex; align-items: center; justify-content: center;
        padding: 18px 8px; text-align: center;
      }
      .analysis-loading-dots { display: flex; align-items: center; justify-content: center; gap: 10px; }
      .analysis-loading-dots span {
        width: 10px; height: 10px; border-radius: 999px; background: #94a3b8;
        animation: gaemiLoadingDot 1.15s ease-in-out infinite;
      }
      .analysis-loading-dots span:nth-child(2) { animation-delay: .10s; }
      .analysis-loading-dots span:nth-child(3) { animation-delay: .20s; }
      .analysis-loading-dots span:nth-child(4) { animation-delay: .30s; }
      .analysis-loading-dots span:nth-child(5) { animation-delay: .40s; }
      .analysis-loading-dots span:nth-child(6) { animation-delay: .50s; }
      .analysis-loading-message {
        display: none; font-size: 1rem; font-weight: 800; letter-spacing: -.02em;
      }
      .analysis-loading-message.is-visible { display: inline-block; }
      .analysis-loading-message.is-shimmer {
        color: transparent;
        background: linear-gradient(90deg, #64748b 0%, #64748b 34%, #e2e8f0 50%, #64748b 66%, #64748b 100%);
        background-size: 220% 100%; background-clip: text; -webkit-background-clip: text;
        animation: gaemiLoadingShimmer 1.45s linear infinite;
      }
      .dark .analysis-loading-message.is-shimmer {
        background-image: linear-gradient(90deg, #a1a1aa 0%, #a1a1aa 34%, #f4f4f5 50%, #a1a1aa 66%, #a1a1aa 100%);
      }
      @keyframes gaemiLoadingDot {
        0%, 60%, 100% { opacity: .28; transform: translateY(0) scale(.82); }
        30% { opacity: 1; transform: translateY(-4px) scale(1); }
      }
      @keyframes gaemiLoadingShimmer {
        from { background-position: 120% 0; }
        to { background-position: -120% 0; }
      }
    `;
    document.head.appendChild(style);

    let flowToken = 0;
    let activeFlow = null;
    const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

    function createFlow(stockName, token) {
      const chatArea = document.getElementById('chatArea');
      if (!chatArea) return null;

      // 기존 로딩 카드만 숨기고 사용자 입력 말풍선과 결과 영역은 그대로 둔다.
      const oldLoader = Array.from(chatArea.children).find(el =>
        el.classList.contains('flex-col') &&
        el.classList.contains('items-center') &&
        el.classList.contains('justify-center') &&
        el.classList.contains('rounded-3xl')
      );
      if (oldLoader) oldLoader.style.display = 'none';

      const stage = document.createElement('div');
      stage.className = 'analysis-loading-sequence animate-fade';
      stage.innerHTML = `
        <div class="analysis-loading-dots" aria-label="분석 준비 중">
          <span></span><span></span><span></span><span></span><span></span><span></span>
        </div>
        <div class="analysis-loading-message" aria-live="polite"></div>`;
      chatArea.appendChild(stage);

      return {
        token,
        stockName,
        el: stage,
        dots: stage.querySelector('.analysis-loading-dots'),
        message: stage.querySelector('.analysis-loading-message'),
        ready: false,
        release: null,
        promise: null,
      };
    }

    function showMessage(flow, text) {
      if (!flow?.el?.isConnected) return;
      flow.dots.hidden = true;
      flow.message.textContent = text;
      flow.message.classList.add('is-visible', 'is-shimmer');
    }

    async function play(flow) {
      await sleep(STAGE_MS);
      if (flow.token !== flowToken) return;
      showMessage(flow, '시세를 조회중입니다...');

      await sleep(STAGE_MS);
      if (flow.token !== flowToken) return;
      showMessage(flow, `${flow.stockName} 오늘의 흐름을 정리하고 있습니다...`);

      await sleep(STAGE_MS);
      if (flow.token !== flowToken) return;
      flow.ready = true;
      flow.release?.();
    }

    window.requestStock = function (stockName) {
      const token = ++flowToken;
      const normalized = String(stockName || '').trim() || '삼성전자';

      // 원래 분석/데이터 흐름을 먼저 시작하고, 그 위의 출력 연출만 교체한다.
      const originalResult = originalRequestStock.call(this, stockName);
      activeFlow?.el?.remove();
      activeFlow = createFlow(normalized, token);

      if (activeFlow) {
        activeFlow.promise = new Promise(resolve => { activeFlow.release = resolve; });
        play(activeFlow);

        // 기존 오류 화면은 그대로 즉시 사용할 수 있게 로딩 연출만 정리한다.
        const chatArea = document.getElementById('chatArea');
        const observer = new MutationObserver(() => {
          if (chatArea?.querySelector('.analysis-state')) {
            activeFlow?.el?.remove();
            if (activeFlow?.token === token) activeFlow = null;
            observer.disconnect();
          }
        });
        if (chatArea) observer.observe(chatArea, { childList: true, subtree: true });
        setTimeout(() => observer.disconnect(), 30000);
      }

      return originalResult;
    };

    window.startTypewriterFlow = async function (stockName, sections, result, requestId) {
      const flow = activeFlow;
      if (flow && flow.token === flowToken && !flow.ready) await flow.promise;
      if (flow && flow.token === flowToken) {
        flow.el?.remove();
        activeFlow = null;
      }
      return originalStartTypewriterFlow.call(this, stockName, sections, result, requestId);
    };
  }

  // app.js is loaded after this file. DOMContentLoaded runs only after the
  // following classic scripts have finished, so the functions to wrap exist
  // on both cached and uncached loads.
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', installLoadingPresentation, { once: true });
  } else {
    installLoadingPresentation();
  }
}());
