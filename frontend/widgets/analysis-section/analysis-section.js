/* Analysis Section Widgets
   Each widget reads only the data it owns from GaemiGTPAnalysisData. */
(function () {
  'use strict';
  const SECTION_BY_WIDGET = { supply: 'supply', levels: 'levels', economic: 'calendar' };
  function escapeHtml(value) { return String(value || '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#039;'); }
  function empty(root, message) { root.innerHTML = `<div class="analysis-section-widget__empty">${escapeHtml(message)}</div>`; }
  function renderSection(root, section) { if (!section) { empty(root, '종목을 분석하면 이 위젯에 표시됩니다.'); return; } root.innerHTML = `<div class="analysis-section-widget__title">${escapeHtml(section.title)}</div><p class="analysis-section-widget__content">${escapeHtml(section.content)}</p>`; }
  function renderMaterials(root, data) {
    const items = [...data.newsItems, ...data.disclosures, ...data.usFilings].slice(0, 5);
    if (!items.length) { empty(root, '종목을 분석하면 관련 뉴스와 공시가 표시됩니다.'); return; }
    root.innerHTML = `<div class="analysis-section-widget__list">${items.map(item => `<div class="analysis-section-widget__row"><strong>${escapeHtml(item.title || item.description || '제목 확인 필요')}</strong><span>${escapeHtml(item.source || (item.form ? 'SEC' : '출처 확인 필요'))}</span></div>`).join('')}</div>`;
  }
  function mount(widgetId, root) {
    if (!root) return;
    if (widgetId === 'why-up') { root.classList.add('analysis-section-widget__why-up'); root.innerHTML = window.GaemiGTPWhyUpContent?.render?.('widget') || ''; return; }
    const data = window.GaemiGTPAnalysisData?.get?.();
    if (!data) { empty(root, '분석 데이터를 준비하고 있습니다.'); return; }
    if (widgetId === 'materials') { renderMaterials(root, data); return; }
    const sectionId = SECTION_BY_WIDGET[widgetId]; if (sectionId) renderSection(root, data.sections[sectionId]);
  }
  window.GaemiGTPAnalysisWidgets = { mount };
}());

/* Analysis loading presentation + central scored-news explanation. */
(function () {
  'use strict';
  const STAGE_MS = 4000;
  const NEWS_FLOW_URL = 'https://gaemi-gtp.onrender.com/news/stock-flow';
  let latestWhyContext = null;

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
    const tonePriority = tone => priceState === 'positive' ? (tone === 'positive' ? 0 : tone === 'negative' ? 2 : 1) : priceState === 'negative' ? (tone === 'negative' ? 0 : tone === 'positive' ? 2 : 1) : (tone === 'positive' || tone === 'negative' ? 0 : 1);
    rows.forEach(item => {
      const signals = Array.isArray(item.movement_signals) ? [...item.movement_signals] : [];
      signals.sort((a, b) => tonePriority(a?.tone) - tonePriority(b?.tone) || (scoreByLabel.get(String(b?.label || '').trim()) || 0) - (scoreByLabel.get(String(a?.label || '').trim()) || 0));
      item.movement_signals = signals;
      const matching = signals.filter(signal => priceState === 'positive' ? signal?.tone === 'positive' : priceState === 'negative' ? signal?.tone === 'negative' : signal?.tone === 'positive' || signal?.tone === 'negative');
      item._whyMatch = matching.length ? 1 : 0;
      item._whyEvidence = matching.reduce((best, signal) => Math.max(best, scoreByLabel.get(String(signal?.label || '').trim()) || 0), 0);
    });
    rows.sort((a, b) => (b._whyMatch - a._whyMatch) || (b._whyEvidence - a._whyEvidence) || ((b.flow_score || 0) - (a.flow_score || 0)));
    rows.forEach(item => { delete item._whyMatch; delete item._whyEvidence; });
    return rows;
  }

  function buildWhySummary(context) {
    const flow = context?.flow || {};
    const stock = context?.stockName || '이 종목';
    const state = context?.priceState || 'mixed';
    const positives = Array.isArray(flow.top_positive_signals) ? flow.top_positive_signals : [];
    const negatives = Array.isArray(flow.top_negative_signals) ? flow.top_negative_signals : [];
    const pos = positives[0]?.label || '';
    const neg = negatives[0]?.label || '';
    if (state === 'positive') {
      if (pos) return `${stock}가 오늘 강한 흐름을 보이는 데는 뉴스에서 반복해서 확인된 ‘${pos}’ 재료가 가장 눈에 띄어. 다만 ${neg ? `‘${neg}’ 같은 부담 재료도 함께 보여서` : '반대 방향 재료도 있을 수 있어서'} 관련 기사와 공시를 같이 확인하는 게 좋아.`;
      return `${stock}는 오늘 상승 중이지만, 현재 수집된 뉴스에서는 상승을 직접 설명할 강한 재료가 충분히 반복 확인되지는 않았어.`;
    }
    if (state === 'negative') {
      if (neg) return `${stock}가 오늘 약한 흐름을 보이는 데는 뉴스에서 반복해서 확인된 ‘${neg}’ 부담이 가장 눈에 띄어. ${pos ? `반대로 ‘${pos}’ 같은 긍정 재료도 함께 있어서` : '긍정 재료도 따로 확인하면서'} 하락 이유를 한쪽 재료만으로 단정하진 않는 게 좋아.`;
      return `${stock}는 오늘 하락 중이지만, 현재 수집된 뉴스에서는 하락을 직접 설명할 강한 재료가 충분히 반복 확인되지는 않았어.`;
    }
    if (pos && neg) return `${stock}가 보합권인 건 뉴스 흐름에서도 ‘${pos}’ 같은 긍정 재료와 ‘${neg}’ 같은 부담 재료가 함께 잡혀 서로 맞서는 모습이야.`;
    if (pos) return `${stock}는 보합권이지만 뉴스에서는 ‘${pos}’ 같은 긍정 재료가 보여. 아직 주가 방향을 확실히 만들 만큼 한쪽으로 쏠린 흐름은 아니야.`;
    if (neg) return `${stock}는 보합권이지만 뉴스에서는 ‘${neg}’ 같은 부담 재료가 보여. 아직 주가 방향을 확실히 만들 만큼 한쪽으로 쏠린 흐름은 아니야.`;
    return `${stock}는 현재 보합권이고, 뉴스에서도 한쪽 방향을 설명할 재료가 뚜렷하게 우세하지 않아.`;
  }

  function decorateWhyBlock(root) {
    if (!latestWhyContext || !root || root.dataset.scoredWhyApplied === 'true') return;
    const title = Array.from(root.querySelectorAll('p')).find(p => p.textContent === '눈에 띄는 흐름 있어 👀' || p.textContent === '오늘은 흐름 없음 ☁️');
    if (!title) return;
    root.dataset.scoredWhyApplied = 'true';
    title.textContent = latestWhyContext.priceState === 'positive' ? '오늘 상승 이유를 뉴스 흐름으로 보면 👀' : latestWhyContext.priceState === 'negative' ? '오늘 하락 이유를 뉴스 흐름으로 보면 👀' : '오늘 보합 이유를 뉴스 흐름으로 보면 👀';
    const summary = document.createElement('p');
    summary.className = 'text-base sm:text-lg text-[#334155] dark:text-[#e4e4e7] leading-relaxed whitespace-pre-line';
    summary.textContent = buildWhySummary(latestWhyContext);
    title.insertAdjacentElement('afterend', summary);

    const flow = latestWhyContext.flow || {};
    const issues = (flow.top_issues || []).slice(0, 3).map(item => item.label).filter(Boolean);
    const themes = (flow.top_themes || []).slice(0, 3).map(item => item.label).filter(Boolean);
    if (issues.length || themes.length) {
      const contextLine = document.createElement('p');
      contextLine.className = 'text-sm text-[#64748b] dark:text-[#a1a1aa] leading-7';
      const parts = [];
      if (issues.length) parts.push(`연관 이슈 · ${issues.join(' · ')}`);
      if (themes.length) parts.push(`관련 테마 · ${themes.join(' · ')}`);
      contextLine.textContent = parts.join('\n');
      summary.insertAdjacentElement('afterend', contextLine);
    }
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
      if (payload?.flow && typeof payload.flow === 'object') result.news_flow = { ...payload.flow, price_state: priceState };
      latestWhyContext = { stockName, priceState, flow: result.news_flow || {}, items: flowItems };
    } catch (_) {}
  }

  function installLoadingPresentation() {
    const originalRequestStock = window.requestStock;
    const originalStartTypewriterFlow = window.startTypewriterFlow;
    if (typeof originalRequestStock !== 'function' || typeof originalStartTypewriterFlow !== 'function' || window.__gaemiLoadingPresentationInstalled) return;
    window.__gaemiLoadingPresentationInstalled = true;

    const chatArea = document.getElementById('chatArea');
    if (chatArea) {
      const whyObserver = new MutationObserver(() => {
        chatArea.querySelectorAll('[data-why-flow]').forEach(prompt => {
          let node = prompt.nextElementSibling;
          while (node && !node.dataset?.replyActions && !node.dataset?.whyFollowupChoices) {
            decorateWhyBlock(node);
            node = node.nextElementSibling;
          }
        });
      });
      whyObserver.observe(chatArea, { childList: true, subtree: true });
    }

    const style = document.createElement('style');
    style.textContent = `#surpriseAntPopup{display:none!important}.analysis-loading-sequence{width:100%;min-height:92px;display:flex;flex-direction:column;align-items:flex-start;justify-content:center;padding:18px 8px;text-align:left}.analysis-loading-dots{display:flex;align-items:center;gap:10px}.analysis-loading-dots[hidden]{display:none}.analysis-loading-dots span{width:10px;height:10px;border-radius:999px;background:#94a3b8;animation:gaemiLoadingDot 1.15s ease-in-out infinite}.analysis-loading-dots span:nth-child(2){animation-delay:.10s}.analysis-loading-dots span:nth-child(3){animation-delay:.20s}.analysis-loading-dots span:nth-child(4){animation-delay:.30s}.analysis-loading-dots span:nth-child(5){animation-delay:.40s}.analysis-loading-dots span:nth-child(6){animation-delay:.50s}.analysis-loading-message{display:none;font-size:1rem;font-weight:800;letter-spacing:-.02em}.analysis-loading-message.is-visible{display:inline-block}.analysis-loading-message--secondary{margin-top:8px}.analysis-loading-message.is-shimmer{color:transparent;background:linear-gradient(90deg,#64748b 0%,#64748b 34%,#e2e8f0 50%,#64748b 66%,#64748b 100%);background-size:220% 100%;background-clip:text;-webkit-background-clip:text;animation:gaemiLoadingShimmer 1.45s linear infinite}.dark .analysis-loading-message.is-shimmer{background-image:linear-gradient(90deg,#a1a1aa 0%,#a1a1aa 34%,#f4f4f5 50%,#a1a1aa 66%,#a1a1aa 100%)}@keyframes gaemiLoadingDot{0%,60%,100%{opacity:.28;transform:translateY(0) scale(.82)}30%{opacity:1;transform:translateY(-4px) scale(1)}}@keyframes gaemiLoadingShimmer{from{background-position:120% 0}to{background-position:-120% 0}}`;
    document.head.appendChild(style);

    let flowToken = 0, activeFlow = null;
    const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
    function createFlow(stockName, token) {
      const area = document.getElementById('chatArea'); if (!area) return null;
      const oldLoader = Array.from(area.children).find(el => el.classList.contains('flex-col') && el.classList.contains('items-center') && el.classList.contains('justify-center') && el.classList.contains('rounded-3xl'));
      if (oldLoader) oldLoader.style.display = 'none';
      const stage = document.createElement('div'); stage.className = 'analysis-loading-sequence animate-fade';
      stage.innerHTML = `<div class="analysis-loading-dots"><span></span><span></span><span></span><span></span><span></span><span></span></div><div class="analysis-loading-message"></div><div class="analysis-loading-message analysis-loading-message--secondary"></div>`; area.appendChild(stage);
      return { token, stockName, el:stage, dots:stage.querySelector('.analysis-loading-dots'), primaryMessage:stage.querySelector('.analysis-loading-message'), secondaryMessage:stage.querySelector('.analysis-loading-message--secondary'), ready:false, release:null, promise:null };
    }
    function showMessage(flow, message, text) { if (!flow?.el?.isConnected || !message) return; message.textContent = text; message.classList.add('is-visible','is-shimmer'); }
    async function play(flow) { await sleep(STAGE_MS); if(flow.token!==flowToken)return; flow.dots.hidden=true; showMessage(flow,flow.primaryMessage,'시세를 조회중입니다'); await sleep(STAGE_MS); if(flow.token!==flowToken)return; showMessage(flow,flow.secondaryMessage,`${flow.stockName} 흐름을 체크중입니다`); await sleep(STAGE_MS); if(flow.token!==flowToken)return; flow.ready=true; flow.release?.(); }
    window.requestStock = function(stockName) {
      latestWhyContext = null;
      const token=++flowToken, normalized=String(stockName||'').trim()||'삼성전자'; const originalResult=originalRequestStock.call(this,stockName); activeFlow?.el?.remove(); activeFlow=createFlow(normalized,token);
      if(activeFlow){activeFlow.promise=new Promise(resolve=>{activeFlow.release=resolve});play(activeFlow);const area=document.getElementById('chatArea');const observer=new MutationObserver(()=>{if(area?.querySelector('.analysis-state')){activeFlow?.el?.remove();if(activeFlow?.token===token)activeFlow=null;observer.disconnect()}});if(area)observer.observe(area,{childList:true,subtree:true});setTimeout(()=>observer.disconnect(),30000)} return originalResult;
    };
    window.startTypewriterFlow = async function(stockName,sections,result,requestId){const flow=activeFlow;if(flow&&flow.token===flowToken&&!flow.ready)await flow.promise;if(flow&&flow.token===flowToken){flow.el?.remove();activeFlow=null}await loadCentralNewsFlow(String(stockName||'').trim(),result,sections);return originalStartTypewriterFlow.call(this,stockName,sections,result,requestId)};
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',installLoadingPresentation,{once:true});else installLoadingPresentation();
}());
