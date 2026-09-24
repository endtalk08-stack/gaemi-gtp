# Left Context Sidebar

왼쪽 세로 레일에서 호출하는 별도 사이드바 영역이다.

## 이번 단계
- 관심종목 영역의 자리만 제공
- 최근 본 종목 영역의 자리만 제공
- 시장정보 사이드바와 열림 상태를 분리
- 모바일에서는 왼쪽 컨텍스트를 열 때 오른쪽 패널을 숨김

## 아직 하지 않는 것
- 관심종목 저장/삭제 실제 기능
- 최근 본 종목 DB 저장
- 로그인/계정 연결
- API/DB 연결

## v7.11

The sidebar shell owns open/close state. The `내 종목` content is mounted by `pages/watchlist/watchlist.js`, keeping the shell and page content separate.
