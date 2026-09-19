# gaemiGTP 일정 API 교체

- 경제지표 캘린더를 Finnhub 경제 API에서 제거했습니다.
- 미국 공식 일정 소스로 교체했습니다.
  - BLS: CPI, PPI, 고용보고서(NFP), JOLTS
  - BEA: GDP, Personal Income and Outlays(PCE)
  - Federal Reserve: FOMC
  - U.S. Census Bureau: 소매판매
- 주요 기업 실적은 기존 Finnhub earnings API를 유지합니다.
- 기존 일정 표시 형식은 유지합니다.
  - 오늘밤 일정: `오늘밤 MM/DD(요일) HH:MM #일정 · ...`
  - 오늘밤 중요 일정 없음: `오늘밤 조용함`
  - 다음 일정은 날짜별 한 줄, 같은 날짜는 `·`로 연결
- 서버 시작 시 영속 일정 캐시를 먼저 읽고 백그라운드 갱신합니다.
- 경제지표 소스가 하나 실패해도 다른 공식 소스와 실적 일정은 계속 표시합니다.
- `__pycache__`, `*.pyc` 제외
