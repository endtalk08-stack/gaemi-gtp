/* 주요일정: Toss-style weekly calendar (날짜 · 일정 · 발표 · 예측 · 이전) in the left sidebar home.
   Data: GaemiGTPSchedule.setItems([{ time, title, country, actual, forecast, previous, holiday }]).
   time is an ISO timestamp; the table is shown in Korean time, grouped by week (Mon–Sun) and
   labelled by the month of the week's Thursday ("11월 4주차"). */
(function () {
  'use strict';
  const KST_OFFSET = 9 * 3600 * 1000;
  const DAYS = ['일', '월', '화', '수', '목', '금', '토'];
  let items = [];
  const esc = v => String(v == null ? '' : v).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[c]));
  const kst = ms => new Date(ms + KST_OFFSET);            // read with getUTC* = Korean wall clock
  const dayKey = d => d.toISOString().slice(0, 10);

  function weekStart(d) {                                   // Monday of the Korean week
    const s = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
    s.setUTCDate(s.getUTCDate() - ((s.getUTCDay() + 6) % 7));
    return s;
  }
  function weekLabel(monday) {
    const thu = new Date(monday); thu.setUTCDate(thu.getUTCDate() + 3);
    const first = new Date(Date.UTC(thu.getUTCFullYear(), thu.getUTCMonth(), 1));
    const firstThu = new Date(first); firstThu.setUTCDate(1 + ((4 - first.getUTCDay() + 7) % 7));
    return (thu.getUTCMonth() + 1) + '월 ' + (Math.round((thu - firstThu) / 604800000) + 1) + '주차';
  }
  function timeText(d) {
    const h = d.getUTCHours(), m = d.getUTCMinutes();
    return (h < 12 ? '오전 ' : '오후 ') + ((h % 12) || 12) + '시' + (m ? ' ' + m + '분' : '');
  }
  function num(v) {
    const n = parseFloat(String(v == null ? '' : v).replace(/[^0-9.+-]/g, ''));
    return Number.isFinite(n) ? n : null;
  }
  function flag(country) {
    if (country !== 'US') return '';
    return '<svg class="gsc-flag" viewBox="0 0 14 10" aria-label="미국"><rect width="14" height="10" fill="#fff"/>'
      + [0, 2, 4, 6, 8].map(y => '<rect y="' + y + '" width="14" height="1" fill="#d22f3c"/>').join('')
      + '<rect width="6" height="5" fill="#2d4a8a"/></svg>';
  }
  function row(item, showDate, todayKey) {
    const d = kst(Date.parse(item.time));
    const key = dayKey(d);
    const date = showDate ? '<span class="gsc-date' + (key === todayKey ? ' gsc-date--today' : '') + '">'
      + d.getUTCDate() + '일 (' + DAYS[d.getUTCDay()] + ')</span>' : '<span></span>';
    if (item.holiday) {
      return '<div class="gsc-row">' + date + '<span class="gsc-title"><span class="gsc-pin">📍</span>' + esc(item.title) + '</span></div>';
    }
    const title = '<span class="gsc-title">' + flag(item.country) + '<span>' + esc(item.title) + '</span></span>';
    const released = item.actual != null && item.actual !== '';
    if (!released) {
      return '<div class="gsc-row">' + date + title + '<span class="gsc-pending">' + timeText(d) + ' 발표 예정</span></div>';
    }
    const a = num(item.actual), f = num(item.forecast);
    const tone = a != null && f != null && a !== f ? (a > f ? ' gsc-num--up' : ' gsc-num--down') : '';
    return '<div class="gsc-row">' + date + title
      + '<span class="gsc-num gsc-num--actual' + tone + '">' + esc(item.actual) + '</span>'
      + '<span class="gsc-num gsc-num--forecast">' + esc(item.forecast ?? '') + '</span>'
      + '<span class="gsc-num gsc-num--previous">' + esc(item.previous ?? '') + '</span></div>';
  }
  // The same table in every place it is shown: the left sidebar section and the 주요일정 widget.
  function render() {
    document.querySelectorAll('[data-schedule-root]').forEach(renderInto);
  }
  function renderInto(host) {
    const valid = items.filter(i => i && typeof i.title === 'string' && Number.isFinite(Date.parse(i.time)))
      .sort((a, b) => Date.parse(a.time) - Date.parse(b.time));
    if (!valid.length) { host.innerHTML = '<div class="gsc-placeholder">주요일정이 여기에 표시됩니다</div>'; return; }
    const todayKey = dayKey(kst(Date.now()));
    const weeks = new Map();
    for (const item of valid) {
      const monday = weekStart(kst(Date.parse(item.time)));
      const k = dayKey(monday);
      if (!weeks.has(k)) weeks.set(k, { monday, items: [] });
      weeks.get(k).items.push(item);
    }
    host.innerHTML = '<div class="gsc">' + [...weeks.values()].map(w => {
      let lastDay = '';
      const rows = w.items.map(item => {
        const k = dayKey(kst(Date.parse(item.time)));
        const html = row(item, k !== lastDay, todayKey);
        lastDay = k;
        return html;
      }).join('');
      return '<section class="gsc-week"><h3 class="gsc-week__title">' + weekLabel(w.monday) + '</h3><div class="gsc-table">'
        + '<div class="gsc-row gsc-row--head"><span>날짜</span><span>일정</span><span class="gsc-num">발표</span>'
        + '<span class="gsc-num">예측</span><span class="gsc-num">이전</span></div>' + rows + '</div></section>';
    }).join('') + '</div>';
  }
  function setItems(list) { items = Array.isArray(list) ? list : []; render(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', render); else render();
  window.GaemiGTPSchedule = { setItems, render };
}());
