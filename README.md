# gaemiGTP

## 실행 기준 경로

- `app.py`: Flask와 API 진입점
- `backend/`: 서버 데이터 수집·가공 로직
- `frontend/`: Render와 GitHub Pages가 배포하는 유일한 화면 코드
- `requirements.txt`: Render Python 의존성

Render는 `frontend/index.html`을 서비스합니다. GitHub Pages 배포도 `.github/workflows/deploy-pages.yml`이 같은 `frontend/`만 배포합니다.

`docs/architecture/`에는 현재 구조와 이후 데이터 분리 계획을 기록합니다.
