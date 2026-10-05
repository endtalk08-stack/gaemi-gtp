(() => {
  const trigger = document.getElementById('stockToolsTrigger');
  const menu = document.getElementById('stockToolsMenu');
  const openButton = document.getElementById('stockCalculatorMenuItem');
  const chatArea = document.getElementById('chatArea');

  if (!trigger || !menu || !openButton || !chatArea) return;

  const tabs = [
    { id: 'average', label: '평단' },
    { id: 'water', label: '물타기' },
    { id: 'return', label: '수익률' },
    { id: 'breakeven', label: '본전' },
    { id: 'target', label: '목표가' }
  ];

  const modes = {
    average: {
      fields: [
        { key: 'p1', label: '1차 매수가', placeholder: '80,000' },
        { key: 'q1', label: '1차 수량', placeholder: '100' },
        { key: 'p2', label: '2차 매수가', placeholder: '70,000' },
        { key: 'q2', label: '2차 수량', placeholder: '50' }
      ],
      validate(v) {
        return v.p1 > 0 && v.q1 > 0 && v.p2 > 0 && v.q2 > 0
          ? ''
          : '가격과 수량을 0보다 크게 입력해 주세요.';
      },
      calculate(v) {
        const totalQty = v.q1 + v.q2;
        const totalCost = (v.p1 * v.q1) + (v.p2 * v.q2);
        return [
          ['새 평단', totalCost / totalQty, 'won', true],
          ['총 보유 수량', totalQty, 'shares'],
          ['총 투자금', totalCost, 'won']
        ];
      }
    },
    water: {
      fields: [
        { key: 'avg', label: '현재 평단', placeholder: '80,000' },
        { key: 'qty', label: '보유 수량', placeholder: '100' },
        { key: 'addPrice', label: '추가 매수가', placeholder: '70,000' },
        { key: 'addQty', label: '추가 수량', placeholder: '50' }
      ],
      validate(v) {
        return v.avg > 0 && v.qty > 0 && v.addPrice > 0 && v.addQty > 0
          ? ''
          : '평단, 매수가, 수량을 0보다 크게 입력해 주세요.';
      },
      calculate(v) {
        const totalQty = v.qty + v.addQty;
        const totalCost = (v.avg * v.qty) + (v.addPrice * v.addQty);
        return [
          ['새 평단', totalCost / totalQty, 'won', true],
          ['총 보유 수량', totalQty, 'shares'],
          ['총 투자금', totalCost, 'won'],
          ['평단 변화', (totalCost / totalQty) - v.avg, 'signedWon']
        ];
      }
    },
    return: {
      fields: [
        { key: 'avg', label: '평균 매수가', placeholder: '80,000' },
        { key: 'current', label: '현재가', placeholder: '70,000' },
        { key: 'qty', label: '보유 수량', placeholder: '100' }
      ],
      validate(v) {
        return v.avg > 0 && v.current >= 0 && v.qty > 0
          ? ''
          : '매수가와 수량은 0보다 크게, 현재가는 0 이상으로 입력해 주세요.';
      },
      calculate(v) {
        const invested = v.avg * v.qty;
        const evaluation = v.current * v.qty;
        const profit = evaluation - invested;
        const rate = ((v.current / v.avg) - 1) * 100;
        return [
          ['평가손익', profit, 'signedWon', true],
          ['수익률', rate, 'percent'],
          ['매수금액', invested, 'won'],
          ['평가금액', evaluation, 'won']
        ];
      }
    },
    breakeven: {
      fields: [
        { key: 'avg', label: '평균 매수가', placeholder: '80,000' },
        { key: 'current', label: '현재가', placeholder: '70,000' }
      ],
      validate(v) {
        return v.avg > 0 && v.current > 0
          ? ''
          : '평균 매수가와 현재가를 0보다 크게 입력해 주세요.';
      },
      calculate(v) {
        const rate = ((v.avg / v.current) - 1) * 100;
        const gap = v.avg - v.current;
        return [
          ['본전 가격', v.avg, 'won', true],
          ['필요 등락률', rate, 'percent'],
          ['현재가와 차이', gap, 'signedWon']
        ];
      }
    },
    target: {
      fields: [
        { key: 'price', label: '기준 가격', placeholder: '70,000' },
        { key: 'rate', label: '목표 수익률 (%)', placeholder: '10', allowNegative: true }
      ],
      validate(v) {
        if (!(v.price > 0)) return '기준 가격을 0보다 크게 입력해 주세요.';
        if (!(v.rate > -100)) return '목표 수익률은 -100%보다 크게 입력해 주세요.';
        return '';
      },
      calculate(v) {
        const target = v.price * (1 + (v.rate / 100));
        return [
          ['목표 가격', target, 'won', true],
          ['기준가 대비', target - v.price, 'signedWon'],
          ['목표 수익률', v.rate, 'percent']
        ];
      }
    }
  };

  const formatNumber = (value, maximumFractionDigits = 2) =>
    Number(value).toLocaleString('ko-KR', { maximumFractionDigits });

  const formatValue = (value, type) => {
    if (type === 'won') return `${formatNumber(Math.round(value), 0)}원`;
    if (type === 'signedWon') {
      const rounded = Math.round(value);
      const sign = rounded > 0 ? '+' : '';
      return `${sign}${formatNumber(rounded, 0)}원`;
    }
    if (type === 'shares') return `${formatNumber(value, 4)}주`;
    if (type === 'percent') {
      const sign = value > 0 ? '+' : '';
      return `${sign}${formatNumber(value, 2)}%`;
    }
    return formatNumber(value);
  };

  const parseValue = (raw) => {
    const cleaned = String(raw || '').replace(/[,s원주%]/g, '');
    if (cleaned === '') return NaN;
    const value = Number(cleaned);
    return Number.isFinite(value) ? value : NaN;
  };

  const closeMenu = () => {
    menu.hidden = true;
    trigger.setAttribute('aria-expanded', 'false');
  };

  const toggleMenu = () => {
    const shouldOpen = menu.hidden;
    if (shouldOpen) document.getElementById('bottomModeMenu')?.classList.add('hidden');
    menu.hidden = !shouldOpen;
    trigger.setAttribute('aria-expanded', shouldOpen ? 'true' : 'false');
    if (shouldOpen) openButton.focus();
  };

  const createCalculator = () => {
    const existing = document.getElementById('gaemiStockCalculatorCard');
    if (existing) {
      existing.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      return;
    }

    let activeMode = 'average';
    let lastCopyText = '';

    const message = document.createElement('section');
    message.className = 'stock-calculator-message';
    message.setAttribute('aria-label', '주식 계산기');
    message.innerHTML = `
      <div id="gaemiStockCalculatorCard" class="stock-calculator-card">
        <div class="stock-calculator-head">
          <div>
            <h2 class="stock-calculator-title">주식 계산기</h2>
            <p class="stock-calculator-subtitle">필요한 값만 입력하면 바로 계산합니다.</p>
          </div>
        </div>
        <div class="stock-calculator-tabs" role="tablist" aria-label="계산 종류"></div>
        <form class="stock-calculator-form" novalidate>
          <div class="stock-calculator-fields"></div>
          <div class="stock-calculator-validation" aria-live="polite"></div>
          <div class="stock-calculator-actions">
            <button class="stock-calculator-action" type="submit">계산</button>
          </div>
        </form>
        <div class="stock-calculator-result" hidden aria-live="polite">
          <div class="stock-calculator-result-head">
            <span class="stock-calculator-result-title">계산 결과</span>
          </div>
          <div class="stock-calculator-result-rows"></div>
        </div>
      </div>
    `;

    const tabWrap = message.querySelector('.stock-calculator-tabs');
    const form = message.querySelector('.stock-calculator-form');
    const fieldWrap = message.querySelector('.stock-calculator-fields');
    const validation = message.querySelector('.stock-calculator-validation');
    const result = message.querySelector('.stock-calculator-result');
    const resultRows = message.querySelector('.stock-calculator-result-rows');

    const removeResultActions = () => {
      message.querySelector('[data-reply-actions="stock-calculator"]')?.remove();
    };

    const renderTabs = () => {
      tabWrap.innerHTML = '';
      tabs.forEach((tab) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = `stock-calculator-tab${tab.id === activeMode ? ' is-active' : ''}`;
        button.textContent = tab.label;
        button.setAttribute('role', 'tab');
        button.setAttribute('aria-selected', tab.id === activeMode ? 'true' : 'false');
        button.addEventListener('click', () => {
          if (activeMode === tab.id) return;
          activeMode = tab.id;
          lastCopyText = '';
          removeResultActions();
          renderTabs();
          renderFields();
          result.hidden = true;
          validation.textContent = '';
        });
        tabWrap.appendChild(button);
      });
    };

    const renderFields = () => {
      fieldWrap.innerHTML = '';
      modes[activeMode].fields.forEach((field) => {
        const label = document.createElement('label');
        label.className = 'stock-calculator-field';

        const caption = document.createElement('span');
        caption.className = 'stock-calculator-label';
        caption.textContent = field.label;

        const input = document.createElement('input');
        input.className = 'stock-calculator-input';
        input.name = field.key;
        input.type = 'text';
        input.inputMode = 'decimal';
        input.autocomplete = 'off';
        input.placeholder = field.placeholder;
        input.setAttribute('aria-label', field.label);

        label.append(caption, input);
        fieldWrap.appendChild(label);
      });
    };

    const readValues = () => {
      const values = {};
      for (const field of modes[activeMode].fields) {
        const input = form.elements.namedItem(field.key);
        const value = parseValue(input?.value);
        if (!Number.isFinite(value)) {
          return { error: '모든 값을 숫자로 입력해 주세요.' };
        }
        if (!field.allowNegative && value < 0) {
          return { error: '음수는 입력할 수 없습니다.' };
        }
        values[field.key] = value;
      }
      return { values };
    };

    const renderResult = (rows) => {
      resultRows.innerHTML = '';
      const plain = ['주식 계산기 결과'];

      rows.forEach(([label, value, type, primary]) => {
        const row = document.createElement('div');
        row.className = `stock-calculator-result-row${primary ? ' is-primary' : ''}`;

        const key = document.createElement('span');
        key.className = 'stock-calculator-result-label';
        key.textContent = label;

        const output = document.createElement('span');
        output.className = 'stock-calculator-result-value';
        output.textContent = formatValue(value, type);

        row.append(key, output);
        resultRows.appendChild(row);
        plain.push(`${label}: ${output.textContent}`);
      });

      lastCopyText = plain.join('\n');
      result.hidden = false;

      removeResultActions();
      window.GaemiGTPFirstReplyActions?.appendFirstReplyActions(
        result,
        lastCopyText,
        'stock-calculator',
        '주식 계산기'
      );

      result.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    };

    form.addEventListener('submit', (event) => {
      event.preventDefault();
      validation.textContent = '';

      const read = readValues();
      if (read.error) {
        validation.textContent = read.error;
        result.hidden = true;
        removeResultActions();
        return;
      }

      const error = modes[activeMode].validate(read.values);
      if (error) {
        validation.textContent = error;
        result.hidden = true;
        removeResultActions();
        return;
      }

      renderResult(modes[activeMode].calculate(read.values));
    });

    renderTabs();
    renderFields();
    chatArea.appendChild(message);
    message.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  };

  trigger.addEventListener('click', (event) => {
    event.stopPropagation();
    toggleMenu();
  });

  openButton.addEventListener('click', () => {
    closeMenu();
    createCalculator();
  });

  document.addEventListener('click', (event) => {
    if (!menu.hidden && !menu.contains(event.target) && event.target !== trigger) closeMenu();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !menu.hidden) {
      closeMenu();
      trigger.focus();
    }
  });

  window.openStockCalculatorInChat = createCalculator;
})();
