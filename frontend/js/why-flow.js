// gaemiGTP - '왜 움직였나?' 흐름 전용
window.GaemiGTPWhyFlow = window.GaemiGTPWhyFlow || {};

window.GaemiGTPWhyFlow.appendWhy = async function ({
  mainContainer,
  requestId,
  getActiveAnalysisRequestId,
  result,
  choices,
  whyState,
  makeUserPrompt,
  getWhyEvidence,
  appendFollowupChoices,
  responseMessageClass,
  stockName
}) {
  
            if (mainContainer.querySelector('[data-why-flow]')) return;
            const prompt = makeUserPrompt(whyState.label, 'whyFlow');
            choices.insertAdjacentElement('afterend', prompt);
            choices.remove();
  
            const loading = document.createElement('div');
            loading.className = 'mt-5 space-y-2';
            prompt.insertAdjacentElement('afterend', loading);
            const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
            for (const message of ['뉴스와 공시를 확인합니다', '생각중', '내용을 정리중입니다']) {
              if (requestId !== getActiveAnalysisRequestId() || !mainContainer.isConnected) return;
              const line = document.createElement('p');
              line.className = `${responseMessageClass} animate-pulse`;
              line.textContent = message;
              loading.appendChild(line);
              await wait(4000);
            }
            if (requestId !== getActiveAnalysisRequestId() || !mainContainer.isConnected) return;
            loading.remove();
  
            const evidence = getWhyEvidence();
            const disclosures = (Array.isArray(result.disclosures) && result.disclosures.length
              ? result.disclosures
              : (Array.isArray(result.us_filings) ? result.us_filings : [])).slice(0, 3);
            const block = document.createElement('section');
            block.className = 'mt-5 space-y-5 animate-fade';
            const signalTitle = document.createElement('p');
            signalTitle.className = responseMessageClass;
            signalTitle.textContent = evidence.signals.length || disclosures.length ? '오늘 눈에 띄는 흐름 👀' : '오늘은 흐름 없음 ☁️';
            const signalList = document.createElement('div');
            signalList.className = 'flex flex-wrap gap-x-3 gap-y-2 font-semibold';
            evidence.signals.forEach((signal) => {
              const tag = document.createElement('span');
              tag.textContent = signal.label;
              tag.style.color = signal.tone === 'positive' ? '#FF8DA1' : signal.tone === 'negative' ? '#38BDF8' : '#94A3B8';
              signalList.appendChild(tag);
            });
            block.appendChild(signalTitle);
            if (evidence.signals.length) block.appendChild(signalList);
  
            const articles = window.GaemiGTPNews.renderArticles({
              evidence,
              block,
              responseMessageClass,
              openExternalLinkModal: window.GaemiGTPExternalLinkModal.openExternalLinkModal
            });
  
            window.GaemiGTPDisclosures.renderDisclosures({
              disclosures,
              articles,
              block,
              responseMessageClass,
              openExternalLinkModal: window.GaemiGTPExternalLinkModal.openExternalLinkModal
            });
  
            if (!articles.length && !disclosures.length) {
              const empty = document.createElement('p');
              empty.className = `${responseMessageClass} whitespace-pre-line`;
              empty.textContent = '기사에서 딱히 잡히는 재료도 없고,\n오늘은 시장 흐름을 조금 더 지켜보자 ☕';
              block.appendChild(empty);
            }
  
            window.GaemiGTPRelatedStocks.renderRelatedStocks({
              articles,
              stockName,
              block,
              responseMessageClass
            });
  
            prompt.insertAdjacentElement('afterend', block);
            const actions = window.GaemiGTPFirstReplyActions.appendFirstReplyActions(block, `${prompt.innerText}\n${block.innerText}`, 'why', stockName);
            const followups = appendFollowupChoices(actions || block);
            followups.addEventListener('click', async (event) => {
              const button = event.target.closest('[data-why-followup]');
              if (!button) return;
            });
            if (window.lucide) window.lucide.createIcons();
            block.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
};
