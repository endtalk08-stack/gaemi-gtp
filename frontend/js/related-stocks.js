// gaemiGTP - 관련 종목 표시 전용
window.GaemiGTPRelatedStocks = window.GaemiGTPRelatedStocks || {};

window.GaemiGTPRelatedStocks.renderRelatedStocks = function ({
  articles,
  stockName,
  block,
  responseMessageClass
}) {
            const relatedStocks = [...new Set(articles.flatMap((item) => Array.isArray(item.related_stocks) ? item.related_stocks : []))]
              .filter((name) => name && name !== stockName)
              .slice(0, 3);
            if (relatedStocks.length) {
              const relatedSection = document.createElement('section');
              relatedSection.className = 'space-y-2';
              relatedSection.appendChild(Object.assign(document.createElement('p'), { className: responseMessageClass, textContent: '관련 종목' }));
              relatedStocks.forEach((name) => {
                const row = document.createElement('div');
                row.className = 'flex items-center gap-2 text-sm';
                const stock = document.createElement('span');
                stock.className = 'min-w-0 flex-1 font-semibold text-[#475569] dark:text-[#d4d4d8]';
                stock.textContent = name;
                const relation = document.createElement('span');
                relation.className = 'text-xs text-[#94a3b8] dark:text-[#71717a]';
                relation.textContent = '뉴스 공동 언급';
                row.append(stock, relation);
                relatedSection.appendChild(row);
              });
              block.appendChild(relatedSection);
            }
};
