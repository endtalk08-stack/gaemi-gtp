# Phase 8 — Workspace + Left Context Blueprint

이번 단계는 **큰 화면 구도와 역할 분리**만 확정한다.
실제 주가/API/DB/세부 위젯 기능은 변경하지 않는다.

## 1. 중앙 Workspace

```text
Main Workspace
└── Widget Dock
    └── + 위젯 추가
        ├── 왜 올랐을까?
        ├── 재료는 있어?
        ├── 차트
        ├── 뉴스
        ├── 거래량
        └── 거래대금 ...
```

중앙은 대화/분석 영역을 유지하면서 필요한 분석 위젯을 추가할 수 있는 방향으로 확장한다.

## 2. 오른쪽 패널과의 관계

```text
공통 Widget Catalog
        ├── 중앙 Workspace
        └── 오른쪽 Panel / Tab
```

같은 위젯을 사용할 수 있지만, 각 영역의 배치와 화면 상태는 독립적으로 관리한다.

## 3. 왼쪽 영역

```text
Left Nav Rail
├── Market Info → Left Market Sidebar
├── Context     → Left Context Sidebar
│                 ├── 관심종목
│                 └── 최근 본 종목
└── User/Settings
```

시장정보와 개인화 영역을 섞지 않는다.
세로 레일 아이콘을 눌러 다른 사이드바가 열리는 구조를 기본 방향으로 예약한다.

## 이번 단계에서 하지 않는 것

- 실제 관심종목 저장
- 최근 본 종목 저장
- 중앙 위젯 실제 구현
- 위젯 추가/삭제 세부 UI
- API/DB 연결
- 로그인/인증 구현
- 기존 화면 동작 변경
