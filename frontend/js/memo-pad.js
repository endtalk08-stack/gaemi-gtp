(() => {
  const openButton = document.getElementById('memoPadMenuItem');
  const chatArea = document.getElementById('chatArea');
  const STORAGE_KEY = 'gaemiGTP_chat_memo_v1';

  if (!openButton || !chatArea) return;

  const readSavedMemo = () => {
    try {
      return localStorage.getItem(STORAGE_KEY) || '';
    } catch (_) {
      return '';
    }
  };

  const saveMemo = (value) => {
    try {
      if (value) localStorage.setItem(STORAGE_KEY, value);
      else localStorage.removeItem(STORAGE_KEY);
      return true;
    } catch (_) {
      return false;
    }
  };

  const copyText = async (value) => {
    try {
      await navigator.clipboard.writeText(value);
      return true;
    } catch (_) {
      const textarea = document.createElement('textarea');
      textarea.value = value;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      const copied = document.execCommand('copy');
      textarea.remove();
      return copied;
    }
  };

  const createMemoPad = () => {
    const existing = document.getElementById('gaemiMemoPadCard');
    if (existing) {
      existing.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      existing.querySelector('.memo-pad-textarea')?.focus();
      return;
    }

    const message = document.createElement('section');
    message.className = 'memo-pad-message';
    message.setAttribute('aria-label', '메모장');
    message.innerHTML = `
      <div id="gaemiMemoPadCard" class="memo-pad-card">
        <div class="memo-pad-head">
          <div>
            <h2 class="memo-pad-title">메모장</h2>
            <p class="memo-pad-subtitle">채팅하다 떠오른 내용을 바로 적어두세요.</p>
          </div>
          <span class="memo-pad-status" aria-live="polite"></span>
        </div>
        <textarea class="memo-pad-textarea" aria-label="메모 내용" placeholder="메모를 입력하세요"></textarea>
        <div class="memo-pad-actions">
          <button type="button" class="memo-pad-button memo-pad-button--quiet" data-memo-action="delete">삭제</button>
          <div class="memo-pad-actions__right">
            <button type="button" class="memo-pad-button memo-pad-button--quiet" data-memo-action="copy">복사</button>
            <button type="button" class="memo-pad-button memo-pad-button--primary" data-memo-action="save">저장</button>
          </div>
        </div>
      </div>
    `;

    const textarea = message.querySelector('.memo-pad-textarea');
    const status = message.querySelector('.memo-pad-status');

    const setStatus = (text) => {
      status.textContent = text;
      if (!text) return;
      window.clearTimeout(setStatus.timer);
      setStatus.timer = window.setTimeout(() => {
        status.textContent = '';
      }, 1600);
    };

    const resize = () => {
      textarea.style.height = 'auto';
      const next = Math.min(Math.max(textarea.scrollHeight, 160), 420);
      textarea.style.height = `${next}px`;
    };

    textarea.value = readSavedMemo();
    textarea.addEventListener('input', () => {
      resize();
      status.textContent = textarea.value === readSavedMemo() ? '' : '저장 안 됨';
    });

    message.addEventListener('click', async (event) => {
      const button = event.target.closest('[data-memo-action]');
      if (!button) return;

      const action = button.dataset.memoAction;
      if (action === 'save') {
        setStatus(saveMemo(textarea.value) ? '저장됨' : '저장 실패');
        return;
      }

      if (action === 'copy') {
        if (!textarea.value) {
          setStatus('내용 없음');
          return;
        }
        setStatus(await copyText(textarea.value) ? '복사됨' : '복사 실패');
        return;
      }

      if (action === 'delete') {
        textarea.value = '';
        saveMemo('');
        resize();
        setStatus('삭제됨');
        textarea.focus();
      }
    });

    chatArea.appendChild(message);
    resize();
    message.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    requestAnimationFrame(() => textarea.focus());
  };

  openButton.addEventListener('click', () => {
    window.GaemiGTPChatTools?.closeMenu();
    createMemoPad();
  });

  window.openMemoPadInChat = createMemoPad;
})();
