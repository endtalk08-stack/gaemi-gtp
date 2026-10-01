// gaemiGTP - 뉴스 표시 전용
// 기존 app.js의 관련 기사 표시 동작을 그대로 분리한 함수입니다.
window.GaemiGTPNews = window.GaemiGTPNews || {};

window.GaemiGTPNews.renderArticles = function ({
  evidence,
  block,
  responseMessageClass,
  openExternalLinkModal
}) {
            const normalizeSignalLabel = (value) => String(value || '').replace(/^#/, '').replace(/\s+/g, '');
            const selectedSignals = (Array.isArray(evidence.signals) ? evidence.signals : [])
              .map((signal) => ({ ...signal, normalizedLabel: normalizeSignalLabel(signal?.label) }))
              .filter((signal) => signal.normalizedLabel);
            const sourceArticles = Array.isArray(evidence.articles) ? evidence.articles : [];
            const matchedArticles = Array.isArray(evidence.matchedArticles) ? evidence.matchedArticles : sourceArticles;
            const articleSignals = (item) => (Array.isArray(item.movement_signals) ? item.movement_signals : [])
              .map((signal) => normalizeSignalLabel(signal?.label))
              .filter(Boolean);

            // 백엔드는 관련도 점수순으로 news_items를 정렬한다.
            // 중앙에는 상위 1~3개만 보여주고, 전체 목록은 아래 더보기에서 유지한다.
            const articles = matchedArticles.slice(0, 3);
            
            if (articles.length) {
              const articleSection = document.createElement('section');
              articleSection.className = 'space-y-2 [&>p]:m-0 [&>button]:m-0';
              articleSection.appendChild(Object.assign(document.createElement('p'), { className: responseMessageClass, textContent: '관련 기사를 찾아봤어 👇' }));
              block.appendChild(articleSection);

              // 중앙에는 핵심 기사만 간단히 보여주고, 전체 출처는 오른쪽 패널에서 확인한다.
              articles.forEach((item, index) => {
                const row = document.createElement('button');
                row.type = 'button';
                row.className = 'block w-full translate-y-1 text-left text-xs leading-5 sm:text-base sm:leading-7 opacity-0 text-[#475569] transition duration-300 hover:text-[#0f172a] dark:text-[#d4d4d8] dark:hover:text-white line-clamp-1';
                row.classList.add(...String(responseMessageClass || '').split(/\s+/).filter(Boolean));
                row.textContent = item.title || '제목 확인 필요';
                row.addEventListener('click', () => openExternalLinkModal(item));
                articleSection.appendChild(row);
                setTimeout(() => {
                  row.classList.remove('translate-y-1', 'opacity-0');
                }, 180 * (index + 1));
              });

              const sourceItems = sourceArticles.slice(0, 20);
              const sourceChip = document.createElement('button');
              sourceChip.type = 'button';
              sourceChip.className = 'news-source-chip';
              sourceChip.setAttribute('aria-label', '더보기');
              const badges = document.createElement('span');
              badges.className = 'news-source-chip__badges';
              sourceItems.slice(0, 3).forEach((item) => {
                const badge = document.createElement('span');
                badge.className = 'news-source-chip__badge';
                const source = String(item.source || '뉴스').trim();
                badge.textContent = source.slice(0, 2);
                badge.title = source;
                badges.appendChild(badge);
              });
              sourceChip.appendChild(badges);
              const label = document.createElement('span');
              label.className = 'news-source-chip__label';
              label.textContent = '더보기';
              sourceChip.appendChild(label);
              sourceChip.addEventListener('click', () => {
                if (window.GaemiGTPRightPanelTabs?.showRelatedNews) {
                  window.GaemiGTPRightPanelTabs.showRelatedNews(sourceItems);
                }
              });
              articleSection.appendChild(sourceChip);
            }
            return articles;
};
