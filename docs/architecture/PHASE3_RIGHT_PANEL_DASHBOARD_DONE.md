# PHASE 3 — Right Panel Dashboard Container

## 적용 범위
- 오른쪽 패널 내부에 `rightPanelDashboard` 독립 컨테이너 추가
- Dashboard 전용 CSS/JS 분리
- 위젯 슬롯 9개만 배치
- 기존 패널 열기/닫기/최대화/리사이즈 로직 유지
- 중앙 화면, API, DB, 데이터 수집/분석 로직은 변경하지 않음

## 새 파일
- `frontend/pages/dashboard/dashboard.css`
- `frontend/pages/dashboard/dashboard.js`

## 기존 유지
- `frontend/shell/right-panel/right-panel.css`
- `frontend/shell/right-panel/right-panel.js`
- `frontend/js/app.js`의 Workspace 상태 복원/패널 상태 전환

## 다음 단계
Dashboard 내부의 각 위젯을 하나씩 독립 파일로 연결합니다. 데이터/API/DB 연결은 위젯 구조가 확정된 뒤 별도 단계에서 진행합니다.
