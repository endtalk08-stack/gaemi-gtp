// gaemiGTP - 공시 표시 전용
window.GaemiGTPDisclosures = window.GaemiGTPDisclosures || {};

window.GaemiGTPDisclosures.renderDisclosures = function ({
  disclosures,
  articles,
  block,
  responseMessageClass,
  openExternalLinkModal
}) {
            if (disclosures.length) {
              const disclosureSection = document.createElement('section');
              disclosureSection.className = 'space-y-2';
              disclosureSection.appendChild(Object.assign(document.createElement('p'), { className: responseMessageClass, textContent: '관련 공시도 확인했어 📄' }));
              block.appendChild(disclosureSection);
              disclosures.forEach((item, index) => {
                const row = document.createElement('button');
                row.type = 'button';
                row.className = 'block w-full translate-y-1 text-left text-sm opacity-0 text-[#475569] transition duration-300 hover:text-[#0f172a] dark:text-[#d4d4d8] dark:hover:text-white';
                row.textContent = item.title || '공시 제목 확인 필요';
                row.addEventListener('click', () => openExternalLinkModal(item));
                disclosureSection.appendChild(row);
                setTimeout(() => {
                  row.classList.remove('translate-y-1', 'opacity-0');
                }, 180 * (articles.length + index + 1));
              });
            }
};