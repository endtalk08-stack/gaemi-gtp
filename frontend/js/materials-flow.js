// gaemiGTP - '재료는 있어?' 흐름 전용
window.GaemiGTPMaterialsFlow = window.GaemiGTPMaterialsFlow || {};

window.GaemiGTPMaterialsFlow.appendMaterials = async function ({
  mainContainer,
  requestId,
  getActiveAnalysisRequestId,
  result,
  choices,
  makeUserPrompt,
  responseMessageClass,
  stockName
}) {
  
            if (mainContainer.querySelector('[data-materials-flow]')) return;
  
            const prompt = makeUserPrompt('재료는 있어?', 'materialsFlow');
            choices.insertAdjacentElement('afterend', prompt);
            choices.remove();
  
            const loading = document.createElement('div');
            loading.className = 'mt-5 space-y-2';
            prompt.insertAdjacentElement('afterend', loading);
  
            const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
            // 첫 답변과 같은 글자 크기/타이핑 연출을 사용한다.
            // 점 6개 로더는 사용하지 않고, 문장 자체가 순서대로 나타난다.
            for (const message of ['뉴스와 공시를 확인합니다', '생각중', '내용을 정리중입니다']) {
              if (requestId !== getActiveAnalysisRequestId() || !mainContainer.isConnected) return;
              const line = document.createElement('p');
              line.className = `${responseMessageClass} typing-cursor animate-fade`;
              loading.appendChild(line);

              let charIdx = 0;
              while (charIdx < message.length) {
                if (requestId !== getActiveAnalysisRequestId() || !mainContainer.isConnected) return;
                line.textContent += message.charAt(charIdx++);
                await wait(35);
              }
              line.classList.remove('typing-cursor');
              await wait(500);
            }
  
            if (requestId !== getActiveAnalysisRequestId() || !mainContainer.isConnected) return;
            loading.remove();
  
            const materials = window.GaemiGTPSourceLists.renderSourceLists(result, { includeHeader: false });
            if (!materials) return;
            materials.dataset.materialsSection = 'true';
            prompt.insertAdjacentElement('afterend', materials);
  
            const materialLines = Array.from(materials.querySelectorAll('.source-list-group-title, .source-list-row'));
            materialLines.forEach((line) => {
              line.style.opacity = '0';
              line.style.transform = 'translateY(6px)';
              line.style.transition = 'opacity 360ms ease, transform 360ms ease';
            });
  
            for (const line of materialLines) {
              if (requestId !== getActiveAnalysisRequestId() || !mainContainer.isConnected) return;
              line.style.opacity = '1';
              line.style.transform = 'translateY(0)';
              await wait(550);
            }
  
            const hashtags = document.createElement('p');
            hashtags.className = 'mt-5 text-sm font-semibold leading-7 text-[#db2777] dark:text-[#e889aa] animate-fade';
            hashtags.textContent = '#HBM #반도체슈퍼사이클 #증권사컨센서스 #주식호재 #경제뉴스 #스마트투자';
            materials.insertAdjacentElement('afterend', hashtags);
  
            const materialText = `${materials.innerText}\n${hashtags.innerText}`;
            window.GaemiGTPFirstReplyActions.appendFirstReplyActions(hashtags, materialText, 'materials', stockName);
            materials.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
};
