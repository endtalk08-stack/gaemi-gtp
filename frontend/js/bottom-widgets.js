// gaemiGTP bottom widgets module
// 하단 개미 투표/투자전략 기능을 app.js에서 분리하기 위한 전용 파일.
// 기존 HTML onclick 호환을 위해 전역 함수 이름을 그대로 유지한다.

let currentChartInstance = null;

const strategyData = {
  '서학': {
    name: '서학개미 전략', icon: '🇺🇸', quote: '"데이터는 거짓말을 하지 않는다."',
    dateRange: '2016.08.28 ~ 2026.08.27', initial: '1억원', finalAsset: '24.5억',
    totalReturn: '+2,335%', cagr: '38.6%', mdd: '-24.8%', trades: '286회', winRate: '62.9%',
    accentColor: '#ff2d78', benchLabel: 'QQQ',
    chartData: [1.0, 1.8, 2.7, 4.5, 7.8, 11.2, 8.9, 14.5, 18.2, 21.4, 24.5],
    benchData: [1.0, 1.2, 1.5, 1.8, 2.4, 3.1, 2.3, 3.2, 3.8, 4.0, 4.2],
    labels: ['16', '17', '18', '19', '20', '21', '22', '23', '24', '25', '26']
  },
  '국장': {
    name: '국장개미 전략', icon: '🇰🇷', quote: '"박스권 국장에서도 외인 턴어라운드는 통한다."',
    dateRange: '2016.08.28 ~ 2026.08.27', initial: '1억원', finalAsset: '24.5억',
    totalReturn: '+2,335%', cagr: '38.6%', mdd: '-18.4%', trades: '412회', winRate: '68.2%',
    accentColor: '#00b8ff', benchLabel: 'KOSPI',
    chartData: [1.0, 2.1, 3.4, 5.8, 9.2, 13.5, 11.0, 16.8, 19.5, 22.1, 24.5],
    benchData: [1.0, 1.05, 1.2, 1.15, 1.4, 1.6, 1.3, 1.45, 1.5, 1.65, 1.8],
    labels: ['16', '17', '18', '19', '20', '21', '22', '23', '24', '25', '26']
  },
  '트레이더': {
    name: '트레이더 전략', icon: '⚡', quote: '"가장 강한 돈이 쏠린 자리에만 베팅한다."',
    dateRange: '2016.08.28 ~ 2026.08.27', initial: '1억원', finalAsset: '32.4억',
    totalReturn: '+3,140%', cagr: '42.1%', mdd: '-15.2%', trades: '1,240회', winRate: '74.5%',
    accentColor: '#eab308', benchLabel: '무위험',
    chartData: [1.0, 2.8, 4.9, 8.2, 13.5, 18.2, 16.8, 23.0, 26.5, 29.8, 32.4],
    benchData: [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0],
    labels: ['16', '17', '18', '19', '20', '21', '22', '23', '24', '25', '26']
  }
};

function toggleStrategyDashboard(type, btnElement) {
  const allTypes = ['서학', '국장', '트레이더'];
  const targetSlot = document.getElementById(`dash-slot-${type}`);
  const isAlreadyOpen = targetSlot && !targetSlot.classList.contains('hidden');

  if (currentChartInstance) { 
    currentChartInstance.destroy(); 
    currentChartInstance = null; 
  }

  allTypes.forEach(t => {
    const slot = document.getElementById(`dash-slot-${t}`);
    if (slot) { slot.innerHTML = ''; slot.classList.add('hidden'); }
    const btn = document.getElementById(`card-btn-${t}`);
    if (btn) {
      btn.classList.remove('border-2', 'border-[#ff2d78]', 'border-[#00b8ff]', 'border-amber-400');
      btn.classList.add('border-[#cbd5e1]', 'dark:border-[#272935]');
    }
  });

  if (isAlreadyOpen) return;

  const data = strategyData[type];
  const activeBorderClass = type === '서학' ? 'border-[#ff2d78]' : (type === '국장' ? 'border-[#00b8ff]' : 'border-amber-400');
  if (btnElement) {
    btnElement.classList.remove('border-[#cbd5e1]', 'dark:border-[#272935]');
    btnElement.classList.add('border-2', activeBorderClass);
  }

  targetSlot.innerHTML = `
        <div class="bg-white dark:bg-[#121318] border border-[#cbd5e1] dark:border-[#22242f] rounded-3xl p-5 sm:p-7 shadow-2xl space-y-6 my-3 animate-fade text-[#0f172a] dark:text-white">
          <div class="flex flex-col sm:flex-row sm:items-start justify-between gap-4  border-[#e2e8f0] dark:border-[#1f212c] pb-5">
            <div class="flex items-center gap-3">
              <div class="w-12 h-12 rounded-2xl bg-[#ff2d78]/10 border border-[#ff2d78]/20 flex items-center justify-center text-2xl shrink-0">
                ${data.icon}
              </div>
              <div>
                <h2 class="text-xl sm:text-2xl font-black text-[#0f172a] dark:text-white tracking-tight">실제 백테스트 검증</h2>
                <p class="text-xs sm:text-sm text-[#64748b] dark:text-[#8e92a4] mt-0.5 font-medium">과거 데이터로 증명된, 개미GTP의 투자 전략입니다.</p>
              </div>
            </div>
            <div class="sm:text-right font-serif italic text-xs sm:text-sm text-[#64748b] dark:text-[#7e8294] shrink-0">
              ${data.quote}
              <div class="text-[11px] text-[#94a3b8] dark:text-[#525565] not-italic font-sans mt-0.5">- gaemiGTP -</div>
            </div>
          </div>

          <div class="flex flex-wrap items-center gap-2 sm:gap-3 text-xs sm:text-sm text-[#64748b] dark:text-[#8e92a4] font-medium">
            <span class="font-black text-[#0f172a] dark:text-white text-base">${data.name}</span>
            <span class="text-[#cbd5e1] dark:text-[#363949]">|</span>
            <span>${data.dateRange}</span>
            <span class="text-[#cbd5e1] dark:text-[#363949]">|</span>
            <span>초기자금 ${data.initial}</span>
            <span class="text-[#cbd5e1] dark:text-[#363949]">|</span>
            <span class="text-emerald-600 dark:text-emerald-400 font-bold">수수료 포함</span>
          </div>

          <div class="grid grid-cols-2 divide-x divide-[#e2e8f0] dark:divide-[#262837] bg-[#f8fafc] dark:bg-[#161720] border border-[#e2e8f0] dark:border-[#262837] rounded-3xl p-5 sm:p-6 text-center">
            <div class="flex flex-col items-center justify-center space-y-1 pr-2 sm:pr-4">
              <div class="text-xs text-[#64748b] dark:text-[#717588] font-bold">1억 → 최종 자산</div>
              <div class="text-2xl sm:text-4xl font-black text-[#0f172a] dark:text-white tracking-tight">${data.finalAsset}</div>
            </div>
            <div class="flex flex-col items-center justify-center space-y-1 pl-2 sm:pl-4">
              <div class="text-xs text-[#64748b] dark:text-[#8e92a4] font-bold">10년 누적수익률</div>
              <div class="text-2xl sm:text-4xl font-black tracking-tight" style="color: ${data.accentColor};">${data.totalReturn}</div>
            </div>
          </div>

          <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div class="bg-[#f8fafc] dark:bg-[#171821] border border-[#e2e8f0] dark:border-[#262837] rounded-2xl p-3.5 text-center space-y-1">
              <div class="text-xs text-[#64748b] dark:text-[#7e8294] font-bold">CAGR</div>
              <div class="text-xl sm:text-2xl font-black" style="color: ${data.accentColor};">${data.cagr}</div>
            </div>
            <div class="bg-[#f8fafc] dark:bg-[#171821] border border-[#e2e8f0] dark:border-[#262837] rounded-2xl p-3.5 text-center space-y-1">
              <div class="text-xs text-[#64748b] dark:text-[#7e8294] font-bold">MDD</div>
              <div class="text-xl sm:text-2xl font-black text-[#00b8ff]">${data.mdd}</div>
            </div>
            <div class="bg-[#f8fafc] dark:bg-[#171821] border border-[#e2e8f0] dark:border-[#262837] rounded-2xl p-3.5 text-center space-y-1">
              <div class="text-xs text-[#64748b] dark:text-[#7e8294] font-bold">총 거래</div>
              <div class="text-xl sm:text-2xl font-black text-[#0f172a] dark:text-white">${data.trades}</div>
            </div>
            <div class="bg-[#f8fafc] dark:bg-[#171821] border border-[#e2e8f0] dark:border-[#262837] rounded-2xl p-3.5 text-center space-y-1">
              <div class="text-xs text-[#64748b] dark:text-[#7e8294] font-bold">승률</div>
              <div class="text-xl sm:text-2xl font-black text-[#0f172a] dark:text-white">${data.winRate}</div>
            </div>
          </div>

          <div class="bg-[#f8fafc] dark:bg-[#161720] border border-[#e2e8f0] dark:border-[#262837] rounded-3xl p-4 sm:p-6 space-y-3">
            <div class="flex items-center justify-between text-xs sm:text-sm">
              <div class="flex items-center gap-2 font-black text-[#0f172a] dark:text-white">
                <span>10년 자산곡선 (단위: 억)</span>
              </div>
              <div class="flex items-center gap-4 text-xs font-bold">
                <span class="flex items-center gap-1.5" style="color: ${data.accentColor};">
                  <span class="w-2.5 h-2.5 rounded-full inline-block" style="background-color: ${data.accentColor};"></span> 전략 수익률
                </span>
                <span class="flex items-center gap-1.5 text-[#64748b] dark:text-[#7e8294]">
                  <span class="w-2.5 h-2.5 rounded-full bg-[#94a3b8] dark:bg-[#7e8294] inline-block"></span> ${data.benchLabel}
                </span>
              </div>
            </div>
            <div class="relative w-full h-52 sm:h-60">
              <canvas id="canvas-acc-${type}"></canvas>
            </div>
          </div>

          <a href="https://www.quantconnect.com" target="_blank" rel="noopener noreferrer" class="block w-full py-3.5 px-6 rounded-2xl bg-gradient-to-r from-[#00a6f4] via-[#00c5ff] to-[#008be3] hover:brightness-110 text-white font-black text-center text-sm sm:text-base shadow-lg shadow-sky-500/20 transition cursor-pointer">
            QuantConnect 원본 결과 보기 ↗
          </a>
        </div>
      `;

  targetSlot.classList.remove('hidden');

  const isDark = document.documentElement.classList.contains('dark');
  const ctx = document.getElementById(`canvas-acc-${type}`).getContext('2d');
  const gradient = ctx.createLinearGradient(0, 0, 0, 220);
  gradient.addColorStop(0, data.accentColor + '44');
  gradient.addColorStop(1, 'rgba(0,0,0,0)');

  currentChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.labels,
      datasets: [
        {
          label: '전략 수익률',
          data: data.chartData,
          borderColor: data.accentColor,
          backgroundColor: gradient,
          borderWidth: 2.5,
          fill: true,
          tension: 0.35,
          pointRadius: 0
        },
        {
          label: data.benchLabel,
          data: data.benchData,
          borderColor: isDark ? '#4e5264' : '#94a3b8',
          borderWidth: 1.5,
          borderDash: [4, 4],
          fill: false,
          tension: 0.2,
          pointRadius: 0
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: isDark ? '#686c80' : '#94a3b8', font: { size: 10 } }
        },
        y: {
          position: 'right',
          grid: { color: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.05)' },
          ticks: {
            color: isDark ? '#686c80' : '#94a3b8',
            font: { size: 10 },
            callback: v => v + '억'
          }
        }
      }
    }
  });
}

let voted = false;

function castVote(type) {
  if (voted) return alert('이미 투표하셨습니다!');
  voted = true;
  const bar = document.getElementById('voteProgressBar');
  const upLbl = document.getElementById('voteUpLabel');
  const downLbl = document.getElementById('voteDownLabel');
  if (type === 'up') {
    bar.style.width = '74%';
    upLbl.innerText = '상승 74%';
    downLbl.innerText = '하락 26%';
  } else {
    bar.style.width = '61%';
    upLbl.innerText = '상승 61%';
    downLbl.innerText = '하락 39%';
  }
}
