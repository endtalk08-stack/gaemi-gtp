# gaemiGTP 경제일정 API 교체

- 경제일정은 Finance Calendar 단일 피드(`/calendar`)를 사용한다.
- 기업 실적은 기존 Finnhub earnings API만 유지한다.
- 경제 캘린더 후보: CPI, PPI, 고용보고서(NFP), 신규실업수당청구건수, PCE, GDP, FOMC, ISM 제조업/서비스 PMI, 소매판매, 신규주택판매, 주택착공, 건축허가, JOLTS, ADP 고용, 원유재고.
- 경제 일정은 서버 캐시에 저장하므로 `/analyze`마다 외부 일정 API를 호출하지 않는다.
- Finance Calendar의 사용 조건에 따라 화면 일정 하단에 `financecalendar.com` 출처 링크를 표시한다.
- 날짜별 일정 그룹화와 `오늘밤` 한 줄 표시는 유지한다.
