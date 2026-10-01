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
            const articleSignals = (item) => (Array.isArray(item.movement_signals) ? item.movement_signals : [])
              .map((signal) => normalizeSignalLabel(signal?.label))
              .filter(Boolean);

            // 위에 보여 준 키워드마다 그 키워드를 실제로 만든 기사를 먼저 한 개씩 고른다.
            // 같은 기사가 여러 키워드의 근거면 중복해서 보여 주지 않는다.
            const articles = [];
            const usedArticles = new Set();
            selectedSignals.forEach((signal) => {
              const matched = sourceArticles.find((item) => {
                if (usedArticles.has(item)) return false;
                return articleSignals(item).includes(signal.normalizedLabel);
              });
              if (matched) {
                articles.push(matched);
                usedArticles.add(matched);
              }
            });

            // 자리가 남으면 선택된 키워드 중 하나라도 실제로 들어 있는 기사만 추가한다.
            if (articles.length < 10) {
              sourceArticles.forEach((item) => {
                if (articles.length >= 10 || usedArticles.has(item)) return;
                const signals = articleSignals(item);
                if (selectedSignals.some((signal) => signals.includes(signal.normalizedLabel))) {
                  articles.push(item);
                  usedArticles.add(item);
                }
              });
            }

            if (articles.length) {
              const articleSection = document.createElement('section');
              articleSection.className = 'space-y-2';
              const articleTrigger = document.createElement('button');
              articleTrigger.type = 'button';
              articleTrigger.className = 'inline-flex items-center rounded-lg border border-transparent px-2 py-1 text-left transition-colors hover:border-[#475569] hover:bg-[#f8fafc] dark:hover:border-[#71717a] dark:hover:bg-white/5 cursor-pointer';
              articleTrigger.appendChild(Object.assign(document.createElement('span'), { className: responseMessageClass, textContent: '관련 기사를 찾아봤어 👉' }));
              articleTrigger.addEventListener('click', () => {
                if (window.GaemiGTPRightPanelTabs?.showRelatedNews) {
                  document.body.classList.add('right-panel-open');
                  window.applySidebarState?.();
                  window.GaemiGTPRightPanelTabs.showRelatedNews(articles);
                }
              });
              articleSection.appendChild(articleTrigger);
              block.appendChild(articleSection);
              articles.forEach((item, index) => {
                const row = document.createElement('button');
                row.type = 'button';
                row.className = 'block w-full translate-y-1 text-left text-sm opacity-0 text-[#475569] transition duration-300 hover:text-[#0f172a] dark:text-[#d4d4d8] dark:hover:text-white';
                row.textContent = item.title || '제목 확인 필요';
                row.addEventListener('click', () => openExternalLinkModal(item));
                articleSection.appendChild(row);
                setTimeout(() => {
                  row.classList.remove('translate-y-1', 'opacity-0');
                }, 180 * (index + 1));
              });
            }
            return articles;
};
