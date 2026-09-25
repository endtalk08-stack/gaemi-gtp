gaemiGTP NEWS CLEAN FIX v1

적용 파일 5개:
- backend/providers/naver_news.py
- backend/providers/google_news.py
- backend/services/news_feed.py
- frontend/widgets/news-widget.js
- frontend/shell/right-panel/right-panel-tabs.js

핵심:
- 별도 뉴스 탭 제거
- 대시보드 뉴스 위젯 하나만 사용
- iframe 제거 -> 패널 리사이즈 방해 없음
- 본문 기존 뉴스/재료와 연결 없음
- 외부사이트 공용 팝업 연결 없음
- '뉴스를 불러오는 중...' 문구 없음
- /news만 사용
- Naver/Google 병렬 수집 + 요청 수/timeout 축소
- 기존 localStorage에 남은 독립 뉴스 탭 자동 제거

주의:
- right-panel width/state 파일은 수정하지 않음.
- app.py, dashboard.js, 본문 app.js는 수정하지 않음.
