/* gaemiGTP Widget Catalog — metadata only.
   Shared by central Workspace and right Panel.
   No API, DB, calculation, or rendering logic belongs here.
*/
(function () {
  'use strict';

  window.GaemiGTPWidgetCatalog = Object.freeze({
    'why-up':    { title: '왜 올랐을까?', icon: 'sparkles', description: '가격 변동 요인' },
    'materials': { title: '재료는 있어?', icon: 'newspaper', description: '관련 뉴스·공시·재료' },
    'chart':     { title: '차트', icon: 'chart-candlestick', description: '가격 흐름' },
    'volume':    { title: '거래량', icon: 'chart-column', description: '거래량 흐름' },
    'trading-value': { title: '거래대금', icon: 'wallet', description: '거래대금 흐름' },
    'news':      { title: '뉴스', icon: 'newspaper', description: '핵심 뉴스' },
    'economic':  { title: '경제일정', icon: 'calendar-days', description: '주요 경제 일정' },
    'earnings':  { title: '실적', icon: 'file-chart-column', description: '실적 일정·결과' },
    'event':     { title: '이벤트', icon: 'zap', description: '시장 이벤트' },
    'ranking':   { title: '순위', icon: 'trophy', description: '관련 종목 순위' },
  });
}());
