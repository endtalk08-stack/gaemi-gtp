# gaemiGTP 전체 구조 이전 — 작업 기록

- 시작일: 2026-11-09 (KST)
- 저장소: `endtalk08-stack/gaemi-gtp`
- 통합 브랜치: `integration/full-migration-20261109`
- 기준 브랜치: `ops/do-ssh-deploy-setup-20261017`
- 이전 뉴스 전용 통합 브랜치 `integration/news-r2-pages-20261109`는 이 작업의 기준으로 사용하지 않음. 삭제 여부 및 실제 삭제는 별도 확인.

## 최종 목표 (확정 지침)

- 이 저장소의 `frontend/`는 현재 Flask `app.py`가 서비스하는 화면 원본. 목표는 기존 `gaemi-gtp` 화면을 Cloudflare Pages로 이전하는 것. 검증 전 Render Python 서비스 제거 금지.
- 실시간 미국 시세와 TOP20: 기존 키움 API → DigitalOcean 메모리 → WebSocket → 사이트. 매초 DB 저장 금지.
- 뉴스 수집·선별과 AI 분석: DigitalOcean에서 기존 기능 재사용.
- 일반 뉴스·화면용 AI 요약: 기존 Cloudflare R2 `gaemigtp-news-data`에 저장·제공.
- 차트 원본 및 중요 장기 기록: Neon 유지. 화면용 차트 결과: R2.
- 국내 네이버 뉴스 수집 및 오른쪽 뉴스 패널: 유지.
- 기존 국내 코드 분석 결과·키워드·사건 분류: R2 이전 대상에서 제외. 관련 코드 임의 삭제 금지.
- 기존 AI 분석 프로그램은 유지하고 재사용/개편 결정은 보류. 기존 AI 요약은 보존하며 R2 이전 대상.
- Upstash·Supabase는 이번 이전에서 새로 사용하지 않음. D1·KV 신규 생성 금지.

## 우선순위 / 진행 게이트

1. [ ] 기존 운영 코드와 실제 Render·DigitalOcean·R2 연결 구조 읽기 전용 확인.
2. [ ] **1순위:** 뉴스의 Neon 쓰기·읽기 의존 경로 전체 조사. 뉴스 원본/선별 결과와 AI 요약만 R2로 전환할 최소 변경 범위 및 장애 위험 보고.
3. [ ] 기존 R2 업로드 코드·버킷·키와 사이트 뉴스 소비 경로 재사용하여 **새 기능 중복 구현 없이** 최소 수정.
4. [ ] 서버 정지 상태를 유지한 코드·정적 테스트 수행. 이후 별도 승인과 조건 확인 하에 DigitalOcean 재개 및 뉴스 수집 → R2 → 사이트 실제 검증.
5. [ ] Render 메인 사이트의 기존 기능 정상화 후 Cloudflare Pages로 전체 이전. 실시간 시세·TOP20·차트·뉴스·AI 채팅 확인.
6. [ ] 과거 Neon 뉴스/AI 요약 데이터의 선별적 R2 이전은 사이트 정상화 이후에 처리. 기존 데이터 확인 전 삭제 금지.
7. [ ] 전체 기능 실측 검증 후 Render 제거 여부 별도 승인.

## 확인된 사실 (2026-11-09)

- Neon 프로젝트 `gaemi-gtp`: 조회된 브랜치 모두 `archived`였음. SQL 데이터 조회 및 재개 안 함.
- R2 기존 버킷 `gaemigtp-news-data`: `news/latest.json` 및 백업 객체 확인. 이것만으로 자동 갱신 확인된 것은 아님.
- 코드상 기존 Neon 관련: `backend/services/news_processed_store.py` (`news_processed_snapshots`, AI 결과), `backend/services/news_metadata_store.py` (뉴스 메타데이터 저장), `ops/staged_ai_issue_store.py` (AI 이슈), `backend/services/market_issue_headlines.py` (Neon 읽기).
- 기존 R2 업로드 구현: `backend/services/r2_news_uploader.py`, 키 `news/latest.json`.
- 확인된 내용은 저장 코드/버킷 상태이며 운영 흐름 전체 정상 여부는 미검증.

## 변경 이력

| 날짜 | 작업 | 결과 | 검증 | 운영 영향 |
| --- | --- | --- | --- | --- |
| 2026-11-09 | 운영 브랜치 기반 전체 이전용 통합 브랜치 생성 | `integration/full-migration-20261109` | GitHub 생성 응답 확인 | 없음 |
| 2026-11-09 | 전체 이전 범위·1순위 뉴스 DB 전환·금지 사항 기록 | 이 문서 생성 | GitHub 파일 조회로 확인 예정 | 없음 |

## 중지/승인 원칙

확인 → 기존 구조 검증 → 문제점 보고 → 사용자 허락 → 최소 수정 → 최소 검증 → 결과 보고.

- 현 시점 DigitalOcean 및 Neon 의도적 중지 상태 유지.
- 사용자 승인 없이 서버 기동, Actions 실행, DB 변경·삭제, 배포, 유료 기능 활성화 금지.
- 코드는 본 브랜치에서만 관리하고 운영 브랜치·기존 사이트를 임의로 변경하지 않음.
- 실제 완료하지 않은 작업을 완료로 기록하지 않음.
- 매 작업에 변경 파일, 이유, 테스트, 배포 여부, 다음 단계 추가 기록.


## 1차 코드 실사 — 뉴스 Neon 의존성 (2026-11-09)

읽기 전용으로 새 통합 브랜치의 실제 파일 내용을 확인함. 운영 서버 환경변수 값이나 서비스 실행 상태는 아직 검증하지 않았음.

| 파일 | 확인된 동작 | 조치 판단 |
| --- | --- | --- |
| `backend/news_worker.py` | 미국 TOP20 뉴스 작업. `main()`에서 `NEWS_DATABASE_URL` 없으면 즉시 종료. 뉴스 지문 조회·스냅샷 저장·체크·정리 호출. | **Neon 없이 기동하려면 구조 변경 필요**. 바로 서비스 기동 금지. |
| `backend/services/news_processed_store.py` | `news_processed_snapshots` 읽기/쓰기, AI 요약 `_ai_issue_briefs`와 코드 분석 `_code_issue_briefs`를 같은 payload 안에서 관리, 만료 데이터 삭제. | 단순 DB URL 제거 금지. 뉴스/AI JSON 분리와 기존 화면 호환성 검토. |
| `backend/services/news_metadata_store.py` | 뉴스 워커 환경에서 원본 기사 메타데이터를 `news_articles`에 비동기 저장. | R2 화면용 JSON과 불필요한 중복 저장 구분. |
| `ops/staged_ai_sequential_batch.py` | AI 작업은 Neon `news_ai_call_ledger`, `news_ai_issues`, `news_processed_snapshots`에 의존. AI 기본 일시중지 플래그 존재. | AI 프로그램 자체는 유지하고 재가동 전 별도 독립성 검증. |
| `backend/services/market_issue_headlines.py` | 기존 TOP20 뉴스 제목 보완 시 Neon `news_processed_snapshots` 조회; DB 미설정이면 빈 결과 반환. | TOP20 표시를 임의로 변경하지 않고 우회/대체 필요 여부 확인. |
| `backend/services/news_result.py` | `NEWS_PROCESSED_READ_MODE`가 `prefer/only`일 때 Neon 스냅샷을 조회, 기본 `off`에서는 기존 수집 및 메모리 캐시 경로. | 오른쪽 패널은 기존 표시 경로 보존, 모드별 확인 필요. |
| `backend/services/r2_news_uploader.py` | 기존 R2 버킷 `gaemigtp-news-data`의 `news/latest.json`에 파일 업로드 함수 이미 있음. | 기존 업로드 코드 재사용, 새 시스템 중복 구축 금지. |
| `functions/news/latest.json.js` | Cloudflare Pages의 `NEWS_R2` 바인딩에서 `news/latest.json` 조회. | 기존 바인딩/키 보존. 메인 Render 사이트와는 별도 경로. |
| `frontend/news/index.html` | 뉴스 페이지가 `/news/latest.json` 또는 `NEWS_R2_URL` 사용. | 기존 뉴스 페이지와 Render 메인 사이트 혼동 금지. |
| `app.py` | TOP20 이슈 제목 endpoint 및 뉴스 DB를 쓰는 별도 차트 API 코드 존재. | `NEWS_DATABASE_URL`을 서버 전체에서 제거하면 차트도 깨질 수 있어 금지. |

### 1차 판단

1. 서비스 복구 전 **일반 뉴스 수집 결과를 R2에 갱신하는 기존 발행 경로**와 미국 TOP20 `news_worker`의 Neon 필수 의존을 분리해서 점검해야 함.
2. 우선 뉴스 메타데이터·처리 결과의 Neon 쓰기를 제어하면서 기존 R2 JSON 발행 및 사이트 조회를 재사용하는 최소 패치 설계가 필요함.
3. AI 요약은 기존 데이터 보존, 기존 AI 코드 재사용·개편 결정은 보류. AI 호출 이력은 중복 분석 방지와 관련되어 있어 R2에 그냥 복사하면 안 됨.
4. 국내 네이버 뉴스와 오른쪽 패널, 실시간 시세, 차트 Neon 장기 보관은 **이번 패치의 수정 대상 아님**.
5. 과거 Neon 데이터의 실제 이전은 운영 정상화 후에 별도로 수행. Neon 브랜치 `archived` 상태 유지.

### 아직 확인해야 할 사항

- 어떤 기존 잡/서비스가 `news/latest.json` 파일을 생성하고 `upload_file`을 실제 호출하는지.
- 현재 `gaemi-gtp`의 Flask `/analyze`가 반환하는 뉴스 결과와 별도 Cloudflare 뉴스 페이지 `/news/latest.json` 연결을 구별.
- DO 서버에서 현재 설정된 환경변수/서비스 종류의 실제 상태(지금은 재가동 금지).
- 코드만의 정적 테스트 및 로컬 모의 R2 검증 가능 경로.

### 변경 이력 추가

| 날짜 | 작업 | 결과 | 검증 | 운영 영향 |
| --- | --- | --- | --- | --- |
| 2026-11-09 | 뉴스 Neon 의존 코드 실사 | 10개 코드 파일에서 핵심 의존 확인, 이 문서에 정리 | GitHub 읽기 전용 확인 | 없음 |


## 1차 최소 코드 수정 — 미국 TOP20 뉴스 R2 저장 (2026-11-09)

통합 브랜치에만 반영; 운영 배포·Actions 실행·DigitalOcean 재가동·Neon 재개 없음.

- 수정 `backend/services/r2_news_uploader.py`: 기존 `news/latest.json` 기본값을 보존하면서 제한된 `news/stocks/us/{SYMBOL}.json` 객체 키 업로드를 허용. 경로 검증 추가.
- 수정 `backend/news_worker.py`: 운영 환경에서 `GAEMIGTP_NEWS_STORAGE=r2`를 **명시적으로 설정할 때만** R2 뉴스 발행 분기로 들어감. 기본 `neon` 모드는 변경하지 않음. R2 분기는 기존 US TOP20 선정/뉴스 수집 및 기존 R2 업로더를 재사용하고, 원문 링크·제목·설명·발행 시각·출처만 종목별 JSON으로 발행.
- R2 모드는 `news_processed_snapshots` DB 읽기/쓰기, AI 예약·실행, Neon 뉴스 정리 호출을 우회. 기존 AI 분석 프로그램은 수정·삭제하지 않음. 기사 수집 또는 R2 업로드 실패 시 이전 성공 기록을 갱신하지 않음. 동일한 지문이면 재업로드 생략.
- 새 테스트 `tests/test_news_worker_r2_only.py`: R2 저장 성공/중복 스킵/실패 시 상태 보호/빈 뉴스 보호/잘못된 종목코드 차단/기존 뉴스 페이지 객체 보호/모드 opt-in 확인.
- 별도 객체 키 `news/stocks/us/{SYMBOL}.json`은 새 R2 버킷이 아니라 기존 `gaemigtp-news-data` 버킷 내부. **기존 `news/latest.json` 파일은 변경하지 않음**.

### 남은 차단 조건 — 아직 재가동 금지

1. 신설 테스트는 GitHub에 작성·내용 재조회했지만 **실제 Python 테스트 실행은 미완료**. GitHub Actions는 승인 없이 실행하지 않음.
2. 운영 R2 자격증명(`R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`) 존재 여부 및 권한 미확인. 키 값 공개 금지.
3. 신규 종목별 R2 JSON을 메인 Render 사이트/오른쪽 패널에서 읽는 경로는 아직 구현·검증되지 않음. 기존 오른쪽 패널 수집 경로는 변경하지 않음.
4. 기존 TV 뉴스 페이지 발행기는 별개이며 이번 변경 대상 아님. US TOP20 뉴스 R2 발행 경로와 기존 뉴스 페이지는 독립 운영.
5. 기존 Groq AI 실행은 Neon 호출·중복 방지 기록에 의존하므로 R2 모드에서 실행하지 않음. **AI 요약 이전/새 생성은 미완료**.
6. 운영에 적용하기 전 실제 서비스의 systemd 환경과 실행 경로 확인, 서버 재가동 승인, 테스트 및 갱신 검증 필요.

### 변경 이력 추가

| 날짜 | 작업 | 결과 | 검증 | 운영 영향 |
| --- | --- | --- | --- | --- |
| 2026-11-09 | R2 업로더에 기존 버킷 내 종목별 키 지원 | `0ca3620` | GitHub 파일 재조회 | 없음 |
| 2026-11-09 | 뉴스 워커 R2 전용 분기 추가 | `41b2ccd` | GitHub 파일 재조회 | 없음 |
| 2026-11-09 | R2 회귀 테스트 작성 | `77aa651` | GitHub 파일 재조회, 실행 미완료 | 없음 |


## 2차 검증 — gaemi-gtp Flask 뉴스 소비 경로 (2026-11-10)

- 코드 조회: `frontend/js/analysis-api.js`는 `BACKEND_URL/analyze`로 분석 요청을 하고 `paired_news_items`를 전달.
- `frontend/widgets/analysis-data/analysis-data.js`는 `panel_news_items` (없으면 `paired_news_items`)를 `newsItems`로 보관.
- `frontend/shell/right-panel/right-panel-tabs.js`의 오른쪽 뉴스 탭은 `GaemiGTPAnalysisData.get().newsItems`를 그리는 구조이며 R2를 직접 호출하지 않음.
- `backend/services/news_result.py`는 `NEWS_PROCESSED_READ_MODE=off` 시 종목 뉴스 수집/캐시를 이용하고, `prefer/only` 시 Neon 스냅샷을 먼저 읽음.
- **따라서 종목별 R2 업로드 경로를 추가한 것만으로 Render 오른쪽 패널이 R2를 읽는 것은 아님.** 기존 패널 구조는 보존했고 R2 연결 변경·배포는 아직 하지 않음.
- 기존 `news/latest.json`은 별도 뉴스 페이지 데이터이며 우측 패널용 종목 데이터와 섞지 않음.
- 실제 소비 경로는 현재 저장소의 Flask `/analyze`와 기존 뉴스 오른쪽 패널을 기준으로 확인함. 별도 사이트는 이번 작업에서 제외.
- Python/JS 테스트: 신규 테스트 파일 및 코드가 GitHub에 저장돼 있음을 확인했지만 **실제 단위 테스트는 실행하지 못함**. `git ls-remote` 원격 접속도 현재 검사 컨테이너의 DNS 제한으로 실패. GitHub Actions는 사용자 별도 허락 없이 실행하지 않음.

### 검증 후 작업 판단

1. R2 저장용 종목별 JSON을 패널에 사용하기 전에 `gaemi-gtp` Flask의 뉴스 호출 경로와 `BACKEND_URL`을 운영 설정과 대조해야 함.
2. 기존 오른쪽 패널은 임의 수정 금지. R2 종목 뉴스 조회 경로는 기존 UI 데이터 계약과 호환되는지 모의 테스트 후 연결.
3. 실가동 기준: R2 발행 정상, 수집 실패 시 이전 데이터 보존, 중복 재업로드 억제, Neon 호출 0, KR 패널 회귀 없음, US TOP20 원본 매칭 유지.
4. **운영 반영 차단:** Render 워크스페이스 확정·실제 테스트 실행·DigitalOcean R2 자격증명 확인·도메인 소비 경로 검증 전에는 서버 재가동/배포하지 않음.

### 변경 이력 추가

| 날짜 | 작업 | 결과 | 검증 | 운영 영향 |
| --- | --- | --- | --- | --- |
| 2026-11-10 | Render 메인 오른쪽 뉴스 탭 소스 분석 | 기존 `/analyze` → `newsItems` 경로 확인, R2 미연결 명시 | GitHub 코드 읽기 전용 확인 | 없음 |

## 실제 파일 구조 및 R2 전환 작업 (2026-11-10)

**정확한 작업 저장소 `endtalk08-stack/gaemi-gtp`만 기준.** 이름이 비슷한 다른 서비스는 대상이 아니며 이번 작업에서 코드·설정 변경 없음.

- `app.py`: Flask API와 `frontend/index.html` 제공. `README.md`도 동일 구조를 명시.
- `frontend/index.html`, `frontend/shell/`, `frontend/widgets/`: 기존 gaemiGTP 화면. 오른쪽 뉴스 탭은 `frontend/shell/right-panel/right-panel-tabs.js`에서 `GaemiGTPAnalysisData.newsItems` 사용.
- `frontend/news/index.html`: 별도 Cloudflare 뉴스 페이지; `/news/latest.json` 사용.
- `functions/news/latest.json.js`: 기존 `NEWS_R2` 바인딩으로 `gaemigtp-news-data/news/latest.json` 읽기.
- `backend/tradingview_news_worker.py` → `backend/services/tradingview_news_page.py` → `backend/services/r2_news_uploader.py`: 기존 TradingView 뉴스 페이지 생성·R2 업로드 경로. 변경하지 않고 그대로 재사용.
- `backend/news_worker.py`: 기존 키움 로컬 TOP20 순회 및 Naver/회사/SEC 뉴스 수집. 기존 `NEWS_DATABASE_URL` 기반 처리 모드는 유지하고 R2 전용 모드를 **명시적 opt-in**으로 추가.
- `backend/services/news_r2_ai.py`: 기존 `ops/staged_daily_groq_issues.py`, `ops/staged_ai_issue_display_adapter.py`를 재사용한 미국 TOP20 AI 요약 R2 출력 경로 추가. AI 호출은 `GAEMIGTP_NEWS_AI_PAUSED=0`과 `GAEMIGTP_NEWS_AI_R2_ENABLED=1`을 모두 설정해야만 실행(현재 활성화 안 됨). 미국 거래일 10:30 ET 이후 1회, 본문과 명시적 발행 시각이 있는 최근 24시간 뉴스만 분석. **AI 호출 전** 기존 `/var/lib/gaemigtp-news/rotation.json`에 예약을 기록하여 중복 유료 호출 방지. 이미 예약되면 성공/실패 무관하게 다시 유료 호출하지 않음.
- R2 객체 **기존 버킷 사용**, 새 버킷/키/서비스 생성 안 함:
  - `news/latest.json` — TradingView 기존 뉴스 페이지; 덮어쓰지 않음
  - `news/stocks/us/{SYMBOL}.json` — 미국 TOP20 뉴스 메타데이터; 기존 코드 기반 수집
  - `news/ai/us/{SYMBOL}.json` — 기존 Groq AI의 출처 검증된 이슈 0~3개 요약; 가격 상승·하락 이유는 실제 가격 맥락 없을 때 생성하지 않음
- `functions/news/stocks/us/[symbol].js` 및 `functions/news/ai/us/[symbol].js`: 기존 `NEWS_R2`에서 종목별 저장 결과 읽는 Pages Functions. **신규 URL은 코드에만 존재하며 배포되지 않았음.**
- `backend/kiwoom_us_price_relay.py`: 실시간 가격 스트림, Neon/Redis 저장하지 않는 기존 코드.
- `backend/kiwoom_us_daily_collector.py`: 일봉 DB 원본은 `NEWS_DATABASE_URL` 사용하므로 이 환경변수 전체 제거 금지.
- `.github/workflows/do-gateway.yml`: 운영 브랜치의 `.github/do-gateway/request.json` 변경으로 Actions→SSH→DigitalOcean 경유. **운영 브랜치에서만 trigger**, 이번 통합 브랜치의 코드 커밋은 서버 배포 아님.

### 수정 파일/검증

| 파일 | 수정 | 상태 |
| --- | --- | --- |
| `backend/news_worker.py` | R2 opt-in raw 뉴스 발행과 AI 요약 발행 연결 | 커밋 |
| `backend/services/r2_news_uploader.py` | 기존 객체 유지, 종목/AI 객체 키만 제한적으로 허용 | 커밋 |
| `backend/services/news_r2_ai.py` | 별도 AI 요약 출처·중복 호출 보호 및 R2 저장 | 신규 커밋 |
| `functions/news/stocks/us/[symbol].js` | 기존 R2 바인딩으로 종목 뉴스 조회 | 신규 커밋 |
| `functions/news/ai/us/[symbol].js` | 기존 R2 바인딩으로 AI 요약 조회 | 신규 커밋 |
| `tests/test_news_worker_r2_only.py` | 순수 수집·저장 안전성 테스트 | 테스트 코드 작성 |
| `tests/test_news_r2_ai.py` | 기본 중지, 1일 예약, 실패 시 중복 호출 금지, 실제 기사 출처/최근 24시간 | 테스트 코드 작성 |

**검증 사실:** 수정·신규 파일은 GitHub에서 재조회됨. 이 통합 브랜치에 대한 GitHub Actions 실행 기록은 **0건**. Python 단위 테스트는 **아직 실제 실행되지 않았음**. 실제 DigitalOcean R2 환경변수·연결과 배포 기능도 미검증.

### 다음 차단 조건

1. 실행 환경에서 Python 테스트 통과 및 R2 모의 객체 읽기 검증.
2. `gaemi-gtp`의 기존 뉴스 패널과 별도 뉴스 페이지 소비 경로에 대한 실 데이터 연결 여부 확정. 새 Functions는 조회 API로만 추가되었고, **UI 자동 연결된 상태는 아님**.
3. DigitalOcean 서버 내 기존 R2 자격증명 바인딩 및 뉴스 서비스 unit 확인. 서버·Neon 의도적 중지 유지.
4. 운영 branch로 승인된 배포 절차를 거치기 전 재가동 금지. 가격/차트 코드 및 기존 국내 패널 변경하지 않음.

### 변경 이력 추가

| 날짜 | 작업 | 결과 | 검증 | 운영 영향 |
| --- | --- | --- | --- | --- |
| 2026-11-10 | 실제 저장소 파일 트리 재점검 | `gaemi-gtp` 운영 브랜치 파일 597개 구성 파악 | GitHub 트리·코드 조회 | 없음 |
| 2026-11-10 | AI 요약 R2 안전 경로 추가 | `backend/services/news_r2_ai.py` 및 worker 호출 | GitHub 파일 재조회 | 없음 |
| 2026-11-10 | 출처/24시간 기준 AI 선별 강화 | `3d21ca6`, `6749600` | 테스트 코드 작성, 실행 미완료 | 없음 |
| 2026-11-10 | 미국 종목뉴스·AI 요약 Pages 조회 Function 추가 | `functions/news/stocks/us/[symbol].js`, `functions/news/ai/us/[symbol].js` | GitHub 파일 재조회 | 없음 |

### 운영 전 추가 안전 확인

- R2 AI의 로컬 예약 기록은 **새로운 R2 모드 내부에서만** 중복 분석을 막음. 이전 Neon `news_ai_call_ledger` 예약과 자동 동기화하지 않으므로 전환 당일 중복 비용 위험이 있음. **실제 활성화 전에 기존 당일 AI 예약 유무를 안전하게 확인**하고, AI는 승인 없이 활성화하지 않음.
- 본 브랜치의 R2 AI 예약은 단일 DigitalOcean 워커 프로세스를 전제로 함. 실제 운영 시 중복 워커 인스턴스가 없음을 검증하기 전 AI 활성화 금지.
- 기존 `frontend/news/index.html`의 `loadNews()`는 여전히 `/news/latest.json`만 읽음. 신규 `news/stocks/us` 및 `news/ai/us` 조회 API는 **아직 UI에 합쳐지지 않았음**. 기존 화면을 임의로 수정하지 않음.
- 기존 R2 업로드 계정의 실제 경로별 쓰기 권한, Functions 실행의 인증·바인딩, Python 회귀 테스트 통과는 미확인. 작성된 코드를 운영 배포 전 검증해야 함.


## 3차 구현 — 미국 TOP20 R2 뉴스 패널 연결·로컬 검증 (2026-11-10)

이번 작업 저장소는 `endtalk08-stack/gaemi-gtp`, 브랜치는 `integration/full-migration-20261109`로 한정. 자동매매 사이트/저장소 관련 작업 없음. 운영 배포·DigitalOcean 뉴스 워커 재가동·Neon 재개 없음.

- `frontend/js/analysis-api.js`: 기존 `/analyze` 호출 및 응답 구조를 유지하면서, **미국 종목**이고 명시적 `window.ENV.NEWS_STOCKS_R2_BASE_URL`을 설정한 경우에만 `{BASE}/news/stocks/us/{SYMBOL}` 조회. 유효한 R2 종목 기사 데이터가 있으면 기존 `panel_news_items` 계약으로 전달.
- R2 조회 오류/404/빈 기사/종목 코드 불일치일 경우 기존 `paired_news_items` 뉴스 패널을 사용. **국내 종목 뉴스는 전혀 변경하지 않음.** 기존 공시·분석 결과도 그대로 전달.
- 종목 코드 허용 문자 검증과 R2 원문 URL HTTP(S) 검증. 잘못된 R2 주소 또는 프로토콜 상대 주소 `//...`는 요청하지 않음. 사용자 화면 레이아웃 변경 없음.
- `tests/news-r2-panel.test.mjs`: R2 비설정 시 기존 경로, 미국 R2 성공, 실패 시 기존 뉴스 유지, 한국 종목 격리, 잘못된 종목 코드, 프로토콜 상대 주소 차단 테스트 추가.
- **실제 로컬 Node 테스트:** 저장된 `frontend/js/analysis-api.js`와 동일한 코드의 길이(3,367자) 및 코드 포인트 FNV-1a 체크섬(`b5ce2512`)을 대조한 로컬 파일로 `node --check` 통과, Node `node --test` 6개 시나리오 전부 통과. 로컬 테스트 스크립트는 저장소 테스트 파일을 직접 checkout한 것이 아니라 6개 동등 시나리오 재현이므로 **GitHub 저장소의 실제 CI 테스트 완료로 기록하지 않음.**
- 기존 R2 뉴스 조회 Functions는 코드에만 추가돼 있으며 실제 Pages 사이트에 배포되지 않았음. `NEWS_STOCKS_R2_BASE_URL`도 운영 사이트에서 설정되지 않았으므로 실제 패널 기능은 **비활성** 상태.

### 추가 Neon 코드 의존 확인

- `backend/news_worker.py` R2 모드는 `news_feed.fetch_stock_news` + `news_processed_store.source_fingerprint` 호출. `source_fingerprint`는 기사 메타데이터 해시 계산만 수행, `_connect()` 호출 없음.
- `backend/services/news_feed.py` 수집과 `backend/providers/naver_news.py`는 기사 조회/가공 및 캐시를 사용, 직접 DB 호출 없음.
- 기존 `news_processed_store.save_snapshot/read_signature/purge_expired` 및 `staged_auto_ai_daily` DB 경로는 `GAEMIGTP_NEWS_STORAGE=r2` 선택 시 실행하지 않는 분기.
- **단, 전체 환경에서 Neon 접속 0건 실측은 아직 미검증**. 전체 Python 모의 단위 테스트와 서비스 실행 검증 전에 보장하지 않음.

### 운영 상태 별도 기록 (이번 통합 브랜치에서 변경하지 않음)

2026-11-10 별도 사용자의 명시적 승인으로 운영 브랜치 GitHub→SSH를 통해 `gaemigtp-tradingview-news.service`만 활성화. status 출력 `active/running`, 기존 `gaemigtp-news.service`는 `inactive/disabled`. 수집 로그 `r2-news upload_ok key=news/latest.json` 및 Cloudflare R2 객체 갱신 확인. **따라서 이 시점부터 'DigitalOcean의 모든 뉴스 서비스가 중지'라는 과거 문장은 현재 전체 운영 상태를 나타내지 않음.** Neon 의도적 중지는 유지. 새 통합 브랜치 R2 종목·AI 코드는 아직 운영 서버에 배포되지 않음.

### 후속 차단 조건

1. 저장소의 Python 테스트 `tests/test_news_worker_r2_only.py`, `tests/test_news_r2_ai.py` 실제 실행 및 실패 수정. GitHub Actions는 별도 승인 없이 시작하지 않음.
2. 기존 `NEWS_R2` Pages Functions의 `news/stocks/us` 및 `news/ai/us` 응답 실검증, 동일 출처 제공/인증 검토.
3. TOP20 종목뉴스 R2 발행이 실제로 가능하도록 운영 워커 단독 전환 검증. 기존 TradingView 뉴스페이지를 덮어쓰거나 Neon 일봉 코드 변경 금지.
4. AI 비용·중복 분석 예약 전환 확인 전에는 `GAEMIGTP_NEWS_AI_R2_ENABLED` 활성화 금지. 시장 휴장일과 기존 Neon AI 예약 상태 확인 필요.


## 재개 작업 결과 — 독립 검증 및 뉴스 패널 장애 격리 (2026-11-10)

- 실제 작업 대상: `endtalk08-stack/gaemi-gtp`의 통합 브랜치. 다른 자동매매 사이트는 조회·수정하지 않음.
- TradingView 전용 수집 서비스 `gaemigtp-tradingview-news.service`는 별도 승인에 따른 복구 후 실행 유지. 이 작업에서는 서비스/Neon/DB/Cloudflare 운영 설정을 변경하지 않음.
- 기존 R2 이관 검증용 workflow가 없는 파일 `backend/services/news_market_issue_r2.py` 등을 컴파일하여 실패했던 기록 확인. 이번 통합 브랜치에 존재하는 파일만 검사하는 `.github/workflows/check-full-migration-news-r2.yml` 추가. 로컬 모의 객체 테스트만 실행하며 뉴스 API, DB, R2, AI에 실제 요청하지 않음.
- `frontend/js/analysis-api.js`: R2를 명시적으로 설정한 미국 종목에서 기존 `/analyze` 요청이 실패해도 R2 뉴스 결과를 표시하도록 두 요청을 독립적으로 처리. 한국 시장, 기존 뉴스·공시 반환, R2 설정이 없을 때 기존 동작은 유지.
- `tests/news-r2-pages.test.mjs`: 기존 `NEWS_R2` 바인딩으로 종목·AI 객체를 조회하는 경로를 모의 검증(응답 200/304/404/503, 종목 식별자 검증).
- `tests/news-r2-panel.test.mjs`: 기존 분석 API가 503일 때 R2 뉴스 유지, 양쪽 모두 실패할 때 기존 실패 응답 유지 사례 추가.
- 최신 독립 GitHub Actions 실행 [42655720175](https://github.com/endtalk08-stack/gaemi-gtp/actions/runs/42655720175): Python 13건 + Node 16건 = **29건 전부 통과**, 문법 검사 통과.

**미완료**: 기존 Pages 프로젝트에 새 API와 미국 뉴스 패널의 URL 환경변수 적용, 실제 R2 종목별 데이터 발생 여부, 기존 AI 결과 실전 출처·권한 검증 및 하루 1회 예약 전환, DigitalOcean R2 뉴스 워커 운영 배포, 라이브 사이트 반영. 운영 이전·배포를 완료했다고 주장하지 않음. 서비스 중지 상태와 비용 안전 정책을 유지함.


## 4차 확인 — 통합 브랜치 오프라인 CI 통과 (2026-11-10)

- GitHub Actions [Validate full-migration R2 news offline, run 42655279300](https://github.com/endtalk08-stack/gaemi-gtp/actions/runs/42655279300): `success`. CI가 실제 실행된 것이므로 위의 초기 기록 중 "Python 테스트 미실행" 문구는 **당시 이력**으로만 읽어야 함.
- 실제 검증: Python **13개 통과**(`tests.test_news_worker_r2_only`, `tests.test_news_r2_ai`), Node **14개 통과**(`tests/news-r2-panel.test.mjs`, `tests/news-r2-pages.test.mjs`); R2 Pages Function 파일 문법 검사 및 Python 컴파일 모두 성공. 전부 외부 API/Neon/실제 R2 쓰기 없는 오프라인 검증.
- `frontend/js/analysis-api.js`는 기존 `/analyze` 출력과 함께 미국 TOP20 종목뉴스 R2 데이터를 **설정이 활성화된 경우에만** 별도의 `panel_news_items`로 전달. 현재 프런트의 `GaemiGTPAnalysisData.set`와 오른쪽 뉴스 탭은 이미 `panel_news_items`를 소비하도록 되어 있음. 국내 뉴스·기존 차트/공시 로직 변경 없음.
- CI는 **서버 연결, 실제 새 종목별 R2 객체 존재, 웹사이트 반영, 유료 AI 호출 여부**를 검증한 것이 아님. 운영 환경 적용은 여전히 미승인/미실행.
- 이 작업 도중 운영 브랜치에서 **별도 승인으로 TradingView 서비스만 복구하면서 GitHub gateway 관련 6개 커밋이 추가됨**. 통합 브랜치를 운영 브랜치로 병합하기 전 최신 운영 변경분을 보존하면서 명시적 검토가 필요. 운영 브랜치 수정/병합은 하지 않음.


## 5차 재개 — 운영 보호 및 R2 이관 차단 원인 확인 (2026-11-10)

- **대상 한정:** `endtalk08-stack/gaemi-gtp` 통합 브랜치의 **뉴스·AI R2 전환**. 차트·시세·자동매매 저장소 및 다른 사이트 변경 없음.
- **Cloudflare 읽기 전용 확인:** 기존 Pages 프로젝트 `gaemigtp-news`의 production branch는 `ops/do-ssh-deploy-setup-20261017`, 배포 상태 성공, `NEWS_R2` 바인딩은 기존 버킷 `gaemigtp-news-data`로 연결.
- **R2 데이터 실측:** 현재 `news/` 경로에 `news/latest.json`과 `news/backups/latest-before-paragraph-fix-20261109.json`만 있음. **미국 TOP20 `news/stocks/us/` 또는 AI `news/ai/us/` 객체는 아직 없음.** 따라서 새 코드에 대한 실제 서비스·R2 게시 및 사이트 연동 완료로 판단하지 말 것.
- **분기 보호:** 통합 브랜치와 운영 브랜치는 **서로 diverged**. 이 확인 당시 통합 ahead 33 commits, behind 6 commits. 운영 브랜치의 TradingView 서비스 복구와 SSH gateway 변경을 보존해야 하므로 **무검토 병합 및 운영 배포 금지.**
- **코드 점검:** `backend/news_worker.py`에서 R2 전용 분기는 기존 `news_feed.fetch_stock_news`를 사용하고 `store.source_fingerprint`는 순수 해시 함수. AI 호출은 기본 OFF, `news/latest.json` 덮어쓰기 금지. 기존 TOP20 종목 로컬 순위 파일과 서비스 상태 실측은 별도 확인이 필요하며, 지난 운영 점검에서 Kiwoom TOP20 수집 서비스 `failed` 상태가 관측됐으므로 새 종목별 R2 발행이 실제 시작할 수 있는지 미확인.
- **추가 보강:** `tests/test_news_worker_r2_only.py`에 `read_signature`, `mark_checked` 등 기존 Neon 경로를 실행하면 테스트가 실패하도록 검증 범위를 확장. R2 모드에서 순위 데이터가 없더라도 Neon 유지보수 함수 `purge_expired`, `purge_expired_original_news`가 호출되지 않음을 추가 검증. **운영 코드 변경 없음.**
- **CI 실측 결과:** GitHub Actions [42660059733](https://github.com/endtalk08-stack/gaemi-gtp/actions/runs/42660059733)에서 Python **14/14 통과**, JavaScript **16/16 통과**, Python 컴파일 및 Pages Functions 구문 검증 성공. 총 30건. **모든 시험은 오프라인 mock 기반**, 실제 뉴스 API·Neon·R2 업로드 및 운영 사이트 작동 검증은 아님.
- **이번 변경 파일:** `tests/test_news_worker_r2_only.py`, 본 작업 기록. 운영 서버 가동, DB/환경변수 변경, Pages 배포, 유료 AI 활성화, 운영 브랜치 병합 **없음**.

### 다음 단계 수행 조건

1. DigitalOcean의 기존 TOP20 순위 파일 `/var/lib/gaemigtp-news/kiwoom-us-top20-news.json`이 최신·정상 20종목인지 **읽기 전용** 확인. 기존 시세·차트 서비스는 재가동하지 않음.
2. 기존 TradingView 수집 서비스 `gaemigtp-tradingview-news.service`는 그대로 보호. TOP20 뉴스와 AI의 R2 전환은 독립 운영 대상으로 분리.
3. 종목별 R2 객체가 없는 상태에서 새 Pages API를 운영에 먼저 내보내도 사용자 화면에는 데이터가 없으므로 **종목뉴스 수집→R2 발행→읽기→화면** 순서로 단계별 실측 검증.
4. 통합 브랜치 최신 코드·운영 브랜치 gateway 변경 차이를 재검토하고, **명시적 배포 승인 전 운영 브랜치 병합·DigitalOcean 변경·Cloudflare Pages 배포 금지.**


## 6차 서버 실측 — 기존 TOP20 로컬 순위·동결 순회·R2 환경 (2026-11-10)

실행 대상: **DigitalOcean 기존 서버** `gaemigtp-news-worker`. 읽기 전용 GitHub Actions→SSH gateway 스크립트만 사용. 원본 뉴스 서비스·TradingView 서비스·Neon·키움 서비스 기동/중지/환경변수 변경 없음. 서버 파일 쓰기 및 네트워크/API/DB 쿼리 없음.

### 확인된 실제 결과

1. [read-only run 42661488569](https://github.com/endtalk08-stack/gaemi-gtp/actions/runs/42661488569) — `/var/lib/gaemigtp-news/kiwoom-us-top20-news.json` **없음**. `rotation.json` **있음**. 마지막 갱신 `2026-10-28T07:03:37Z`; `next_index=17`; R2 뉴스 지문 0개, R2 AI 예약 0개.
2. 같은 점검은 GitHub gateway의 `/etc/gaemigtp/news-worker.env` 환경만 사용하므로 `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`가 **그 실행 환경에 없음**을 확인. **이 사실만으로 서버 전체에 R2 키가 없다고 말하면 안 됨.**
3. [read-only run 42661996682](https://github.com/endtalk08-stack/gaemi-gtp/actions/runs/42661996682) — `rotation.json`의 동결 순회 20종목을 원본 `us_top20_rotation.py`의 필수 필드(순위 1~20, 중복 없는 티커, 유효 종목명·형식)와 동일한 조건으로 읽기 전용 검증: **20/20 유효**, `next_index=17`, `pending=False`, 기존 동결 목록 사용 가능.
4. 동일한 두 번째 점검 — `/var/lib/gaemigtp-news/r2.env` 실제 존재·읽기 가능, 파일 안에 `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` 변수 **이름 존재**. 키 값과 실제 사용·권한은 조회하지 않음. `gaemigtp-tradingview-news.service`에는 기존 `EnvironmentFile=-/var/lib/gaemigtp-news/r2.env` 설정이 있으며, TradingView의 `news/latest.json` 업로드 성공 이력이 있음.
5. 두 번째 첫 실행 [42661787725](https://github.com/endtalk08-stack/gaemi-gtp/actions/runs/42661787725)은 standalone script의 `backend` 모듈 import 경로 오류로 실패했으며, 순수 표준 라이브러리 검사로 수정한 재실행 42661996682는 성공. 이 실패는 서버의 뉴스 수집 장애나 기존 서비스 오류가 아니라 **점검 스크립트 오류**임.

### 확인된 문제와 영향

- **정규 최신 TOP20 순위 로컬 스냅샷이 없어 신규 최신 순위를 확보할 수 없음.** 유효한 기존 동결 20종목은 fallback이 가능하지만 10월 28일 이후 갱신되지 않은 상태여서 **최신 TOP20 뉴스라고 주장하면 안 됨**. 동결 목록의 나머지 3개 처리 뒤에도 코드상 이전 20종목을 재순회할 수 있으나 신선도는 복구되지 않음.
- 별도 `r2.env`에 credential **변수 이름**이 있어도, 기존 `gaemigtp-news.service`의 유효한 systemd `EnvironmentFile` 목록에 자동 포함된다고 가정할 수 없음. **NEWS_STORAGE=r2 배포/기동 이전에 뉴스 서비스의 실제 환경 파일 포함 여부를 읽기 전용 확인하고**, R2 권한과 발행 테스트를 완료해야 함.
- `gaemigtp-kiwoom-us-value.service`는 앞선 실제 status 점검에서 `failed`였음. 로컬 순위 생성 코드는 `backend/kiwoom_us_value_collector.py`의 `_write_local_news_top20`; 이것을 뉴스 이전 작업과 혼동하여 서비스를 임의 재가동하거나 Neon을 활성화하지 않음.
- `GAEMIGTP_NEWS_STORAGE`는 점검 job 환경에서 미설정(default Neon), AI R2 스위치 미설정. AI 실행/유료 호출 없음. **현재 TOP20 R2 객체 신규 생성도 없음.**

### 실행 및 변경 기록

| 구분 | 파일·범위 | 결과 |
| --- | --- | --- |
| 서버 읽기 전용 점검 | `ops/do-gateway/verify_top20_r2_readiness_readonly_20261110.py` | 통과, ranking 파일 부재 확인 |
| 서버 fallback/환경 점검 | `ops/do-gateway/audit_top20_fallback_r2env_readonly_20261110.py` | 첫 진입 오류 수정 후 재실행 통과 |
| GitHub gateway 요청 | 운영 브랜치 `.github/do-gateway/request.json` | 검증용 작업 3회 (첫 2차 점검 실패 포함); 서비스 제어·배포 없음 |
| 통합 브랜치 | 본 worklog | 서버 결과 기록만, 앱 기능 수정 없음 |

**다음 차단 조건:** 신규 TOP20 순위 로컬 스냅샷 생성 경로의 실패 원인과 순위 데이터 신선도, R2 뉴스 서비스의 유효 환경 파일을 확인한 뒤 사용자에게 보고. 사용자 별도 승인 전 키움·Neon·기존 뉴스 서비스는 기동하지 않고 운영 배포·Cloudflare Pages 변경도 하지 않음.


### TOP20 순위 생성 실패 원인 — 기존 키움 수집 로그 (2026-11-10)

- [읽기 전용 Kiwoom value 로그 42662330300](https://github.com/endtalk08-stack/gaemi-gtp/actions/runs/42662330300): `gaemigtp-kiwoom-us-value.service`가 2026-10-28 07:25~07:27 UTC 반복 실패한 실제 오류는 `psycopg.OperationalError` / `NEWS_DATABASE_URL`의 Neon PostgreSQL 연결 불가(`Network is unreachable`). 당시 서비스는 `status=1/FAILURE`; 장애는 추측이 아니라 기존 journal 기록으로 확인.
- 운영 브랜치 `backend/kiwoom_us_value_collector.py` 170~229행 대조: **미국 확장 거래시간 외 구간**에서 기존 DB 스냅샷 유무를 먼저 조회하므로 이 단계에서 Neon 연결이 실패하면 키움 데이터를 수집하거나 `kiwoom-us-top20-news.json`을 생성하기 전에 종료할 수 있음. 반면 거래시간 안에는 20개 소스 순위를 받아 로컬 파일을 먼저 기록하고 그 이후 Neon에 저장하도록 설계되어 있음. 그러므로 **모든 시간대에 Neon이 항상 선행되어야 한다는 주장은 사실이 아님**.
- 사용자 정책상 Neon은 의도적 중지이며 이 뉴스 점검을 이유로 Neon을 재가동하지 않음. 키움 TOP20 수집 서비스의 재시작, DB 우회 동작 변경, 순위 파일 수동 생성·교체도 승인 전 실행하지 않음.
- 현재 로컬 TOP20 JSON 파일이 없는 상태에서 `rotation.json`에 유효한 과거 20종목이 남아 있어도 그것을 **신규 실시간 TOP20**으로 표시하면 안 됨. 최신 순위의 정상 생성·신선도 확인을 별도 게이트로 유지.
- 점검을 위한 운영 브랜치 파일 수정은 `ops/do-gateway/` 내부의 읽기 전용 스크립트 2개와 `.github/do-gateway/request.json`에 한정됨. 실제 서비스 환경·키·DB·배포 파일 변경 없음.
