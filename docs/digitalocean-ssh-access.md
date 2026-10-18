# DigitalOcean 뉴스 워커 SSH 접속 (GitHub Actions)

## 목적과 범위

DigitalOcean은 뉴스 수집·중복 제거·검증·가공을 담당하고, Neon은 저장, Render는 조회와 화면 제공을 담당한다. 서버 이전을 검증한 후에만 Render 중복 작업을 제거한다.

검증한 SSH 연결을 **상태 확인 전용, 수동 실행**으로 보관한다. 임의 원격 명령 실행이나 배포는 이 워크플로에서 허용하지 않는다.

- 워크플로: `.github/workflows/do-worker-connection-check.yml` — `main`
- GitHub Actions 환경: `digitalocean-news-worker`
- 원격 사용자: `gaemi-deploy` (root 아님)
- 점검 대상: `/opt/gaemigtp-news/app/backend` 존재 여부, `gaemigtp-news.service` 활성 상태
- 최초 검증: https://github.com/endtalk08-stack/gaemi-gtp/actions/runs/39166246923/attempts/2

## 비밀정보 보관

GitHub **Settings → Environments → digitalocean-news-worker**의 Secrets 또는 조직 정책에 따른 허용된 Actions Secrets에 아래 이름으로 보관한다. **값은 Git, README, 채팅, PR, 로그에 남기지 않는다.**

| Secret | 용도 |
|---|---|
| `DO_HOST` | 원격 서버 주소 |
| `NEWS_DEPLOY_SSH_KEY` | 배포 전용 계정의 비공개 SSH 키 |
| `NEWS_SSH_KNOWN_HOSTS` | 독립적으로 신원 확인을 마친 서버의 호스트 공개키 |

워크플로에서 `ssh-keyscan`으로 처음 접속한 호스트를 자동 신뢰하지 않는다. 저장된 호스트 공개키와 `StrictHostKeyChecking=yes`로 검증한다. 서버 개인키/호스트키 지문 원문을 코드나 문서에 기록하지 않는다.

## 수동 접속 확인

1. GitHub 저장소에서 **Actions → DigitalOcean worker SSH connection check** 선택
2. **Run workflow → Branch: `main` → Run workflow**
3. GitHub Environment 승인 정책이 있다면 승인 후 실행
4. `inspect-only` 로그에서 아래 상태 확인

```text
SSH_CONNECTION_OK user=gaemi-deploy
WORKER_SERVICE=active
```

오류가 발생하면 Secret 구성, 서버 호스트키, 계정 권한, systemd 상태를 확인한다. 해결을 위해 개인키를 공개하거나 호스트키 검증을 끄지 않는다.

## 보안 정책

- **수동 실행 전용:** push/PR/schedule 자동 SSH 접속 없음
- **브랜치 제한:** `main`에서만 실행하도록 job 조건으로 제한
- **최소 권한:** GitHub `GITHUB_TOKEN`은 `contents: read`만, 원격 계정은 `gaemi-deploy`; 원격 실행은 읽기 전용 명령으로 고정
- **키 보호:** 권한 `600`의 임시 파일 사용, 끝나면 삭제, 비밀값 출력 금지
- **서버 변경:** 별도 PR에서 작업·명령을 검토하고 별도 전용 워크플로를 만들 것. 이 점검 워크플로에 사용자 입력 명령을 추가하지 않는다.
- **침해 대응:** 키 유출이 의심되면 새 SSH 키 발급, 서버의 구 키 폐기, GitHub Secrets 갱신. 호스트키 변경은 별도 채널로 검증.
- **관리자 설정 필요:** `Settings → Environments → digitalocean-news-worker`에서 Required reviewers, deployment branches 제한을 확인·설정한다. `main`에는 보호 규칙 또는 Ruleset(승인·필수 CI·강제 push 차단)을 활성화한다. **이 파일을 커밋하는 것만으로 해당 설정이 켜지지 않는다.**
- **미검증 영역:** 서버 계정의 sudo/authorized_keys 명령 제한, 환경 승인 규칙 등은 별도 서버·관리자 권한으로 확인해야 한다. SSH 연결 성공은 권한 최소화의 증명이 아니다.

뉴스 수집·AI 모델·토큰 제한·Neon TTL·Render 코드는 이 변경에서 건드리지 않는다.
