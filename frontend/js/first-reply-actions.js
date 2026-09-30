// gaemiGTP - 첫 답변 액션 전용
      window.GaemiGTPFirstReplyActions = window.GaemiGTPFirstReplyActions || {};

window.GaemiGTPFirstReplyActions.appendFirstReplyActions = function(anchor, replyText, actionGroup = 'first', stockName = '') {
        if (!anchor) return null;
        const existing = anchor.parentElement?.querySelector(`[data-reply-actions="${actionGroup}"]`);
        if (existing) return existing;

        const actions = document.createElement('div');
        actions.dataset.replyActions = actionGroup;
        actions.className = 'mt-3 flex items-center gap-1 text-[#64748b] dark:text-[#a1a1aa]';
        actions.innerHTML = `
          <button type="button" class="inline-flex h-8 w-8 items-center justify-center rounded-lg transition hover:bg-[#f1f5f9] hover:text-[#0f172a] dark:hover:bg-[#27272a] dark:hover:text-white" data-first-reply-action="copy" aria-label="답변 복사" title="복사"><i data-lucide="copy" class="h-4 w-4"></i></button>
          <button type="button" class="inline-flex h-8 w-8 items-center justify-center rounded-lg transition hover:bg-[#f1f5f9] hover:text-[#0f172a] dark:hover:bg-[#27272a] dark:hover:text-white" data-first-reply-action="share" aria-label="답변 공유" title="공유"><i data-lucide="share-2" class="h-4 w-4"></i></button>
          <button type="button" class="inline-flex h-8 w-8 items-center justify-center rounded-lg transition hover:bg-[#f1f5f9] hover:text-[#0f172a] dark:hover:bg-[#27272a] dark:hover:text-white" data-first-reply-action="read" aria-label="답변 소리 내어 읽기" title="소리 내어 읽기"><i data-lucide="volume-2" class="h-4 w-4"></i></button>
          <button type="button" class="inline-flex h-8 w-8 items-center justify-center rounded-lg transition hover:bg-[#f1f5f9] hover:text-[#0f172a] dark:hover:bg-[#27272a] dark:hover:text-white" data-first-reply-action="like" aria-label="좋아요" title="좋아요" aria-pressed="false"><i data-lucide="thumbs-up" class="h-4 w-4"></i></button>
          <button type="button" class="inline-flex h-8 w-8 items-center justify-center rounded-lg transition hover:bg-[#f1f5f9] hover:text-[#0f172a] dark:hover:bg-[#27272a] dark:hover:text-white" data-first-reply-action="dislike" aria-label="별로예요" title="별로예요" aria-pressed="false"><i data-lucide="thumbs-down" class="h-4 w-4"></i></button>`;

        const setTemporaryLabel = (button, label) => {
          const original = button.title;
          button.title = label;
          setTimeout(() => { button.title = original; }, 1200);
        };
        const copyReply = async () => {
          try {
            await navigator.clipboard.writeText(replyText);
            return true;
          } catch (_) {
            const textarea = document.createElement('textarea');
            textarea.value = replyText;
            document.body.appendChild(textarea);
            textarea.select();
            const copied = document.execCommand('copy');
            textarea.remove();
            return copied;
          }
        };

        actions.addEventListener('click', async (event) => {
          const button = event.target.closest('[data-first-reply-action]');
          if (!button) return;
          const action = button.dataset.firstReplyAction;

          if (action === 'copy') {
            if (await copyReply()) setTemporaryLabel(button, '복사됨');
            return;
          }
          if (action === 'share') {
            if (navigator.share) {
              try {
                await navigator.share({ title: `${stockName} 첫 답변`, text: replyText, url: window.location.href });
                return;
              } catch (_) { /* 공유 취소 시 복사로 대체하지 않는다. */ }
            }
            if (await copyReply()) setTemporaryLabel(button, '복사됨');
            return;
          }
          if (action === 'read') {
            if (!('speechSynthesis' in window)) return;
            if (window.speechSynthesis.speaking) {
              window.speechSynthesis.cancel();
              button.title = '소리 내어 읽기';
              return;
            }
            const utterance = new SpeechSynthesisUtterance(replyText);
            utterance.lang = 'ko-KR';
            utterance.rate = 1;
            utterance.onend = () => { button.title = '소리 내어 읽기'; };
            button.title = '읽는 중 · 다시 누르면 멈춤';
            window.speechSynthesis.speak(utterance);
            return;
          }

          const opposite = actions.querySelector(`[data-first-reply-action="${action === 'like' ? 'dislike' : 'like'}"]`);
          const selected = button.getAttribute('aria-pressed') !== 'true';
          button.setAttribute('aria-pressed', String(selected));
          opposite?.setAttribute('aria-pressed', 'false');
          button.classList.toggle('text-[#0f172a]', selected);
          button.classList.toggle('dark:text-white', selected);
          opposite?.classList.remove('text-[#0f172a]', 'dark:text-white');
        });

        anchor.insertAdjacentElement('afterend', actions);
        if (window.lucide) window.lucide.createIcons();
        return actions;
      };
