# PANEL WORKSPACE

오른쪽 전체 패널(`shell/right-panel`)과 구분되는 **독립 12그리드 작업공간**입니다.

- `right-panel`: 오른쪽 전체 패널 껍데기
- `panel-workspace`: `…` 메뉴에서 선택해 여는 위젯 작업공간
- `panel-grid`: 작업공간 내부 12그리드
- `widget`: 그리드에 배치되는 독립 위젯

뉴스/공시/API/DB/중앙 채팅은 이 폴더의 책임이 아닙니다.

기존 `pages/dashboard/` 파일은 현재 `index.html`의 기존 로딩 경로와 이전 전역 객체 호환을 위해 얇은 호환 레이어로만 남겨 둡니다. 새 작업은 이 폴더에서 진행합니다.
