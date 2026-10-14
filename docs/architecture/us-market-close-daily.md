# 미국장 마감시황 07:00 KST 자동 준비 (DB 없음)

현재 단계에서는 데이터베이스, 로컬 파일, Redis 등 **영구 저장을 사용하지 않는다.**
증권사 API를 연결할 때 영구 저장을 별도 설계한다.

## 기존 처리 재사용

- 시세: `backend/providers/market_price.py` — Yahoo 일봉
- 뉴스 검색/원문: `backend/services/news_feed.py`, `news_detail.py`
- 미국장 기사 선별: `backend/services/us_market_close_news.py`
- 미국장 결과 가공·메모리 캐시: `backend/services/us_market_close_brief.py`
- 중앙 채팅 API: 기존 `GET /api/market/us-close-brief`
- 7시 실행: `.github/workflows/us-market-close-daily.yml`

## 동작

GitHub Actions UTC 월~금 22:00 (한국시간 화~토 07:00)에
**실행 중인 기존 Render 서버 API를 한 번 호출**한다.
07:20, 07:40에 같은 API를 재확인한다.
완성된 결과가 해당 Render 워커의 메모리에 있으면 재수집하지 않는다.
지수 3종과 마감시황 원문 확인 기사가 모두 있어야 예약 실행을 성공으로 본다.
그보다 적으면 결과를 완성된 것으로 고정하지 않고 10분 캐시 후 재확인을 허용한다.
중앙 `#미국장` 클릭·로딩·그래프·문장·복사/공유 UI는 변경하지 않는다.

**한계:** GitHub 예약은 정확한 분 단위 실행이 보장되지 않는다.
Render가 쉬거나 재시작하면 메모리는 사라지고, Gunicorn 워커 간에도 캐시는 공유되지 않는다.
이때 중앙 채팅이 기존 API 경로를 통해 다시 데이터를 조회하며 정상 동작한다.
이는 운영 DB를 연결하지 않기로 한 현재 범위의 의도적인 트레이드오프다.

## 비공개 모드의 인증

Render의 `SITE_PRIVATE_MODE=1`이면 자동 호출도 접근 제한을 받는다.
GitHub Repository Settings → Secrets and variables → Actions에
`GAEMI_SITE_ACCESS_PASSWORD`를 등록해야 한다.
값은 Render의 기존 `SITE_ACCESS_PASSWORD` 또는 `AI_TEST_TOKEN`의
**현재 로그인 비밀번호와 동일한 값**이어야 한다.
비공개 모드가 아니라면 추가 GitHub secret이 필요 없다.
GitHub Actions는 기존 `/dev-access/login`으로 로그인한 뒤 세션 쿠키로
기존 미국장 API를 조회한다. 새 인증 우회 경로는 만들지 않는다.

## 미래 작업 (지금은 하지 않음)

증권사 API 도입 이후에는 저장 방식과 거래일별 중복 방지 설계를 다시 결정한다.
기존 Neon 운영 DB 테이블은 변경하지 않았고 마이그레이션 임시 브랜치는 폐기했다.
