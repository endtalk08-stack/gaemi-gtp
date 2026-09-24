# gaemiGTP 구조 개편 1단계

이번 단계는 **기능 개발이 아니라 구조의 기준선을 만드는 단계**다.

## 반영
- LEFT NAV RAIL / LEFT MARKET SIDEBAR / MAIN / RIGHT PANEL을 서로 다른 Shell 영역으로 정의
- HOME / STOCK ANALYSIS / MARKET / DASHBOARD 페이지 영역 정의
- WIDGET 영역을 기능별 폴더로 정의
- DATA / CORE / ANALYSIS / API / BACKTEST / USER / ADMIN 영역 정의
- 현재 파일과 목표 위치 매핑표 추가
- 중복으로 확인된 `backend/app.py`, `backend/utils/app.py`, `backend/utils/backend/` 제거

## 의도적으로 하지 않음
- 현재 `frontend/index.html`과 `frontend/js/app.js`를 즉시 쪼개지 않음
- 현재 `backend/services/engine.py`를 즉시 분해하지 않음
- API/DB 동작 변경 없음
- 화면 기능 변경 없음

## 다음 단계
현재 파일 하나를 선택해서 목표 영역으로 이동하고, 이동 후 검증한다.
