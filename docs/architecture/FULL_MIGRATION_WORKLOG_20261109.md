# gaemiGTP 전체 구조 이전 — 작업 기록

- 시작일: 2026-11-09 (KST)
- 저장소: `endtalk08-stack/gaemi-gtp`
- 통합 브랜치: `integration/full-migration-20261109`
- 기준 브랜치: `ops/do-ssh-deploy-setup-20261017`
- 이전 뉴스 전용 통합 브랜치 `integration/news-r2-pages-20261109`는 이 작업의 기준으로 사용하지 않음. 삭제 여부 및 실제 삭제는 별도 확인.

## 최종 목표 (확정 지침)

- 메인 웹사이트: Render → 기존 또는 승인된 Cloudflare Pages 배포 방식으로 이전. 전체 검증 전 Render 제거 금지.
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
- Render 메인 사이트 뉴스 패널이 어디서 데이터를 가져오는지(Cloudflare 뉴스 페이지와 구별).
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


## 2차 검증 — Render 메인 뉴스 소비 경로 (2026-11-10)

- 코드 조회: `frontend/js/analysis-api.js`는 `BACKEND_URL/analyze`로 분석 요청을 하고 `paired_news_items`를 전달.
- `frontend/widgets/analysis-data/analysis-data.js`는 `panel_news_items` (없으면 `paired_news_items`)를 `newsItems`로 보관.
- `frontend/shell/right-panel/right-panel-tabs.js`의 오른쪽 뉴스 탭은 `GaemiGTPAnalysisData.get().newsItems`를 그리는 구조이며 R2를 직접 호출하지 않음.
- `backend/services/news_result.py`는 `NEWS_PROCESSED_READ_MODE=off` 시 종목 뉴스 수집/캐시를 이용하고, `prefer/only` 시 Neon 스냅샷을 먼저 읽음.
- **따라서 종목별 R2 업로드 경로를 추가한 것만으로 Render 오른쪽 패널이 R2를 읽는 것은 아님.** 기존 패널 구조는 보존했고 R2 연결 변경·배포는 아직 하지 않음.
- 기존 `news/latest.json`은 별도 뉴스 페이지 데이터이며 우측 패널용 종목 데이터와 섞지 않음.
- 실제 Render 서비스 조회는 계정 워크스페이스 선택이 필요한 상태여서 이 단계에서는 진행하지 못함. 어떠한 Render 설정도 변경하지 않음.
- Python/JS 테스트: 신규 테스트 파일 및 코드가 GitHub에 저장돼 있음을 확인했지만 **실제 단위 테스트는 실행하지 못함**. `git ls-remote` 원격 접속도 현재 검사 컨테이너의 DNS 제한으로 실패. GitHub Actions는 사용자 별도 허락 없이 실행하지 않음.

### 검증 후 작업 판단

1. R2 저장용 종목별 JSON을 직접 패널에 읽히게 하기 전에 Render의 실제 뉴스 호출 경로와 BACKEND_URL을 운영 설정과 대조해야 함.
2. 기존 오른쪽 패널은 임의 수정 금지. R2 종목 뉴스 조회 경로는 기존 UI 데이터 계약과 호환되는지 모의 테스트 후 연결.
3. 실가동 기준: R2 발행 정상, 수집 실패 시 이전 데이터 보존, 중복 재업로드 억제, Neon 호출 0, KR 패널 회귀 없음, US TOP20 원본 매칭 유지.
4. **운영 반영 차단:** Render 워크스페이스 확정·실제 테스트 실행·DigitalOcean R2 자격증명 확인·도메인 소비 경로 검증 전에는 서버 재가동/배포하지 않음.

### 변경 이력 추가

| 날짜 | 작업 | 결과 | 검증 | 운영 영향 |
| --- | --- | --- | --- | --- |
| 2026-11-10 | Render 메인 오른쪽 뉴스 탭 소스 분석 | 기존 `/analyze` → `newsItems` 경로 확인, R2 미연결 명시 | GitHub 코드 읽기 전용 확인 | 없음 |


## Render 실제 운영 서비스/메인 사이트 저장소 점검 (2026-11-10)

**실제 Render 연결에서 읽기 전용으로 확인.** 이전 분석에서 `endtalk08-stack/gaemi-gtp`의 `frontend/`를 메인 화면이라고 간주한 것은 잘못된 전제였음. 현재 서비스는 **서로 다른 두 저장소**에 연결됨.

| Render 서비스 | 종류 | GitHub 저장소/브랜치 | 실제 배포 확인 |
| --- | --- | --- | --- |
| `gaemigtp` (`srv-db7k6uavcj2c73dv63eg`) | Static Site, 빌드 `npm ci && npm run build`, 출력 `dist` | `endtalk08-stack/gaemigtp` / `main` | Render 최신 배포 `bb35e469` (2026-11-05), 상태 `live` |
| `gaemi-gtp` (`srv-daek7jlbedkc73djl4j0`) | Python Web Service, `gunicorn app:app` | `endtalk08-stack/gaemi-gtp` / `main` | Render 최신 배포 `6d1c2a5c` (2026-10-31), 상태 `live` |

- **현재 생성한 통합 브랜치 `integration/full-migration-20261109`는 Python 백엔드 저장소 `gaemi-gtp`에만 있음.** 메인 `gaemigtp` 저장소의 복구·Cloudflare Pages 이전을 대체하지 못함.
- 실제 메인 저장소 `endtalk08-stack/gaemigtp`의 `src/widgets/market.jsx` `NewsWidget`은 테스트용 뉴스 배열을 하드코딩하고 있으며 코드 주석도 '실제 API/DB 연결은 하지 않는다'고 명시.
- 메인 저장소 `src/market-proxy.js`는 `market.gaemigtp.com`의 시세·차트 등 API, `account.gaemigtp.com` 계정 API를 사용함. **이 경로는 뉴스 전용 Render Python `/analyze` 소비 경로와 동일하다고 가정하면 안 됨**.
- `gaemi-gtp` 저장소의 `frontend/js/analysis-api.js` 및 오른쪽 뉴스 패널 호출 경로는 그 저장소 내부의 프런트엔드 기준. 메인 Render Static Site의 `NewsWidget`과 구분.
- Render 양 서비스 모두 `main` 자동 배포 설정. 이번 통합 브랜치의 코드 변경이 자동 배포된 것은 아님.
- Render `live`는 배포 상태를 뜻하며 실제 도메인의 모든 기능 정상 작동을 보증하지 않음.

### 즉시 우선순위 정정

1. 메인 사이트 `endtalk08-stack/gaemigtp`의 실 뉴스 UI 및 API 연결을 별도로 명시하고 검증해야 함. 테스트용 위젯을 운영 데이터로 오인하지 말 것.
2. DigitalOcean 뉴스 R2 저장 변경과 메인 UI 읽기 연결은 **서로 다른 저장소의 작업**. 뉴스와 오른쪽 패널 보존 조건을 적용할 정확한 화면/서비스를 먼저 식별.
3. 운영 배포·DigitalOcean 재가동은 아직 실행하지 않음. 추가 복구나 DB 변경은 현재 파일 상태를 확인한 뒤 최소 변경.

### 변경 이력 추가

| 날짜 | 작업 | 결과 | 검증 | 운영 영향 |
| --- | --- | --- | --- | --- |
| 2026-11-10 | Render 서비스 목록·최신 배포·메인 프런트 저장소 조회 | 실제 메인 `gaemigtp`와 Python `gaemi-gtp` 분리 확인; 메인 NewsWidget 테스트 데이터 확인 | Render 연결 및 GitHub 소스 조회 | 없음 |
