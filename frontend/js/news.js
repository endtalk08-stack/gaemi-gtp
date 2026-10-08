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
  // 뉴스는 분석이 끝났다고 패널을 강제로 열지 않는다. 사용자가 오른쪽
  // 패널 메뉴의 '뉴스'를 열면 AnalysisData에서 이 목록을 읽어 표시한다.
  // 관련 종목 계산은 기존처럼 상위의 분석 대상 기사로 유지한다.
  return matchedArticles.slice(0, 3);
};
