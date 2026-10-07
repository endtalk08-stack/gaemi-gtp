(function () {
  'use strict';

  function bindTabs(selector) {
    document.querySelectorAll(selector).forEach((button) => {
      button.addEventListener('click', () => {
        document.querySelectorAll(selector).forEach((item) => {
          const active = item === button;
          item.classList.toggle('is-active', active);
          item.setAttribute('aria-selected', String(active));
        });
      });
    });
  }

  function renderToday() {
    const now = new Date();
    const date = document.getElementById('earningsCalendarDate');
    const label = document.getElementById('earningsCalendarDayLabel');
    if (!date || !label) return;

    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const weekdays = ['일', '월', '화', '수', '목', '금', '토'];
    date.textContent = `${year}.${month}.${day}`;
    label.textContent = `${now.getMonth() + 1}월 ${now.getDate()}일 ${weekdays[now.getDay()]}요일`;
  }

  document.addEventListener('DOMContentLoaded', () => {
    bindTabs('[data-calendar-mode]');
    bindTabs('[data-calendar-importance]');
    renderToday();
  });
}());
