// gaemiGTP - 분석 상태 표시 전용
    window.GaemiGTPAnalysisStatus = window.GaemiGTPAnalysisStatus || {};

window.GaemiGTPAnalysisStatus.renderAnalysisStatus = function(chatArea, stockName, ok) {
      const state = document.createElement('div');
      state.className = 'analysis-state animate-fade';
      state.innerHTML = ok ? `
        <div class="w-10 h-10 mx-auto mb-3 rounded-full bg-[#f1f5f9] dark:bg-[#27272a] flex items-center justify-center text-[#64748b] dark:text-[#a1a1aa]">
          <i data-lucide="database" class="w-5 h-5"></i>
        </div>
        <div class="font-black text-base text-[#0f172a] dark:text-white">분석 데이터가 없습니다</div>
        <div class="mt-1 text-xs text-[#64748b] dark:text-[#a1a1aa]">${stockName}에 대한 분석 내용을 준비하고 있습니다.</div>
      ` : `
        <div class="w-10 h-10 mx-auto mb-3 rounded-full bg-[#f1f5f9] dark:bg-[#27272a] flex items-center justify-center text-[#64748b] dark:text-[#a1a1aa]">
          <i data-lucide="refresh-cw" class="w-5 h-5"></i>
        </div>
        <div class="font-black text-base text-[#0f172a] dark:text-white">분석 데이터를 불러오지 못했습니다</div>
        <div class="mt-1 text-xs text-[#64748b] dark:text-[#a1a1aa]">잠시 후 다시 시도해주세요.</div>
      `;
      chatArea.appendChild(state);
      if (window.lucide) lucide.createIcons();
      return state;
    };
