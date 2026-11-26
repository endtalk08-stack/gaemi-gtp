# DigitalOcean 운영 게이트웨이 (main)

## 고정된 배포 통로

- 저장소: `endtalk08-stack/gaemi-gtp`
- 브랜치: `main`
- GitHub Actions: `.github/workflows/do-gateway.yml`
- 작업 요청: `.github/do-gateway/request.json`
- GitHub Environment: `digitalocean-news-worker` (기존 설정 재사용)
- SSH: 기존 `DO_HOST`, `NEWS_DEPLOY_SSH_KEY`, `NEWS_SSH_KNOWN_HOSTS`만 사용
- 서버 제한 계정: `gaemi-deploy`
- 원격 실행: `sudo -n /usr/local/sbin/gaemi-do-gateway` (서버측 명령 화이트리스트)
- 애플리케이션 경로: `/opt/gaemigtp-news/app`

## 언제 실행되나

1. GitHub Actions 화면에서 **DigitalOcean project management gateway** → **Run workflow**를 실행하면 **읽기 전용 상태 조회(status)**만 수행한다.
2. `main`의 **`.github/do-gateway/request.json` 파일을 명시적으로 수정해 push**하면 해당 요청을 검증 후 실행한다. 배포·재시작은 반드시 이 단계로 별도 요청해야 한다.
3. 보통의 `main` 커밋, `backend/**` 변경, `frontend/**` 변경, Cloudflare Pages 배포만으로 DigitalOcean은 **배포되거나 재시작되지 않는다**.
4. 기존 `ops/do-ssh-deploy-setup-20261017` 브랜치와 그 임시 진단 도구는 옮기거나 삭제하지 않는다. 재사용할 운영 코드는 검증해서 `main`에 올리고, 단발성 작업 스크립트는 작업 브랜치에 둔다.

## 운영 요청 예시 (한 번에 한 명령)

작업 파일은 실제 실행될 요청 하나만 담아야 하며, 허용된 필드만 사용할 수 있다.

```json
{"operation":"status"}
```

```json
{"operation":"logs","unit":"gaemigtp-kiwoom-us-top20-https.service","lines":100}
```

```json
{"operation":"deploy","path":"backend/kiwoom_us_top20_api.py","target":"backend/kiwoom_us_top20_api.py"}
```

```json
{"operation":"restart","unit":"gaemigtp-kiwoom-us-top20-https.service"}
```

위의 `deploy`는 GitHub 체크아웃된 파일의 Git blob 해시를 서버에 함께 제출한다. 요청 파일을 변경하기 전에 대상 소스가 반드시 `main`에 있어야 한다. 복사·재시작 권한과 실제 대상 경로는 서버의 `gaemi-do-gateway`가 최종 심사한다.

## GitHub Environment 배포 브랜치 허용 확인 (2026-11-24)

**현재 추가 설정 필요:** `digitalocean-news-worker` Environment의 사용자 지정 Deployment branches 정책에는 `ops/do-ssh-deploy-setup-20261017`만 등록되어 있다. 따라서 `main`에서 시작한 첫 읽기 전용 상태 조회(실행 45279068400)가 **SSH 단계 이전**에 거부되었다.

GitHub 저장소 **Settings → Environments → digitalocean-news-worker → Deployment branches and tags**에서 기존 브랜치를 삭제하지 말고 **`main`을 추가 허용**해야 한다. 기존 Environment Secrets는 그대로 재사용할 수 있으며, 키를 새로 만들거나 브라우저에 복사할 필요는 없다.

이 설정을 수정한 뒤 GitHub Actions → DigitalOcean project management gateway → **Run workflow** → `main`에서 읽기 전용 `status`로 연결 성공을 재검증한다. 연결 성공 전에는 `deploy` 또는 `restart`를 진행하지 않는다.

## 운영 시 주의

- 서버 배포와 서비스 재시작은 별개다. 각각의 요청과 성공 여부를 GitHub Actions 실행 기록으로 확인한다.
- 서버 반영 전 소스 검증 및 가능한 회귀 테스트를 실행한다. 변경 전 서버 파일과 서비스 상태를 확인한다.
- API 토큰·비밀번호·SSH 키 값을 저장소나 요청 JSON에 넣지 않는다.
- 원격 게이트웨이는 기존 서버에 이미 설치되어 있어야 한다. `main`에 워크플로를 복구하는 것 자체는 서버 설정이나 시세 데이터를 수정하지 않는다.
- `gaemigtp`(하이픈 없는 별도 HTS 저장소), HTS 자동매매·Supabase·주문 관련 시스템은 이 배포 경로의 대상이 아니다.

## 시세 서비스 원본 동기화 (2026-11-26)

`gaemigtp-kiwoom-us-top20-api/https.service`(거래대금 TOP20, 업종 지도, SPY·DIA)가 쓰는 파일은
서버에서 실제로 실행 중인 버전으로 `main`에 맞춰 두었다.

- `backend/kiwoom_us_top20_api.py`, `backend/kiwoom_us_live_prices.py`, `backend/us_quote_change.py`,
  `backend/providers/kiwoom_us_industries.py`, `ops/systemd/gaemigtp-kiwoom-us-top20-*.service`
- 이 파일을 서버에 올릴 때는 반드시 `main`의 현재 버전을 기준으로 수정한다. 예전 사본이나
  작업 브랜치의 오래된 파일을 그대로 `deploy`하면 이미 고친 문제가 되살아난다.
- `.github/workflows/us-quote-service-check.yml`이 `main`과 배포 브랜치에서 아래 재발 방지 테스트를 실행한다.
  - 장이 닫혀 있을 때 업종 ETF가 마지막 거래일 종가 등락률을 보여줄 것
  - 장 마감 뒤(휴장일·주말·장 시작 전) 저장된 TOP20 파일의 등락률을 버리지 않을 것
  - 화면 요청이 키움 ETF 갱신을 기다리지 않을 것, ETF 거래소 목록은 하루 캐시할 것
  - 두 서비스가 `/var/lib/gaemigtp-news`에 마지막 종가 파일을 쓸 수 있을 것
