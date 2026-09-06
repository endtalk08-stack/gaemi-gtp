// 개미 투표 위 G마크 헤더가 장착된 하단 위젯 렌더러
    function renderBottomWidgets(wrapperId, stockName) {
      const container = document.getElementById(wrapperId);
      const bottomDiv = document.createElement('div');
      bottomDiv.className = "space-y-6 pt-4 animate-fade";
      bottomDiv.innerHTML = `
        <!-- 개미 투표 섹션 -->
        <div class="space-y-3">
          <!-- G마크 헤더 (요청하신 대박 아이디어 1안 적용) -->
          <div class="flex items-center gap-2.5 pb-1">
            <div class="w-7 h-7 rounded-full bg-[#0f172a] dark:bg-white text-white dark:text-black flex items-center justify-center font-black text-xs shadow-sm shrink-0">G</div>
            <h3 class="font-black text-base sm:text-lg text-[#0f172a] dark:text-white">개미들아, 내일 어떻게 될 거 같아? 실력 발휘해 봐!</h3>
          </div>

          <!-- 투표 박스 본체 -->
          <div class="bg-white dark:bg-[#1e1f24] border border-[#cbd5e1] dark:border-[#282a30] rounded-3xl p-5 space-y-4 shadow-sm">
            <div class="flex items-center justify-between">
              <span class="font-black text-base text-[#0f172a] dark:text-white">개미 투표</span>
              <span class="text-xs text-[#64748b] dark:text-[#a1a1aa] font-bold">내일 주가 전망</span>
            </div>
            <div class="space-y-2">
              <div class="flex items-center justify-between text-xs font-black">
                <span id="voteUpLabel" class="text-emerald-500 dark:text-emerald-400">상승 68%</span>
                <span id="voteDownLabel" class="text-sky-500 dark:text-sky-400">하락 32%</span>
              </div>
              <div class="w-full h-2 bg-sky-400 rounded-full overflow-hidden flex">
                <div id="voteProgressBar" class="h-full bg-emerald-500 dark:bg-emerald-400 rounded-full transition-all duration-500" style="width: 68%;"></div>
              </div>
            </div>
            <div class="grid grid-cols-2 gap-3">
              <button type="button" onclick="castVote('up')" id="btnVoteUp" class="py-3 rounded-xl border border-emerald-500/40 bg-emerald-50 dark:bg-emerald-950/20 text-emerald-600 dark:text-emerald-400 font-black text-sm">상승 전망</button>
              <button type="button" onclick="castVote('down')" id="btnVoteDown" class="py-3 rounded-xl border border-[#cbd5e1] dark:border-[#282a30] bg-[#f8fafc] dark:bg-[#18191d] text-[#64748b] dark:text-[#a1a1aa] font-black text-sm">하락 전망</button>
            </div>
          </div>
        </div>

        <!-- 전략 3인방 아코디언 -->
        <div class="space-y-3">
          <div class="flex items-center gap-2.5 pb-1">
            <div class="w-7 h-7 rounded-full bg-[#0f172a] dark:bg-white text-white dark:text-black flex items-center justify-center font-black text-xs shadow-sm shrink-0">G</div>
            <h3 class="font-black text-base sm:text-lg text-[#0f172a] dark:text-white">내 투자 스타일에 맞는 전략도 확인해바.</h3>
          </div>

          <!-- 서학개미 -->
          <div class="space-y-2">
            <button type="button" onclick="toggleStrategyDashboard('서학', this)" id="card-btn-서학" class="w-full text-left p-4 sm:p-5 rounded-2xl bg-white dark:bg-[#1e1f24] border border-[#cbd5e1] dark:border-[#27272a] hover:border-[#94a3b8] dark:hover:border-[#52525b] transition cursor-pointer shadow-sm">
              <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div class="space-y-1">
                  <div class="flex items-center gap-2">
                    <span class="text-sm font-bold text-[#64748b] dark:text-[#a1a1aa]">US</span>
                    <span class="font-black text-lg text-[#0f172a] dark:text-white">서학개미 (장기)</span>
                  </div>
                  <p class="text-base text-[#64748b] dark:text-[#a1a1aa]">미국 빅테크 메가트렌드 진입 후 분할익절과 잔여물량으로 추종.</p>
                </div>
                <div class="flex items-center gap-5 sm:text-right shrink-0 pt-2 sm:pt-0 border-t sm:border-t-0 border-[#e2e8f0] dark:border-[#27272a]">
                  <div><div class="text-[13px] text-[#94a3b8] dark:text-[#71717a] font-bold">10년 누적 성과</div><div class="text-lg font-black text-[#0f172a] dark:text-white">+2,335%</div></div>
                  <div><div class="text-[13px] text-[#94a3b8] dark:text-[#71717a] font-bold">1억 → 최종 자산</div><div class="text-lg font-black text-[#0f172a] dark:text-white">24.5억</div></div>
                </div>
              </div>
            </button>
            <div id="dash-slot-서학" class="hidden animate-fade"></div>
          </div>

          <!-- 국장개미 -->
          <div class="space-y-2">
            <button type="button" onclick="toggleStrategyDashboard('국장', this)" id="card-btn-국장" class="w-full text-left p-4 sm:p-5 rounded-2xl bg-white dark:bg-[#1e1f24] border border-[#cbd5e1] dark:border-[#27272a] hover:border-[#94a3b8] dark:hover:border-[#52525b] transition cursor-pointer shadow-sm">
              <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div class="space-y-1">
                  <div class="flex items-center gap-2">
                    <span class="text-sm font-bold text-[#64748b] dark:text-[#a1a1aa]">KR</span>
                    <span class="font-black text-lg text-[#0f172a] dark:text-white">국장개미 (스윙)</span>
                  </div>
                  <p class="text-base text-[#64748b] dark:text-[#a1a1aa]">코스피 시총 상위주 20일선 지지 반등 및 외국인 순매수 턴어라운드 노림수.</p>
                </div>
                <div class="flex items-center gap-5 sm:text-right shrink-0 pt-2 sm:pt-0 border-t sm:border-t-0 border-[#e2e8f0] dark:border-[#27272a]">
                  <div><div class="text-[13px] text-[#94a3b8] dark:text-[#71717a] font-bold">10년 누적 성과</div><div class="text-lg font-black text-[#0f172a] dark:text-white">+2,335%</div></div>
                  <div><div class="text-[13px] text-[#94a3b8] dark:text-[#71717a] font-bold">1억 → 최종 자산</div><div class="text-lg font-black text-[#0f172a] dark:text-white">24.5억</div></div>
                </div>
              </div>
            </button>
            <div id="dash-slot-국장" class="hidden animate-fade"></div>
          </div>

          <!-- 트레이더 -->
          <div class="space-y-2">
            <button type="button" onclick="toggleStrategyDashboard('트레이더', this)" id="card-btn-트레이더" class="w-full text-left p-4 sm:p-5 rounded-2xl bg-white dark:bg-[#1e1f24] border border-[#cbd5e1] dark:border-[#27272a] hover:border-[#94a3b8] dark:hover:border-[#52525b] transition cursor-pointer shadow-sm">
              <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div class="space-y-1">
                  <div class="flex items-center gap-2">
                    <span class="text-amber-400 text-lg">⚡</span>
                    <span class="font-black text-lg text-[#0f172a] dark:text-white">트레이더 (단기)</span>
                  </div>
                  <p class="text-base text-[#64748b] dark:text-[#a1a1aa]">15시 15분 당일 거래대금 양봉 매수 후 익일 개장 초반 시가 갭 분할 청산.</p>
                </div>
                <div class="flex items-center gap-5 sm:text-right shrink-0 pt-2 sm:pt-0 border-t sm:border-t-0 border-[#e2e8f0] dark:border-[#27272a]">
                  <div><div class="text-[13px] text-[#94a3b8] dark:text-[#71717a] font-bold">10년 누적 성과</div><div class="text-lg font-black text-[#0f172a] dark:text-white">+2,335%</div></div>
                  <div><div class="text-[13px] text-[#94a3b8] dark:text-[#71717a] font-bold">1억 → 최종 자산</div><div class="text-lg font-black text-[#0f172a] dark:text-white">32.4억</div></div>
                </div>
              </div>
            </button>
            <div id="dash-slot-트레이더" class="hidden animate-fade"></div>
          </div>
        </div>

        <div class="pt-2 pb-4 flex justify-center">
          <button type="button" onclick="openMeme('${stockName}')" class="px-6 py-3 rounded-xl bg-[#f1f5f9] dark:bg-[#1e1f24] border border-[#cbd5e1] dark:border-[#3f3f46] text-[#0f172a] dark:text-white font-bold text-sm flex items-center gap-2 shadow-sm cursor-pointer">
            <span>📸</span> <span>카카오톡 공유용 짤 카드 만들기</span>
          </button>
        </div>
      `;
      container.appendChild(bottomDiv);
    }
