# Phase 2.1 — Right Panel Shell 분리 완료

## 이번 단계
- 오른쪽 패널의 배치/폭/리사이즈 CSS를 `frontend/shell/right-panel/right-panel.css`로 분리
- 오른쪽 패널의 폭 계산/리사이즈 컨트롤을 `frontend/shell/right-panel/right-panel.js`로 분리
- 기존 `app.js`는 호환용 wrapper만 남김
- 기존 HTML의 `onclick` 및 상태 로직은 유지
- 가운데 본문 데이터/API는 수정하지 않음

## 아직 하지 않은 것
- Dashboard 실제 기능/데이터 연결
- 위젯 실제 연결
- DATA/ANALYSIS/API/DB 이동

## 다음 단계
Dashboard 컨테이너와 위젯 배치/책임을 화면 수준에서 확정한 뒤 실제 내용을 하나씩 추가한다.
