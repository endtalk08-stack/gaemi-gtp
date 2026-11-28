# KIS KRX 야간선물 실시간 수신 테스트

한국투자증권 실전투자 API의 시세 수신 전용 테스트 프로그램입니다.

- 실시간 체결 TR: H0MFCNT0
- 실시간 호가 TR: H0MFASP0
- 기본 종목 코드: 101W9000 (한국투자증권 공식 샘플에 기재된 예시 코드)
- 실전 WebSocket: ws://ops.koreainvestment.com:21000

주문·정정·취소 기능은 포함하지 않습니다.

## 실행 환경

기존 DigitalOcean 애플리케이션 서버 등 Python이 이미 설치된 환경에서 실행하도록 분리했습니다. 사용자 PC에 Python을 새로 설치하거나 gaemiGTP 웹사이트를 변경할 필요가 없습니다.

## 환경변수

- KIS_APP_KEY: 한국투자증권 실전투자 앱키
- KIS_APP_SECRET: 한국투자증권 실전투자 앱시크릿
- KIS_NIGHT_FUTURES_CODE: 구독할 야간선물 종목코드 (기본 101W9000)

앱키와 앱시크릿을 GitHub 코드, 커밋되는 파일, 로그, 채팅에 올리지 마세요. 서버의 비밀 환경변수로만 설정해야 합니다.

## 설치 및 실행

    python -m pip install -r tools/kis_night_futures/requirements.txt
    python tools/kis_night_futures/kis_night_futures_ws.py

체결만 받으려면 --trades-only, 호가만 받으려면 --quotes-only 옵션을 사용합니다.
종목코드는 --symbol 옵션으로 지정할 수 있습니다.

## 검증 기준

정상 연결 시 다음 로그가 반복 출력되어야 합니다.

- [체결] 현재가, 등락률, 체결량, 누적 거래량
- [호가] 매도 1호가·잔량, 매수 1호가·잔량

시장이 닫혀 있으면 연결 성공 후에도 실시간 체결 메시지가 오지 않을 수 있습니다. 연결 승인·구독 응답을 먼저 확인하고 실제 야간선물 거래 시간에 체결 수신을 검증해야 합니다.

## 공식 참고

- KIS Developers API 목록: https://apiportal.koreainvestment.com/apiservice-summary
- 한국투자증권 공식 Open Trading API 예제: https://github.com/koreainvestment/open-trading-api
- 공식 예제의 KRX 야간선물 체결 TR: H0MFCNT0
- 공식 예제의 KRX 야간선물 호가 TR: H0MFASP0

현재 이 프로그램은 독립 테스트 도구입니다. 운영 서버 설치·실행, 시세 저장, gaemiGTP 연결은 별도 승인 및 검증 후 진행합니다.
