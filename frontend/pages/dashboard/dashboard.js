/* Dashboard Page Container — v7.3
   책임: Dashboard라는 화면 컨테이너와 독립 위젯 슬롯만 구성한다.
   데이터/API/DB/분석/자동매매 로직은 담당하지 않는다.
*/
(function () {
  'use strict';

  const WIDGET_SLOTS = [
    { id: 'market-state', title: '시장 상태', icon: 'activity', description: '시장 상태 위젯 영역', widgetKey: 'market-state' },
    { id: 'chart', title: '차트', icon: 'chart-candlestick', description: '차트 위젯 영역' },
    { id: 'volume', title: '거래량', icon: 'bar-chart-3', description: '거래량 위젯 영역' },
    { id: 'trading-value', title: '거래대금', icon: 'wallet', description: '거래대금 위젯 영역' },
    { id: 'news', title: '뉴스', icon: 'newspaper', description: '뉴스 위젯 영역' },
    { id: 'economic', title: '경제일정', icon: 'calendar-days', description: '경제일정 위젯 영역' },
    { id: 'earnings', title: '실적', icon: 'badge-dollar-sign', description: '실적 위젯 영역' },
    { id: 'event', title: '이벤트', icon: 'zap', description: '이벤트 위젯 영역' },
    { id: 'ranking', title: '순위', icon: 'trophy', description: '순위 위젯 영역' },
  ];

  function createSlot(slot) {
    const article = document.createElement('article');
    article.className = 'dashboard-widget-slot';
    article.dataset.widgetSlot = slot.id;
    article.innerHTML = `
      <div class="dashboard-widget-slot__head">
        <span class="dashboard-widget-slot__icon" aria-hidden="true">
          <i data-lucide="${slot.icon}" class="w-4 h-4"></i>
        </span>
        <span class="dashboard-widget-slot__title">${slot.title}</span>
      </div>
      <div class="dashboard-widget-slot__body">${slot.description}</div>
      <div class="dashboard-widget-slot__mount"></div>
    `;

    const widget = slot.widgetKey && window.GaemiGTPWidgets
      ? window.GaemiGTPWidgets[slot.widgetKey]
      : null;
    if (widget && typeof widget.mount === 'function') {
      widget.mount(article.querySelector('.dashboard-widget-slot__mount'));
      article.classList.add('dashboard-widget-slot--mounted');
    }

    return article;
  }

  function mount() {
    const root = document.getElementById('rightPanelDashboard');
    if (!root || root.dataset.dashboardMounted === 'true') return;

    root.innerHTML = `
      <div class="right-panel-dashboard__head">
        <div>
          <h2 class="right-panel-dashboard__title">대시보드</h2>
          <p class="right-panel-dashboard__subtitle">독립 위젯을 배치하는 화면 영역</p>
        </div>
        <span class="right-panel-dashboard__status">구조 준비</span>
      </div>
      <section class="right-panel-dashboard__grid" aria-label="대시보드 위젯 영역"></section>
    `;

    const grid = root.querySelector('.right-panel-dashboard__grid');
    WIDGET_SLOTS.forEach((slot) => grid.appendChild(createSlot(slot)));

    root.dataset.dashboardMounted = 'true';
    if (window.lucide) window.lucide.createIcons();
  }

  window.GaemiGTPDashboard = {
    mount,
    widgetSlots: WIDGET_SLOTS.map((slot) => ({ ...slot })),
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount, { once: true });
  } else {
    mount();
  }
})();
