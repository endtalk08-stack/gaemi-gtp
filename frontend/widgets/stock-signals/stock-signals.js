/* Stock signal card: a read-only view of backend stock_signals. */
(function () {
  'use strict';

  function render({ anchor, stockName, result }) {
    if (!anchor || !result || !anchor.isConnected) return;
    const signals = Array.isArray(result.stock_signals) ? result.stock_signals : [];
    if (!signals.length) return;
    const existing = anchor.parentElement?.querySelector('[data-gtp-stock-signals]');
    if (existing) existing.remove();

    const section = document.createElement('section');
    section.dataset.gtpStockSignals = 'true';
    section.className = 'gtp-stock-signals';
    const heading = document.createElement('h3');
    heading.className = 'gtp-stock-signals__heading';
    heading.textContent = '주가 변동 시그널';
    section.appendChild(heading);

    signals.filter(signal => signal && signal.stock === stockName).forEach(signal => {
      const button = document.createElement('button');
      button.className = 'gtp-stock-signals__row';
      button.type = 'button';
      const title = document.createElement('span');
      title.className = 'gtp-stock-signals__title';
      title.textContent = signal.title;
      const context = document.createElement('span');
      context.className = 'gtp-stock-signals__meta';
      const count = Array.isArray(signal.evidence) ? signal.evidence.length : 0;
      context.textContent = count
        ? '관련 원문 확인 ' + count + '건 · 근거 보기'
        : '변동 이유 미확인 · 근거 보기';
      button.append(title, context);
      button.addEventListener('click', () =>
        window.GaemiGTPRightPanelTabs?.showStockSignal?.(signal)
      );
      section.appendChild(button);
    });
    const note = document.createElement('p');
    note.className = 'gtp-stock-signals__note';
    note.textContent = '시세 변동과 관련 뉴스는 별개입니다. 원인이 검증되지 않으면 단정하지 않습니다.';
    section.appendChild(note);
    anchor.insertAdjacentElement('afterend', section);
  }

  window.GaemiGTPStockSignals = { render };
}());
