# Phase 4 — Right Panel First Widget Independent

이번 단계에서는 기존 v7.3 Dashboard의 **시장 상태** 카드만 독립 위젯으로 분리했다.

## 변경 범위
- `frontend/widgets/market-state/market-state.js`
- `frontend/widgets/market-state/market-state.css`
- `frontend/widgets/market-state/README.md`
- `frontend/pages/dashboard/dashboard.js`
- `frontend/pages/dashboard/dashboard.css`
- `frontend/index.html`

## 유지한 것
- 오른쪽 패널 열기/닫기
- 최대화/복원
- 패널 리사이즈
- 모바일 전체화면 동작
- 새로고침 상태 복원
- 왼쪽 시장정보 패널
- 중앙 화면
- 기존 API/DB/분석 코드

## 의도
Dashboard는 **배치 담당**, 실제 위젯은 **자기 표시 담당**으로 분리한다.

이번 단계에서는 데이터/API/DB 연결을 하지 않는다.
