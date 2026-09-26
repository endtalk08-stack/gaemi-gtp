/* Why Up — fixed content shared by the main analysis body and plugin widget. */
(function () {
  'use strict';

  const CONTENT = `오늘 신났네 ㅎㅎ

09:00   시초가 +1.5% 상승 출발

09:15   1분봉 거래대금 평소 대비 4.2배 폭발

09:20   5분봉 거래대금 평소 대비 2.1배 폭발

09:30   개미 인기 종목 순위 1위 등극

09:40   20일선 돌파

09:50   볼린저밴드 상단 돌파

09:15   거래대금 순위 3위 등극!

09:30   상승률 1위 등극! 상한가 터짐!

#삼성전자 #국장살려 #거래대금폭발 #상한가 #주식스타그램 #주식일기 #재테크기록`;

  window.GaemiGTPWhyUpContent = Object.freeze({ get: () => CONTENT });
}());
