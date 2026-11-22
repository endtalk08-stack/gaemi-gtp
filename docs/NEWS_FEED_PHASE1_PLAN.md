# 뉴스피드 1단계 계획 (확정)

작성일: 2026-11-22. 이 문서는 뉴스피드 기능의 기준 문서다. 이후 작업은 이 문서를 기준으로 진행하고,
범위를 바꾸려면 먼저 이 문서를 수정한 뒤에 코드를 바꾼다.

## 배경

- 지금까지 네이버 뉴스 최신 기사 6개를 모아 "왜 올랐을까"를 물어보면 품질이 꽤 좋았다.
- 문제는 상승→하락처럼 방향이 바뀔 때마다 다시 분석해야 하는데, 매번/상시로 돌리면 비용이 커진다.
- 그래서 "정기 스케줄 + 의미 있는 방향 전환 시에만" 트리거하는 구조로 비용을 통제한다.
- 사이트는 몇 달간 이것저것 시도하며 복잡해졌다. 이 문서는 지금 당장 켤 1단계 범위만 못박고,
  나머지는 이름만 정의해두고 손대지 않는다.

## 데이터 저장

- **Neon (Postgres)** — 전체 이력 저장. 분석 결과를 종목·시각별로 쌓아서, 중복 분석 방지와
  디버깅(언제 무슨 근거로 이렇게 말했는지 추적)에 쓴다.
- **R2 (Cloudflare)** — "지금 최신 피드" 스냅샷 1개 JSON (`news/feed-latest.json`)을 올려두고,
  Cloudflare Pages Function이 Neon을 거치지 않고 R2에서 바로 읽어 프론트에 서빙한다.
  (기존 `functions/market/qqq-reason.js`가 이미 `env.DATA_R2.get('news/latest.json')` 패턴을
  쓰고 있어서, 같은 방식을 그대로 따른다. 키 이름만 `news/feed-latest.json`으로 분리.)

## 트리거 조건 (비용 통제)

1. **정기 스케줄**: 하루 3회 고정 시각 — 장전 / 점심 / 마감 직전. (정확한 시각은 구현 시 확정)
2. **방향 전환 이벤트**: 종목의 등락 부호가 바뀌고(+→- 또는 -→+), 그 방향으로 추가로
   **0.5%p 이상** 움직였을 때만 트리거. 단순 부호 전환만으로는 트리거하지 않는다.
3. **쿨다운**: 같은 종목은 최소 **20분** 안에는 재트리거하지 않는다. (부호가 그 사이 여러 번
   바뀌어도 무시)
4. 실행 위치: **GitHub Actions** (무료, 레포에 이미 비슷한 패턴의 워크플로우가 많음).

## 1단계 실제 구현 범위

- 카테고리는 **`ai_stock_analysis` 하나만** 실제로 채운다.
- 흐름: 키움 시세로 트리거 조건 판정(비용 없음) → 조건 충족 시 네이버 뉴스 최신 6개(제목+description)
  수집 → 기존 `backend/services/worker_ai_lab.py`의 `ISSUE_PROMPT`를 그대로 재사용해 Groq
  (`openai/gpt-oss-20b`) 호출 → `{"issues":[{"headline","summary","direction","tags","source_ids"}]}`
  형태 JSON 응답 → Neon에 이력 저장 + R2 스냅샷 갱신.
- 프롬프트의 "근거 뉴스가 없으면 재료를 만들지 않는다" 원칙을 그대로 유지한다 (허위 인과관계 방지).

## 피드 공통 스키마 (지금부터 이 형태로 고정)

```json
{
  "id": "string",
  "created_at": "ISO8601",
  "day_phase": "pre_market | market_open | intraday | market_close",
  "category": "ai_stock_analysis | ai_market_analysis | econ_indicator | analyst_opinion | earnings | notable_stock | condition_search",
  "ticker": "string | null",
  "headline": "string",
  "summary": "string",
  "direction": "up | down | null",
  "tags": ["string"],
  "source_ids": ["number"]
}
```

- `day_phase`, `category` 값 중 **지금 실제로 쓰는 건 `market_open` / `intraday` + `ai_stock_analysis`
  뿐**이다. 나머지 값은 이름만 정의해두고 2·3단계에서 그대로 채워 넣는다 (스키마 재설계 불필요).
- `tags`는 AI가 생성하는 자유 해시태그를 그대로 쓴다 (`#핵심키워드` 형태). 고정된 카테고리
  체계를 새로 만들 필요 없음 — 나중에 태그 필터 UI를 붙이고 싶으면 이 필드를 그대로 쓰면 된다.

## 다음 단계 (지금은 손대지 않음)

| day_phase | category | 상태 |
|---|---|---|
| pre_market | econ_indicator | 미착수 |
| pre_market | analyst_opinion | 미착수 |
| pre_market | earnings | 미착수 |
| market_open | ai_market_analysis | 미착수 |
| intraday | notable_stock | 미착수 (키움 조건검색식 자체가 아직 없음) |
| intraday | condition_search | 미착수 |
| — | 트레이딩뷰/Wabble 뉴스 | 결제 미결정, 보류 |

## 프론트엔드 — News 페이지 (지금 비어있는 탭)

참고 레퍼런스: 증권플러스(속보/주요뉴스), 종목뉴스 태그 필터 화면, 이 레포 데모
아티팩트(`오늘 이슈 피드`)의 피드 아이템 형태.

- 전체 톤: 지금 Chat 패널과 같은 다크·미니멀 톤 유지. 새 디자인 시스템 만들지 않음.
- 날짜 구분 헤더("오늘, 11월 22일 일요일") 아래로 시간순 리스트.
- 아이템 구성: 상대 시간("23분 전") + 제목 + 본문 1~2줄 + 관련 종목 칩(등락률 색 구분) +
  AI 태그 칩(`tags` 필드).
- 필터 탭: "전체"만 동작. 카테고리가 하나뿐이므로 다른 탭은 1단계에서 넣지 않는다
  (죽은 버튼 방지). 2·3단계에서 카테고리가 늘어나면 그때 탭을 추가한다.
- 공유·댓글·북마크 같은 참여 아이콘은 그 기능 자체가 없으므로 1단계에서 넣지 않는다.
- 카드형 장식(그림자, 둥근 테두리 과다)은 쓰지 않는다. 리스트 하나로 심플하게.

## 캐릭터·음성 연동

- 보류. 뉴스피드가 먼저 안정적으로 돌아간 뒤에 진행한다.
- 참고: `frontend/js/reply-speech.js`에 브라우저 내장 음성 읽기 기능이 이미 있어서, 나중에
  캐릭터를 붙일 때 이 모듈을 확장해서 재사용하면 된다 (새로 만들 필요 없음).
