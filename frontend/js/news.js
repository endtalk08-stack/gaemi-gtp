// gaemiGTP - 뉴스의 표시 위치를 오른쪽 패널로 일원화한다.
// 채팅 본문에는 기사 제목을 반복하지 않고, 흐름 키워드와 분석만 남긴다.
window.GaemiGTPNews = window.GaemiGTPNews || {};

window.GaemiGTPNews.renderArticles = async function ({ evidence }) {
  const sourceArticles = Array.isArray(evidence?.articles) ? evidence.articles : [];
  const matchedArticles = Array.isArray(evidence?.matchedArticles)
    ? evidence.matchedArticles
    : sourceArticles;

  // 오른쪽 패널은 전체 출처 목록을 담당한다. 채팅 중앙에는 같은 기사를
  // 다시 그리지 않는다. 최대 20개는 기존 패널의 읽기 좋은 목록 길이다.
  const panelArticles = sourceArticles.length ? sourceArticles.slice(0, 20) : matchedArticles.slice(0, 20);
  if (panelArticles.length && window.GaemiGTPRightPanelTabs?.showRelatedNews) {
    window.GaemiGTPRightPanelTabs.showRelatedNews(panelArticles);
  }

  // 관련 종목 계산은 기존처럼 상위의 분석 대상 기사로 유지한다.
  return matchedArticles.slice(0, 3);
};
