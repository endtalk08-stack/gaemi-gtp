// gaemiGTP - 외부 링크 모달 전용
    window.GaemiGTPExternalLinkModal = window.GaemiGTPExternalLinkModal || {};

window.GaemiGTPExternalLinkModal.openExternalLinkModal = function(item) {
      const modal = document.getElementById('externalLinkModal');
      if (!modal) return;
      const href = item.original_link || item.link || item.url || item.article_url || '';
      if (!href) return;

      const title = item.title || item.description || '제목 확인 필요';
      const source = item.source || (item.form ? 'SEC' : '출처 확인 필요');
      const when = item.display_datetime || item.datetime || item.date || item.pub_date || '';
      const time = item.time || item.acceptance_time || '';
      const tz = item.time_zone || '';
      const meta = `${source}${when ? ` · ${when}` : ''}${time ? ` · ${time}${tz ? ` ${tz}` : ''}` : ''}`;

      document.getElementById('externalLinkArticleTitle').textContent = title;
      document.getElementById('externalLinkArticleMeta').textContent = meta;
      document.getElementById('externalLinkUrl').textContent = href;
      modal.dataset.href = href;
      modal.classList.add('is-open');
      modal.setAttribute('aria-hidden', 'false');
      document.body.style.overflow = 'hidden';
      if (window.lucide) window.lucide.createIcons();
    };

    window.GaemiGTPExternalLinkModal.closeExternalLinkModal = function() {
      const modal = document.getElementById('externalLinkModal');
      if (!modal) return;
      modal.classList.remove('is-open');
      modal.setAttribute('aria-hidden', 'true');
      modal.dataset.href = '';
      document.body.style.overflow = '';
    };

    window.GaemiGTPExternalLinkModal.initExternalLinkModal = function() {
      const modal = document.getElementById('externalLinkModal');
      const close = document.getElementById('externalLinkClose');
      const copy = document.getElementById('externalLinkCopy');
      const open = document.getElementById('externalLinkOpen');
      if (!modal) return;
      close?.addEventListener('click', closeExternalLinkModal);
      modal.addEventListener('click', (e) => {
        if (e.target === modal) closeExternalLinkModal();
      });
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal.classList.contains('is-open')) closeExternalLinkModal();
      });
      copy?.addEventListener('click', async () => {
        const href = modal.dataset.href || '';
        if (!href) return;
        try {
          await navigator.clipboard.writeText(href);
          copy.textContent = '복사됨';
          setTimeout(() => copy.textContent = '링크 복사', 1200);
        } catch (_) {
          const ta = document.createElement('textarea');
          ta.value = href; document.body.appendChild(ta); ta.select();
          document.execCommand('copy'); ta.remove();
          copy.textContent = '복사됨';
          setTimeout(() => copy.textContent = '링크 복사', 1200);
        }
      });
      open?.addEventListener('click', () => {
        const href = modal.dataset.href || '';
        if (!href) return;
        window.open(href, '_blank', 'noopener,noreferrer');
      });
    };

    // ★ 버그 완벽 수정된 텍스트 파싱 로직
