# Phase 2 — Right Panel

- [x] right-panel shell 경계 확정
- [x] right-panel CSS를 `frontend/shell/right-panel/right-panel.css`로 분리
- [x] right-panel 폭/리사이즈 컨트롤을 `frontend/shell/right-panel/right-panel.js`로 분리
- [x] dashboard 콘텐츠와 shell 책임 분리 기준 확정
- [x] 가운데 기존 데이터/API 변경 없음
- [ ] Dashboard 컨테이너 실제 배치 확정
- [ ] 위젯 배치/목록 확정
- [ ] 각 위젯 원천/가공 데이터 정의
- [ ] API 정의
- [ ] DB 저장 필요성 정의
- [ ] 실제 데이터 연결

## 이번 단계 원칙
오른쪽 패널의 열기/닫기 상태는 다른 shell과 협력해야 하므로 당분간 `app.js`가 조정한다. 패널의 순수한 폭/리사이즈 동작은 별도 shell controller가 담당한다.
