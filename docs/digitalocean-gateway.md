# DigitalOcean 공용 관리 통로 (2026-10-20)

대상: `gaemigtp-news-worker` DigitalOcean 서버 한 대. 기존 GitHub Actions의 `digitalocean-news-worker` 환경과 SSH 계정 `gaemi-deploy`를 재사용한다.

## 설치 상태

- GitHub Actions 스테이징: [성공한 실행](https://github.com/endtalk08-stack/gaemi-gtp/actions/runs/39378323146)
- 서버 스테이징 경로: `/home/gaemi-deploy/.gaemi-gateway/bootstrap/`
- 검증된 설치 스크립트 blob SHA: `26c7473f9fa74922706deb3ec78ca6ee785d85ad`
- 검증된 관리 프로그램 blob SHA: `dd1f50231f2ab1d36756b6bb24c2aca5b1035c42`
- **root 설치는 별도 승인·실행 필요**. GitHub에서 파일을 준비했다고 root 설치가 끝난 것은 아니다.

## 일회성 설치

Droplet Console에서 단 한 번 실행:

```bash
sudo bash -c 'p=/home/gaemi-deploy/.gaemi-gateway/bootstrap/install-once.sh; test "$(git hash-object "$p")" = 26c7473f9fa74922706deb3ec78ca6ee785d85ad && exec bash "$p"'
```

정상 출력: `GAEMI_GATEWAY_INSTALLED_AND_SSH_USER_VERIFIED`, `ORIGINAL_NEWS_WORKER_UNCHANGED`.

설치 후 `gaemi-deploy`는 root-owned `/usr/local/sbin/gaemi-do-gateway` 프로그램 **한 개만** 암호 없이 sudo로 실행할 수 있다. 서버 전체 명령에 대한 직접적인 `NOPASSWD:ALL`은 허용하지 않는다. 다만 gateway를 통한 코드 배포 및 후속 gateway 갱신은 높은 권한을 행사하므로 연결된 GitHub 및 SSH 키 접근은 보호해야 한다.

## 이후 요청 방법

요청 파일: `.github/do-gateway/request.json` (브랜치 `ops/do-ssh-deploy-setup-20261017`)

이 파일을 GitHub에 커밋하면 `.github/workflows/do-gateway.yml`이 자동으로 **한 번** 실행된다. 자동 주기나 뉴스 수집·AI 호출은 설정하지 않는다.

동작 예시 (한 번에 하나의 요청만 보내며 JSON 전체를 교체):

- 상태 확인: `{"operation":"status"}`
- 로그 확인: `{"operation":"logs","unit":"gaemigtp-news.service","lines":80}`
- 서비스 재시작: `{"operation":"restart","unit":"gaemigtp-news.service"}`
- 파일 배포: `{"operation":"deploy","path":"backend/services/us_market_close.py","target":"backend/services/us_market_close.py"}`
- AI/뉴스 테스트 실행: `{"operation":"run","path":"ops/jobs/us_close_test.py","request_id":"usclose-20261020-v2","timeout":180}`
- 관리 프로그램 확장: `{"operation":"upgrade","path":"ops/do-gateway/gaemi-do-gateway"}`

`run`은 root가 아니라 `gaemigtp-news` 전용 계정으로 실행하며 `/etc/gaemigtp/news-worker.env`를 전달한다. 테스트 `request_id`는 재사용하면 차단된다(재시도 중복 비용 방지). `deploy`는 프로젝트 backend/frontend/app.py 또는 `gaemigtp-` 접두사 systemd unit으로만 제한된다. 코드 파일은 해시 검증 후 배포하며 기존 파일은 `/var/backups/gaemi-gateway/`에 백업된다. 별도 재시작을 요청하기 전까지 기존 서비스를 재시작하지 않는다.

최초 관리자 설치 후 GitHub Actions에서 상태 확인 작업이 성공하는 것을 먼저 검증해야 한다. 서비스 적용 또는 AI 호출은 해당 작업 요청이 있을 때만 수행한다.
