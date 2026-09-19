# Economic Calendar Patch

## 변경
1. Finance Calendar에서 FOMC 관련 행을 수집하지 않도록 변경했습니다.
2. FOMC는 연준 공식 일정의 정책결정 날짜를 기준으로 별도 추가합니다.
3. Redis key와 파일 캐시를 v3로 올려 이전 FOMC 캐시가 자동으로 사용되지 않도록 했습니다.
4. 기존 해시태그 표시 규칙과 출처 미표시 설정을 유지했습니다.

## 확인
- `python -m py_compile backend/services/engine.py` 통과
- 핵심 FOMC 필터: Finance Calendar의 `FOMC Rate Decision` / `Federal Funds Rate Decision` -> 제외
- 2026-10-28 FOMC 정책결정 -> KST 2026-10-29 03:00으로 생성되는 것 확인
