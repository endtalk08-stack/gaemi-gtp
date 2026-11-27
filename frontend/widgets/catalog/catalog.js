/* gaemiGTP Widget Catalog — metadata only.
   Shared by central Workspace and right Panel.
   No API, DB, calculation, or rendering logic belongs here.
*/
(function () {
  'use strict';

  window.GaemiGTPWidgetCatalog = Object.freeze({
    'qqq': { title: 'QQQ', icon: 'chart-no-axes-combined', description: '나스닥100 ETF 실시간 시세' },
    'spy': { title: 'SPY', icon: 'chart-no-axes-combined', description: 'S&P 500 ETF 실시간 시세' },
    'dia': { title: 'DIA', icon: 'chart-no-axes-combined', description: '다우 ETF 실시간 시세' },
    'night-futures': { title: '코스피200 야간선물', icon: 'moon-star', description: '야간 선물 흐름' },
    'news-caption': { title: '속보', icon: 'radio-tower', description: '한 줄 뉴스 제목 자막' },
    'news-feed': { title: '뉴스', icon: 'newspaper', description: '검색·분류별 뉴스 피드' },
    'industry': { title: '업종', icon: 'layout-grid', description: '업종 ETF 등락률 및 시가총액 상위 종목' },
    'chart': { title: '차트', icon: 'chart-candlestick', description: '선택 종목의 키움 일봉 차트' },
  });
}());
