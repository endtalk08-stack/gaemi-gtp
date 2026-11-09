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
