# gaemiGTP 패널 레이아웃 수정본

PC: 패널은 드래그로 최대 1,200px까지 조절하고, 패널 헤더의 최대화 버튼을 누르면 왼쪽 시장정보 영역을 제외한 Workspace 전체를 사용합니다.

모바일: 패널을 열면 본문과 왼쪽 시장정보 영역을 숨기고 화면 전체(100dvw)를 사용합니다.

## Structure refactor baseline v7

A target architecture and one-by-one migration map are documented under `docs/architecture/`.
Runtime files are intentionally kept in place until each migration step is verified.


## v7.6 — Right Panel Page Containers

오른쪽 패널의 탭 화면을 Dashboard / Auto Trade / Custom Analysis 영역으로 분리했다.
현재 단계에서는 화면 컨테이너만 분리하며 데이터/API/DB/주문 실행 로직은 추가하지 않는다.


## v7.7 — Global Panel Layout Blueprint

중앙 Workspace, 왼쪽 레일/컨텍스트 사이드바, 오른쪽 탭 패널의 큰 구조를 확장할 자리를 마련했다.
중앙의 `+` 위젯 추가와 왼쪽 레일 기반 관심/최근본 사이드바는 구조만 예약하며 실제 데이터/세부 동작은 다음 단계에서 진행한다.


## v7.11 — Left Context Page Boundary

왼쪽 `내 종목` 컨텍스트 사이드바의 외곽 셸과 관심종목/최근 본 종목 콘텐츠를 분리했다.
현재는 화면 구조만 분리하며 저장/DB/API 연결은 추가하지 않는다.
