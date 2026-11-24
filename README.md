# gaemiGTP

## 운영 원본과 배포 기준

- GitHub 저장소: `endtalk08-stack/gaemi-gtp`
- 운영 원본 브랜치: `main`
- 운영 Cloudflare Pages 프로젝트: `gaemigtp-main`
- 운영 주소: https://gaemigtp-main.pages.dev
- 정적 파일 출력 디렉터리: `frontend/`
- Pages Functions 디렉터리: 저장소 최상위 `functions/`
- 단일 배포 워크플로: `.github/workflows/gaemigtp-main-pages-news-production.yml`

## 작업 및 배포 순서

1. `main`에서 작업 브랜치를 만든다.
2. 관련 JS, CSS, HTML, Functions 변경을 한 작업 브랜치에 모은다.
3. `scripts/pages/verify-pages-inputs.mjs`와 Pages Functions 빌드 검사를 통과시킨다.
4. `main` 대상 Pull Request를 열면 같은 PR 병합 커밋을 기존 Pages 프로젝트의 미리보기 환경에 배포한다.
5. 미리보기의 HTML, 모든 로컬 JS/CSS 및 중첩 리소스를 원본과 바이트 단위로 비교하고 Functions/R2 응답을 확인한다.
6. 검증된 PR만 `main`에 병합한다. 병합 후 같은 워크플로가 운영 배포하고 동일한 검사를 다시 실행한다.

## 보호 규칙

- `main`에 파일별로 여러 번 연속 커밋하지 않는다. 함께 변경되어야 하는 파일은 한 커밋으로 묶는다.
- Cloudflare 대시보드의 수동 파일 업로드나 별도 Wrangler 명령으로 운영 배포하지 않는다.
- 배포 시 저장소의 `frontend/`와 최상위 `functions/`를 임시 작업공간에 그대로 복사하고, 그 임시공간 루트에서 Wrangler를 실행한다. 원본 저장소에 Wrangler 설치 파일이나 node_modules가 생기지 않게 한다.
- 기존 Pages 프로젝트 설정과 `DATA_R2` 바인딩을 새로 만들거나 변경하지 않는다.
- 과거 `ops/gaemigtp-main-pages-preview`, `feat/pages-r2-daily-chart-20261110`, `fix/pages-quote-chart-path-20261110`, `work/spy-dia-pages-preview-20261122` 브랜치는 현재 `main`과 분기되어 있으므로 통째로 병합하지 않는다. 필요한 변경은 개별 파일과 커밋을 현재 `main`과 대조한 뒤 재적용한다.
- 운영 배포는 `main`의 단일 커밋을 기준으로 하며, 배포 후 모든 참조 파일이 해당 커밋의 파일과 일치해야 한다.

## 애플리케이션 구성

- `app.py`: Flask 및 API 진입점
- `backend/`: 서버 데이터 수집·가공 로직
- `frontend/`: Cloudflare Pages 정적 화면
- `functions/`: Cloudflare Pages API Functions
- `requirements.txt`: Python 의존성
