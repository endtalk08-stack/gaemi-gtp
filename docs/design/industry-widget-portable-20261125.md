# gaemiGTP 업종 플러그인 위젯 및 이동 구조 설계 (2026-11-25)

## 목적과 작업 경계

- `endtalk08-stack/gaemi-gtp`의 **업종** 화면을 플러그인 목록에서 선택할 수 있는 독립 위젯으로 추가한다.
- 먼저 업종 위젯 하나를 3개 영역(왼쪽 시장 사이드바, 중앙 위젯 독, 오른쪽 패널)에 **한 위치만 활성화**하는 이동 구조의 첫 적용 대상으로 삼는다. 다른 플러그인 위젯은 현행대로 둔다.
- **기존 업종 탭/시장/거래대금, DigitalOcean 키움 시세 서버, WebSocket, 거래 로직, 데이터베이스, 인증, Cloudflare Functions는 수정하지 않는다.**
- 변경은 이 실험 브랜치에서만 수행한다. **main 병합 및 운영 배포 금지** (별도 검토 뒤 결정).

## 기존 코드 확인

| 책임 | 파일 | 확인 결과 |
| --- | --- | --- |
| 왼쪽 업종 | `frontend/shell/left-market-sidebar/market-sidebar.js` | 내부 `renderIndustryMap` 및 `loadIndustryMap`이 `#marketRankingList`를 사용 |
| 플러그인 목록 | `frontend/widgets/catalog/catalog.js` | QQQ, SPY, DIA, 야간선물, 속보, 뉴스 |
| 플러그인 추가/삭제 | `frontend/shell/left-plugin-sidebar/plugin-sidebar.js` | `GaemiGTPWidgetDock.add/remove` 호출 |
| 중앙 독 | `frontend/shell/center-chat/widget-dock/widget-dock.js` | 위젯 ID를 로컬 상태로 저장하고 다시 렌더링 |
| 오른쪽 패널 | `frontend/shell/right-panel/right-panel-tabs.js` | 대시보드/공시 workspace view를 교체하는 구조 |

## 업종 데이터 계약 (기존 읽기 전용 API 재사용)

- 업종 및 시가총액별 종목: `GET https://quotes.gaemigtp.com/market/us-industries?include_stocks=1&view=heatmap`
- 업종 ETF 등락률: `GET https://quotes.gaemigtp.com/market/us-industry-etf-quotes`
- 기존 11개 대분류 ETF: `XLK, XLV, XLF, XLY, XLC, XLI, XLP, XLE, XLU, XLRE, XLB`
- 기존 보조 3개 ETF: `SOXX`(반도체), `XBI`(바이오), `IBIT`(비트코인)
- **실시간 %는 ETF 응답의 `change_pct`를 그대로 사용**한다. 키움 시세 기준일과 장시간 전환 로직을 위젯에서 재계산하지 않는다.
- 각 업종의 종목 후보는 기존 키움 업종 코드에 연결된 시가총액순 상위 종목에서 3개를 선택하고, 표시 순서만 등락률순으로 정한다.
- 최초 읽기 실패 시 값 임의 생성 금지; 마지막 정상 조회값이 있으면 유지하고 읽기 대기 상태를 표시한다.
- 이 위젯은 기존 업종 탭을 폐기/교체하지 않는다. 초기에 왼쪽 배치일 때는 기존 업종 탭 자리에서 독립 위젯을 표시하여 화면 중복을 피한다.

## 3영역 배치 구조: 첫 구현

```text
Plugin Catalog [industry]
            |
GaemiGTPWidgetDock.add/remove  (설치 여부)
            |
IndustryWidget Controller (배치: left | center | right)
            |
       단 하나의 DOM 위젯
          /      |      \
 left: 업종 탭   center: WidgetDock   right: 패널 '업종' 뷰
```

- 위젯 상단의 **왼쪽 / 중앙 / 오른쪽** 버튼으로 이동한다.
- **왼쪽:** 기존 시장 사이드바의 업종 탭 자리에서 위젯을 표시한다. 시장/거래대금 탭을 누르면 종전 목록으로 전환한다.
- **중앙:** `centralWidgetDockBody`에 전체 가로폭의 위젯 카드로 배치한다.
- **오른쪽:** 기존 오른쪽 패널의 메뉴에 `업종` 항목만 추가, 대시보드/공시를 유지한다.
- 위치를 바꿀 때 **같은 위젯 DOM 노드를 이동**해 스크롤/선택 상태를 가능한 보존한다.
- 플러그인에서 삭제하면 3영역에서 제거하고 기존 시장 목록을 복원한다.
- 위치는 레이아웃 설정만 로컬 저장소에 기록한다. **PC-모바일 동기화는 이번 단계에 포함되지 않음**; 서버 계정 설정 도입은 별도 설계가 필요하다.

## 갱신 및 성능

- 위젯 인스턴스당 타이머/요청은 하나만, 다른 영역에 복제하거나 새 WebSocket을 만들지 않는다.
- 화면이 보이지 않거나 브라우저가 숨겨지면 주기적 조회를 건너뛰고, 다시 보일 때 갱신한다.
- 서버가 보내는 ETF 등락률/기준일을 신뢰하고 위젯 자체에서 별도 % 계산 금지.
- 기존 왼쪽 시장 사이드바 조회와 위젯 전용 REST 조회는 **초기 단계에서 독립**이다. 동일 시각 양쪽에서 요청이 발생할 수 있어, 장기적으로 공유 읽기 캐시를 검토한다.

## 검증 계획

1. 플러그인 목록에 `업종`이 나타나는지 확인.
2. 중앙에 추가 → 실제 업종 11개 + 보조 3개와 관련 종목, 시세 상태 확인.
3. 중앙 → 오른쪽 → 왼쪽 → 중앙 이동, 단일 인스턴스/상태/스크롤 보존 확인.
4. 왼쪽에 배치한 상태에서 시장·거래대금·업종 탭 전환 후 기존 목록 복구 확인.
5. 플러그인 삭제/새로고침 후 복원 확인.
6. ETF 시세 누락·네트워크 장애·미국 장 마감 시 마지막 정상값 처리 확인.
7. 모바일 폭에서 전체 가로 스크롤/패널 겹침, 중앙 뉴스·채팅·HTS 비침범 확인.
8. `node --check` / 기존 Pages 검증/프리뷰 점검 후 별도 승인 시 병합.

## 향후 전체 플러그인 확장

- 성공하면 개별 위젯 데이터 제공자는 그대로 두고 `widgetId → placement`만 관리하는 공통 배치 매니저로 이전한다.
- 위젯의 `mount` / `unmount` / `refresh` / `suspend`를 공통 인터페이스로 추상화한다.
- QQQ/뉴스/차트 등은 각 데이터 소스와 구독을 공유하며 **위젯 이동 때문에 시세 WebSocket이 중복 연결되지 않도록** 테스트한다.
- 운영 배포는 이 설계와 검증에 대한 사용자의 별도 결정 후 수행한다.
