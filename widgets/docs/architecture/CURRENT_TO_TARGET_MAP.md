# 현재 파일 → 목표 구조 매핑

| 현재 | 목표 | 처리 |
|---|---|---|
| `app.py` | `app.py` | 유지. 향후 얇은 진입점으로 정리 |
| `frontend/index.html` | `frontend/shell` + `frontend/pages` | 현재 유지, UI를 한 단계씩 분리 |
| `frontend/css/app.css` | `frontend/shell`/위젯 스타일 | 현재 유지, 스타일은 기능 단위로 점진 분리 |
| `frontend/js/app.js` | `frontend/shell` + `pages` + `widgets` | 현재 역할 혼합. 가장 늦게 쪼갬 |
| `frontend/widgets/news-widget.js` | `frontend/widgets/news/` | 독립 위젯으로 정리 대상 |
| `backend/services/engine.py` | `backend/data` + `backend/analysis` + 일부 `backend/core` | 역할을 먼저 분석한 후 단계적 분리 |
| `backend/services/news.py` | `backend/data/news` + `backend/analysis/news` | 수집/필터/점수 책임 분리 대상 |
| `backend/services/market_levels.py` | `backend/analysis/levels` | 분석 모듈 분리 대상 |
| `backend/services/warmup.py` | `backend/data`/인프라 영역 | 역할 확인 후 이동 |
| `backend/database/` | `backend/database/` | 유지 |
| `backend/cache/` | `backend/cache/` | 유지 |
| `frontend/admin/` | `frontend/admin/` | 사용자 화면과 분리 유지 |
| `/admin` API/기능 | `backend/admin/` | 사용자 API와 분리 대상 |


## Phase 2.1 완료
- 오른쪽 패널 폭/리사이즈 컨트롤 → `frontend/shell/right-panel/right-panel.js`
- 오른쪽 패널 shell 스타일 → `frontend/shell/right-panel/right-panel.css`
- 패널의 열기/닫기/최대화 상태 전환은 현재 `frontend/js/app.js`에서 유지 (다음 분리 단계에서 검토)
