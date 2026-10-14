# 미국장 마감시황 자동 생성 (07:00 KST)

## 기존 코드 재사용
- 시세: `backend/providers/market_price.py` (Yahoo 일봉)
- 기사 검색/원문: `backend/services/news_feed.py`, `news_detail.py`
- 선별: `backend/services/us_market_close_news.py`
- 결과 구성: `backend/services/us_market_close_brief.py`
- 저장/조회: `backend/services/us_market_close_store.py`
- 예약 실행: `backend/services/us_market_close_daily.py`
- 화면: 기존 `/api/market/us-close-brief` 응답 규격과 타이핑/그래프 재사용

## 예약
GitHub Actions workflow: `.github/workflows/us-market-close-daily.yml`
UTC 월~금 22:00 = KST 화~토 07:00.
07:20, 07:40은 앞선 실행에서 **저장되지 않은 경우에만** 데이터를 다시 확인한다.
GitHub Actions 스케줄은 부하에 따라 지연되거나 생략될 수 있다. 코드상 11:59 KST까지 지연 실행을 허용한다.
이보다 정확한 실행 보장이 필요하면 비용 확인 후 Render Cron으로 교체한다(동시에 두 스케줄러를 운영하지 않는다).

## 최초 활성화 순서 (운영 승인 필요)
1. Neon의 검토된 마이그레이션 `002_us_market_close_results.sql`을 적용한다. 운영 DB에는 사용자 승인 후 반영한다.
2. GitHub 저장소 Settings > Secrets and variables > Actions > Repository secrets에 다음 3개를 등록한다.
   - `GAEMI_NEON_DATABASE_URL`: 기존 `gaemi-gtp` Neon 데이터베이스의 연결 문자열
   - `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`: 이미 사용하는 네이버 뉴스 API 자격 증명과 동일한 값
3. 워크플로를 수동으로 시험하려면 실행 시간 제한에 유의한다. 예약은 KST 07:00 전후이며, 그 외 시간에는 `outside_schedule`로 종료한다.
4. 성공 후 Neon에서 `SELECT session_date, generated_at, index_count, article_count FROM us_market_close_results ORDER BY session_date DESC LIMIT 3;`로 결과를 확인한다.
5. **첫 유효 결과가 저장된 것을 확인한 뒤에만** Render 웹 서비스 환경 변수로 `DATABASE_URL`을 같은 Neon 연결 문자열로 추가하고 `US_CLOSE_READ_SAVED_ONLY=1`을 설정한다.
6. 중앙 `#미국장` 클릭 결과가 저장된 거래일과 일치하는지 확인한다.

운영 스위치가 꺼져 있으면 기존 클릭 시 조회 로직을 유지한다.
운영 스위치를 켜면 중앙 채팅은 **저장된 결과만 조회**하며 API 호출 시 기사나 시세를 재수집하지 않는다.

## 안전장치
- 미국 거래일별 `session_date` PRIMARY KEY와 `ON CONFLICT DO NOTHING`: 중복 저장 방지
- 같은 거래일에 지수가 3개 모두 확인되고 원문 검증 기사가 1개 이상일 때만 저장
- 휴장일 또는 자료 부족 시 현재 날짜의 결과를 생성하지 않음
- 기존 종목별 뉴스/분석 저장 로직 변경 없음
- 휴일에는 최신으로 저장된 거래일의 결과를 읽고, 화면 본문은 해당 거래일 날짜를 표시
- 저장된 본문에는 종목별 원천 뉴스 전체가 아니라 근거 링크/원문 문장 및 가공된 메뉴별 결과만 포함
