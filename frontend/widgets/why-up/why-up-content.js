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

  const COMPACT_CONTENT = CONTENT
    .split('\n')
    .map(line => line.trim())
    .filter(Boolean)
    .join('\n');

  const STORY_ROWS = [
    ['09:00', '시초가 +1.5% 상승 출발'],
    ['09:15', '1분봉 거래대금 평소 대비 4.2배 폭발'],
    ['09:20', '5분봉 거래대금 평소 대비 2.1배 폭발'],
    ['09:30', '개미 인기 종목 순위 1위 등극'],
    ['09:40', '20일선 돌파'],
    ['09:50', '볼린저밴드 상단 돌파'],
    ['09:15', '거래대금 순위 3위 등극!'],
    ['09:30', '상승률 1위 등극! 상한가 터짐!'],
  ];

  const TAGS = '#삼성전자 #국장살려 #거래대금폭발 #상한가 #주식스타그램 #주식일기 #재테크기록';

  function escapeHtml(value) {
    return String(value || '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function emphasizeSignals(value) {
    return escapeHtml(value).replace(
      /(\+\d+(?:\.\d+)?%|\d+(?:\.\d+)?배 폭발|\d+일선 돌파|볼린저밴드 상단 돌파|\d위 등극!?|상한가)/g,
      '<span class="why-up-story__signal">$1</span>'
    );
  }

  function render(variant) {
    const type = variant === 'widget' ? 'why-up-story--widget' : 'why-up-story--main';
    const rows = STORY_ROWS.map(([time, detail]) => `
      <div class="why-up-story__row">
        <time class="why-up-story__time">${time}</time>
        <span class="why-up-story__detail">${emphasizeSignals(detail)}</span>
      </div>`).join('');

    return `<section class="why-up-story ${type}">
      <p class="why-up-story__intro">오늘 신났네 ㅎㅎ</p>
      <div class="why-up-story__timeline">${rows}</div>
      <p class="why-up-story__tags">${escapeHtml(TAGS)}</p>
    </section>`;
  }

  window.GaemiGTPWhyUpContent = Object.freeze({
    get: () => CONTENT,
    getCompact: () => COMPACT_CONTENT,
    render,
  });
}());
