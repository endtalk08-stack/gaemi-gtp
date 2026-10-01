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
            if (articles.length < 3) {
              sourceArticles.forEach((item) => {
                if (articles.length >= 3 || usedArticles.has(item)) return;
                const signals = articleSignals(item);
                if (selectedSignals.some((signal) => signals.includes(signal.normalizedLabel))) {
                  articles.push(item);
                  usedArticles.add(item);
                }
              });
            }

            if (articles.length) {
              const articleSection = document.createElement('section');
              articleSection.className = 'space-y-2 [&>p]:m-0 [&>button]:m-0';
              articleSection.appendChild(Object.assign(document.createElement('p'), { className: responseMessageClass, textContent: '관련 기사를 찾아봤어 👇' }));
              block.appendChild(articleSection);

              // 중앙에는 핵심 기사만 간단히 보여주고, 전체 출처는 오른쪽 패널에서 확인한다.
              articles.forEach((item, index) => {
                const row = document.createElement('button');
                row.type = 'button';
                row.className = 'block w-full translate-y-1 text-left opacity-0 text-[#475569] transition duration-300 hover:text-[#0f172a] dark:text-[#d4d4d8] dark:hover:text-white';
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
              sourceChip.setAttribute('aria-label', `출처 ${sourceItems.length}개 보기`);
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
              label.textContent = `출처 ${sourceItems.length}개`;
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
