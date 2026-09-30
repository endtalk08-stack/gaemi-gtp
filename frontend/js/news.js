// gaemiGTP - 뉴스 표시 전용
// 기존 app.js의 관련 기사 표시 동작을 그대로 분리한 함수입니다.
window.GaemiGTPNews = window.GaemiGTPNews || {};

window.GaemiGTPNews.renderArticles = function ({
  evidence,
  block,
  responseMessageClass,
  openExternalLinkModal
}) {
            const articles = evidence.articles.slice(0, 3);
            if (articles.length) {
              const articleSection = document.createElement('section');
              articleSection.className = 'space-y-2';
              articleSection.appendChild(Object.assign(document.createElement('p'), { className: responseMessageClass, textContent: '관련 기사도 찾아봤어 👇' }));
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
};
