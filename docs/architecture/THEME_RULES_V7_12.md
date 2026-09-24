# Theme Rules — v7.12

## 목적
다크/라이트 모드를 새로 추가되는 Shell / Page / Widget에서도 처음부터 동일하게 지원한다.

## 기준
- 테마 상태는 `frontend/theme/theme.js` 한 곳에서 관리한다.
- 저장 키: `gaemiGTP_theme_v1`.
- 기본 테마: dark.
- 모든 신규 구조 모듈은 가능하면 `frontend/theme/theme.css`의 `--gtp-*` 토큰을 사용한다.
- 신규 모듈에서 별도의 `dark` 상태 저장/토글 로직을 만들지 않는다.
- 데이터/API/DB 로직에는 테마 상태를 넣지 않는다.

## 작업 원칙
1. 새 UI 추가 시 Light/Dark 두 상태의 색을 동시에 정한다.
2. 구조 작업과 데이터 작업을 섞지 않는다.
3. 기존 화면의 색을 한 번에 전면 교체하지 않는다.
