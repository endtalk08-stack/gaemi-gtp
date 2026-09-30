// gaemiGTP - 뉴스·공시 출처 패널 전용
    window.GaemiGTPSourceLists = window.GaemiGTPSourceLists || {};

window.GaemiGTPSourceLists.renderSourceLists = function(result, { includeHeader = true } = {}) {
      if (!result) return null;

      const newsItems = Array.isArray(result.news_items) ? result.news_items : [];
      const disclosureItems = Array.isArray(result.disclosures) ? result.disclosures : [];
      const usFilingItems = Array.isArray(result.us_filings) ? result.us_filings : [];
      const sourceDisclosureItems = disclosureItems.length ? disclosureItems : usFilingItems;
      const sourceCount = newsItems.length + sourceDisclosureItems.length;
      if (!sourceCount) return null;

      // 기존 '출처' 접기/펼치기 UI 대신 본문과 동일한 G 섹션으로 항상 노출한다.
      const wrap = document.createElement('div');
      wrap.className = 'source-toggle-wrap animate-fade';

      const header = document.createElement('div');
      header.className = 'flex items-center gap-2.5';
      header.innerHTML = `
        <div class="w-7 h-7 sm:w-8 sm:h-8 rounded-full bg-[#0f172a] dark:bg-white text-white dark:text-black flex items-center justify-center font-black text-xs sm:text-sm shadow-sm shrink-0">G</div>
        <h4 class="font-black text-lg sm:text-xl text-[#0f172a] dark:text-white">재료는 있어?</h4>
      `;
      if (includeHeader) wrap.appendChild(header);

      const panel = document.createElement('div');
      panel.className = 'source-list-panel is-open';
      panel.setAttribute('aria-hidden', 'false');

      const makeGroup = (label, items) => {
        if (!items.length) return null;
        const group = document.createElement('div');
        group.className = 'source-list-group';

        const heading = document.createElement('div');
        heading.className = 'source-list-group-title';
        heading.textContent = label;
        group.appendChild(heading);

        const card = document.createElement('div');
        card.className = 'source-list-card';

        items.slice(0, 3).forEach(item => {
          const link = document.createElement('a');
          link.className = 'source-list-row';
          const href = item.original_link || item.link || item.url || item.article_url || '';
          if (href) {
            link.href = '#';
            link.setAttribute('role', 'button');
            link.addEventListener('click', (event) => {
              event.preventDefault();
              window.GaemiGTPExternalLinkModal.openExternalLinkModal(item);
            });
          } else {
            link.removeAttribute('href');
            link.setAttribute('aria-disabled', 'true');
          }

          const isInsider = label === '공시' && (
            String(item.form || '').toUpperCase() === '4' ||
            !!item.person ||
            !!item.transaction_kind ||
            !!item.transaction_summary ||
            Object.prototype.hasOwnProperty.call(item, 'transaction_count')
          );
          const main = document.createElement('div');
          main.className = 'source-list-main';
          const titleEl = document.createElement('div');
          titleEl.className = 'source-list-title';

          if (isInsider) {
            const kind = item.transaction_kind || '';
            const summaryText = item.transaction_summary || '';
            const count = Number(item.transaction_count || 0);
            let summary = summaryText || kind || '내부자 거래';
            if (count > 0 && !/\d+건/.test(summary) && !summary.includes(' · ')) {
              summary = `${summary} · ${count}건`;
            }
            titleEl.textContent = summary;
            titleEl.style.color = /매도/.test(summary) ? '#FF8DA1' : (/매수|취득/.test(summary) ? '#38BDF8' : '');

            main.appendChild(titleEl);

            const keywords = Array.isArray(item.keywords) ? item.keywords.filter(Boolean) : [];
            if (keywords.length) {
              const keywordEl = document.createElement('div');
              keywordEl.className = 'mt-2 text-sm font-semibold leading-6 text-[#db2777] dark:text-[#e889aa]';
              keywordEl.textContent = keywords.map(keyword => `#${String(keyword).replace(/^#/, '')}`).join(' ');
              main.appendChild(keywordEl);
            }

            const linkEl = document.createElement('div');
            linkEl.className = 'mt-2 text-xs font-medium text-[#64748b] dark:text-[#a1a1aa]';
            linkEl.textContent = '공시 원문 보기';
            main.appendChild(linkEl);
          } else {
            titleEl.textContent = item.title || item.description || '제목 확인 필요';
            main.appendChild(titleEl);

            if (label === '공시') {
              const keywords = Array.isArray(item.keywords) ? item.keywords.filter(Boolean) : [];
              if (keywords.length) {
                const keywordEl = document.createElement('div');
                keywordEl.className = 'mt-2 text-sm font-semibold leading-6 text-[#db2777] dark:text-[#e889aa]';
                keywordEl.textContent = keywords.map(keyword => `#${String(keyword).replace(/^#/, '')}`).join(' ');
                main.appendChild(keywordEl);
              }

              const linkEl = document.createElement('div');
              linkEl.className = 'mt-2 text-xs font-medium text-[#64748b] dark:text-[#a1a1aa]';
              linkEl.textContent = '공시 원문 보기';
              main.appendChild(linkEl);
            }
          }

          const arrow = document.createElement('i');
          arrow.setAttribute('data-lucide', 'chevron-right');
          arrow.className = 'source-list-arrow w-5 h-5';
          link.appendChild(main);
          link.appendChild(arrow);
          card.appendChild(link);
        });

        group.appendChild(card);
        return group;
      };

      const newsGroup = makeGroup('뉴스', newsItems);
      const disclosureGroup = makeGroup('공시', sourceDisclosureItems);
      if (newsGroup) panel.appendChild(newsGroup);
      if (disclosureGroup) panel.appendChild(disclosureGroup);
      wrap.appendChild(panel);

      if (window.lucide) window.lucide.createIcons();
      return wrap;
    };
