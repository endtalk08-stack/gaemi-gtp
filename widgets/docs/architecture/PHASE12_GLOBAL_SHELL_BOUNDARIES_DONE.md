# Phase 12 — Global Shell Boundaries

이번 단계에서는 화면에 보이는 새 기능을 추가하지 않고 큰 영역의 경계를 명시했다.

## 확정한 큰 구도
- left-nav-rail: 어떤 사이드바를 열지 선택하는 진입점
- left-market-sidebar: 실시간/순위/거래대금/산업/테마 등 시장정보
- left-context-sidebar: 관심종목/최근본 등 개인화
- main: 중앙 Workspace와 central widget dock
- right-panel: 탭 → 페이지 → 위젯

## 중요한 경계
시장정보와 개인화 사이드바를 섞지 않는다.
중앙 Workspace와 오른쪽 패널의 위젯 배치는 서로 독립한다.
실제 데이터/API/DB 연결은 구조 확정 이후 한 단계씩 진행한다.

## 이번 단계에서 하지 않은 것
- 기존 DOM 이동
- API 변경
- DB 변경
- 실제 위젯 데이터 연결
- 디자인 재작업
