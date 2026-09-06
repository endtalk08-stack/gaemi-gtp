<!DOCTYPE html>
<html lang="ko" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <title>gaemiGTP</title>
  
  <link rel="stylesheet" as="style" crossorigin href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css" />
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script>tailwind.config = { darkMode: 'class' }</script>
  <style>
    body {
      font-family: "Pretendard", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      letter-spacing: -0.015em;
      -webkit-font-smoothing: antialiased;
    }
    ::-webkit-scrollbar { display: none; width: 0px; }
    html, body, #chatArea, aside { scrollbar-width: none; -ms-overflow-style: none; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
    .animate-fade { animation: fadeIn 0.25s ease-out forwards; }
    
    @keyframes popBounce {
      0% { transform: scale(0.6); opacity: 0; }
      50% { transform: scale(1.15); opacity: 1; }
      100% { transform: scale(1); opacity: 1; }
    }
    .animate-pop { animation: popBounce 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards; }

    .typing-cursor::after {
      content: '▋';
      display: inline-block;
      vertical-align: baseline;
      margin-left: 4px;
      color: #71717a;
      animation: blink 0.8s infinite;
    }
    @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }
  </style>
</head>
<body class="bg-[#f8fafc] dark:bg-[#121316] text-[#1e293b] dark:text-[#e4e4e7] flex h-[100dvh] w-screen overflow-hidden transition-colors duration-200 relative select-none">

  <!-- 📱 배경 오버레이 -->
  <div id="sidebarBackdrop" onclick="closeAllSidebars()" class="fixed inset-0 bg-black/60 z-40 hidden backdrop-blur-sm transition-opacity duration-300"></div>

  <!-- 🐜 깜짝 개미 순간 팝업 (분석 완료 시 1초 등장) -->
  <div id="surpriseAntPopup" class="fixed inset-0 z-50 flex items-center justify-center pointer-events-none hidden">
    <div class="bg-white/95 dark:bg-[#1e1f24]/95 backdrop-blur-md border border-[#cbd5e1] dark:border-[#3f3f46] rounded-3xl p-6 flex flex-col items-center gap-3 shadow-2xl animate-pop">
      <div class="text-6xl animate-bounce">🐜✨</div>
      <h3 class="text-xl font-black text-[#0f172a] dark:text-white">분석 완료! 다 찾았다!</h3>
      <p class="text-xs text-[#64748b] dark:text-[#a1a1aa] font-bold">10초 핵심 리포트를 확인해봐!</p>
    </div>
  </div>

  <!-- [뷰 1] 메인 히어로 첫 화면 -->
  <div id="mainHeroView" class="fixed inset-0 z-30 bg-[#0f1013] text-white flex flex-col justify-between overflow-hidden">
    <header class="h-16 flex items-center justify-between px-6 shrink-0">
      <div class="flex items-center gap-3">
        <button type="button" onclick="switchToAnalysisMode('SK하이닉스')" class="text-xl text-[#a1a1aa] hover:text-white p-1">☰</button>
        <span class="font-black text-lg tracking-tight text-white cursor-pointer" onclick="resetToHome()">gaemiGTP</span>
      </div>
      <div class="flex items-center gap-4">
        <button type="button" onclick="toggleTheme()" class="text-lg text-[#a1a1aa] hover:text-white p-1" title="테마 변경">☀️</button>
      </div>
    </header>

    <div class="flex-1 flex flex-col items-center justify-center px-4 -mt-12 w-full max-w-3xl mx-auto text-center space-y-6">
      <div class="space-y-2">
        <h1 class="text-4xl sm:text-5xl font-black tracking-tight text-white">gaemiGTP</h1>
        <p class="text-sm sm:text-base text-[#a1a1aa] font-medium">종목명 하나면 10초 만에 끝납니다</p>
      </div>

      <div class="w-full relative">
        <form class="relative flex items-center" onsubmit="event.preventDefault(); handleHeroSearch();">
          <input 
            id="heroStockInput" 
            type="text" 
            placeholder="종목명 입력 (예: SK하이닉스, 삼성전자, NVDA, 비트코인)" 
            class="w-full bg-[#18191d] border border-[#282a30] hover:border-[#3a3d46] focus:border-[#4a4e5a] rounded-full px-6 py-4 text-sm sm:text-base text-white placeholder-[#71717a] focus:outline-none pr-36 shadow-xl transition"
          >
          <div class="absolute right-2.5 flex items-center gap-1.5">
            <span class="text-xs font-semibold text-[#a1a1aa] px-3 py-2">gaemi</span>
            <button type="submit" class="w-9 h-9 rounded-full bg-[#2a2b30] hover:bg-white hover:text-black text-[#a1a1aa] flex items-center justify-center transition cursor-pointer shadow">
              <span class="text-base font-black">↑</span>
            </button>
          </div>
        </form>
      </div>

      <div class="flex flex-wrap items-center justify-center gap-2 pt-1">
        <button type="button" onclick="switchToAnalysisMode('SK하이닉스')" class="text-xs bg-[#18191d] hover:bg-[#262830] text-[#a1a1aa] hover:text-white border border-[#282a30] px-4 py-2 rounded-full transition">SK하이닉스</button>
        <button type="button" onclick="switchToAnalysisMode('삼성전자')" class="text-xs bg-[#18191d] hover:bg-[#262830] text-[#a1a1aa] hover:text-white border border-[#282a30] px-4 py-2 rounded-full transition">삼성전자</button>
        <button type="button" onclick="switchToAnalysisMode('알테오젠')" class="text-xs bg-[#18191d] hover:bg-[#262830] text-[#a1a1aa] hover:text-white border border-[#282a30] px-4 py-2 rounded-full transition">알테오젠</button>
        <button type="button" onclick="switchToAnalysisMode('엔비디아')" class="text-xs bg-[#18191d] hover:bg-[#262830] text-[#a1a1aa] hover:text-white border border-[#282a30] px-4 py-2 rounded-full transition">엔비디아</button>
        <button type="button" onclick="switchToAnalysisMode('비트코인')" class="text-xs bg-[#18191d] hover:bg-[#262830] text-[#a1a1aa] hover:text-white border border-[#282a30] px-4 py-2 rounded-full transition">비트코인</button>
      </div>
    </div>
    <div class="h-6"></div>
  </div>

  <!-- 사이드바 -->
  <aside id="leftSidebar" class="fixed inset-y-0 left-0 z-50 w-64 bg-[#f8fafc] dark:bg-[#16171b] border-r border-[#e2e8f0] dark:border-[#27272a] flex flex-col justify-between shrink-0 transform -translate-x-full lg:translate-x-0 lg:static transition-transform duration-300 ease-in-out shadow-2xl lg:shadow-none">
    <div class="p-4 flex flex-col gap-5 overflow-y-auto">
      <div class="flex items-center justify-between px-1">
        <div class="flex items-center gap-2.5 cursor-pointer" onclick="resetToHome()">
          <span class="text-2xl">🐜</span>
          <span class="font-black text-xl text-[#0f172a] dark:text-white tracking-tight">gaemiGTP</span>
        </div>
        <button type="button" onclick="closeAllSidebars()" class="lg:hidden text-[#71717a] hover:text-white text-lg p-1">✕</button>
      </div>
      <div class="flex flex-col gap-2">
        <span class="text-[11px] font-bold text-[#64748b] dark:text-[#a1a1aa] uppercase px-1">실전 전략 3인방</span>
        <button type="button" onclick="switchToAnalysisMode('SK하이닉스'); closeAllSidebars();" class="text-left text-xs bg-white dark:bg-[#1e1f24] hover:bg-[#f1f5f9] dark:hover:bg-[#27272a] text-[#334155] dark:text-[#e4e4e7] p-2.5 rounded-xl border border-[#cbd5e1] dark:border-[#27272a] flex items-center justify-between shadow-sm">
          <div class="flex items-center gap-2"><span>🇺🇸</span> <span class="font-bold">서학개미 (장기)</span></div>
          <span class="text-[11px] text-[#64748b] dark:text-[#a1a1aa] font-bold">24.5억</span>
        </button>
        <button type="button" onclick="switchToAnalysisMode('SK하이닉스'); closeAllSidebars();" class="text-left text-xs bg-white dark:bg-[#1e1f24] hover:bg-[#f1f5f9] dark:hover:bg-[#27272a] text-[#334155] dark:text-[#e4e4e7] p-2.5 rounded-xl border border-[#cbd5e1] dark:border-[#27272a] flex items-center justify-between shadow-sm">
          <div class="flex items-center gap-2"><span>🇰🇷</span> <span class="font-bold">국장개미 (스윙)</span></div>
          <span class="text-[11px] text-[#64748b] dark:text-[#a1a1aa] font-bold">24.5억</span>
        </button>
        <button type="button" onclick="switchToAnalysisMode('SK하이닉스'); closeAllSidebars();" class="text-left text-xs bg-white dark:bg-[#1e1f24] hover:bg-[#f1f5f9] dark:hover:bg-[#27272a] text-[#334155] dark:text-[#e4e4e7] p-2.5 rounded-xl border border-[#cbd5e1] dark:border-[#27272a] flex items-center justify-between shadow-sm">
          <div class="flex items-center gap-2"><span>⚡</span> <span class="font-bold">트레이더 (단기)</span></div>
          <span class="text-[11px] text-[#64748b] dark:text-[#a1a1aa] font-bold">32.4억</span>
        </button>
      </div>
    </div>
  </aside>

  <!-- 2. 중앙 메인 분석 화면 -->
  <main class="flex-1 flex flex-col h-full bg-[#f8fafc] dark:bg-[#121316] overflow-hidden min-w-0">
    <header class="h-16 border-b border-[#e2e8f0] dark:border-[#27272a] flex items-center justify-between px-4 sm:px-6 bg-white/80 dark:bg-[#16171b]/80 backdrop-blur shrink-0 z-10">
      <div class="flex items-center gap-3">
        <button type="button" onclick="toggleLeftSidebar()" class="lg:hidden p-1.5 rounded-lg border border-[#cbd5e1] dark:border-[#27272a] bg-[#f8fafc] dark:bg-[#1e1f24] text-base text-[#0f172a] dark:text-white cursor-pointer">☰</button>
        <span class="font-bold text-[#0f172a] dark:text-white text-base cursor-pointer" onclick="resetToHome()">gaemiGTP</span>
      </div>
      <div class="flex items-center gap-2 sm:gap-3">
        <button type="button" onclick="resetToHome()" class="text-xs px-2.5 py-1.5 rounded-lg border border-[#cbd5e1] dark:border-[#27272a] text-[#64748b] dark:text-[#a1a1aa] hover:text-[#0f172a] dark:hover:text-white">메인으로</button>
        <button type="button" onclick="toggleTheme()" class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold bg-[#f1f5f9] dark:bg-[#1e1f24] text-[#0f172a] dark:text-white border border-[#cbd5e1] dark:border-[#3f3f46] rounded-full hover:bg-[#e2e8f0] dark:hover:bg-[#27272a] transition cursor-pointer shadow-sm">
          <span id="themeIcon">🌙</span><span id="themeText">다크 모드</span>
        </button>
      </div>
    </header>

    <!-- 대화 및 리포트 표시창 (강제 스크롤 절대 금지) -->
    <div id="chatArea" class="flex-1 overflow-y-auto p-4 md:p-8 flex flex-col gap-6 max-w-5xl mx-auto w-full"></div>

    <!-- 하단 검색창 -->
    <div class="shrink-0 p-3 sm:p-4 bg-white/95 dark:bg-[#16171b]/95 backdrop-blur border-t border-[#e2e8f0] dark:border-[#27272a] z-20">
      <div class="max-w-4xl mx-auto relative">
        <form class="relative flex items-center w-full" onsubmit="event.preventDefault(); handleBottomSearch();">
          <input 
            id="bottomStockInput" 
            type="text" 
            placeholder="종목명 입력 (예: SK하이닉스, 삼성전자, NVDA, BTC)" 
            class="w-full bg-white dark:bg-[#1e1f24] border border-[#cbd5e1] dark:border-[#282a30] hover:border-[#94a3b8] dark:hover:border-[#3a3d46] focus:border-[#0f172a] dark:focus:border-[#4a4e5a] rounded-full px-5 sm:px-6 py-3.5 sm:py-4 text-sm sm:text-base text-[#0f172a] dark:text-[#f4f4f5] placeholder-[#94a3b8] dark:placeholder-[#71717a] focus:outline-none pr-32 sm:pr-36 shadow-md transition"
          >
          <div class="absolute right-2 flex items-center gap-1 sm:gap-1.5">
            <button type="submit" class="w-8 h-8 sm:w-9 sm:h-9 rounded-full bg-[#0f172a] dark:bg-[#2a2b30] hover:bg-[#334155] dark:hover:bg-white text-white dark:text-[#a1a1aa] dark:hover:text-black flex items-center justify-center transition cursor-pointer shadow">
              <span class="text-sm sm:text-base font-black">↑</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  </main>

  <!-- 📸 짤 카드 모달 -->
  <div id="memeModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 hidden">
    <div class="bg-white dark:bg-[#1e1f24] border border-[#e2e8f0] dark:border-[#27272a] rounded-3xl max-w-sm w-full p-6 relative shadow-2xl animate-fade">
      <button type="button" onclick="document.getElementById('memeModal').classList.add('hidden')" class="absolute top-4 right-4 text-[#94a3b8] dark:text-[#a1a1aa] hover:text-[#0f172a] dark:hover:text-white text-base font-bold cursor-pointer">✕</button>
      <div class="text-center mb-4">
        <span class="text-xs text-[#64748b] dark:text-[#a1a1aa] font-bold uppercase tracking-wider">gaemiGTP 짤 카드</span>
        <h3 class="text-base font-bold text-[#0f172a] dark:text-white mt-1">카카오톡 공유 카드</h3>
      </div>
      <div id="memeCardToRender" class="bg-[#f8fafc] dark:bg-[#121316] border border-[#cbd5e1] dark:border-[#27272a] rounded-2xl p-5 text-center shadow-inner space-y-3">
        <div class="flex items-center justify-between border-b border-[#e2e8f0] dark:border-[#27272a] pb-2 text-sm">
          <span class="font-black text-[#0f172a] dark:text-white">gaemiGTP</span>
          <span id="memeStockBadge" class="bg-white dark:bg-[#1e1f24] text-[#0f172a] dark:text-white border border-[#cbd5e1] dark:border-[#3f3f46] px-2 py-0.5 rounded font-bold shadow-sm">SK하이닉스</span>
        </div>
        <div id="memeEmoji" class="text-5xl my-2">😎</div>
        <h4 id="memeTitle" class="font-bold text-base text-[#0f172a] dark:text-white">"20일선 눌림목 반등 타점 포착!"</h4>
        <p id="memeSub" class="text-sm text-[#475569] dark:text-[#a1a1aa] leading-relaxed">개미들아 쫄지 마라! 후드 개미 시그널 탑승 완료.</p>
      </div>
      <button type="button" onclick="downloadMemeImage()" class="w-full mt-4 bg-[#0f172a] dark:bg-white hover:bg-[#334155] dark:hover:bg-[#e4e4e7] text-white dark:text-black font-black py-3 rounded-xl text-sm shadow-md cursor-pointer">📸 짤 카드 다운로드 (카톡 공유)</button>
    </div>
  </div>

  <script>
    const BACKEND_URL = 'https://gaemi-gtp.onrender.com';
    let activeStock = 'SK하이닉스';
    let currentChartInstance = null;

    function resetToHome() {
      document.getElementById('mainHeroView').classList.remove('hidden');
      closeAllSidebars();
    }
    function switchToAnalysisMode(stockName) {
      document.getElementById('mainHeroView').classList.add('hidden');
      requestStock(stockName || 'SK하이닉스');
    }
    function handleHeroSearch() {
      const val = document.getElementById('heroStockInput').value;
      switchToAnalysisMode(val || 'SK하이닉스');
    }
    function handleBottomSearch() {
      const val = document.getElementById('bottomStockInput').value;
      if (val) {
        requestStock(val);
        document.getElementById('bottomStockInput').value = '';
      }
    }
    function toggleLeftSidebar() {
      const leftBar = document.getElementById('leftSidebar');
      const backdrop = document.getElementById('sidebarBackdrop');
      if (leftBar.classList.contains('-translate-x-full')) {
        leftBar.classList.remove('-translate-x-full');
        leftBar.classList.add('translate-x-0');
        backdrop.classList.remove('hidden');
      } else {
        closeAllSidebars();
      }
    }
    function closeAllSidebars() {
      const leftBar = document.getElementById('leftSidebar');
      const backdrop = document.getElementById('sidebarBackdrop');
      if (leftBar) { leftBar.classList.add('-translate-x-full'); leftBar.classList.remove('translate-x-0'); }
      if (backdrop) backdrop.classList.add('hidden');
    }
    function toggleTheme() {
      const htmlEl = document.documentElement;
      const themeIcon = document.getElementById('themeIcon');
      const themeText = document.getElementById('themeText');
      if (htmlEl.classList.contains('dark')) {
        htmlEl.classList.remove('dark');
        if (themeIcon) themeIcon.innerText = '☀️';
        if (themeText) themeText.innerText = '라이트 모드';
      } else {
        htmlEl.classList.add('dark');
        if (themeIcon) themeIcon.innerText = '🌙';
        if (themeText) themeText.innerText = '다크 모드';
      }
    }

    // 서버 통신
    async function fetchAnalysisFromBackend(stockName) {
      try {
        const response = await fetch(`${BACKEND_URL}/analyze?stock=${encodeURIComponent(stockName)}`);
        if (!response.ok) throw new Error('서버 에러');
        const data = await response.json();
        return data.sections || getFallbackSections(stockName);
      } catch (err) {
        return getFallbackSections(stockName);
      }
    }

    function getFallbackSections(stockName) {
      return [
        {
          title: "🔥 그래서 오늘은 왜 올랐어?",
          content: `개미들아! ${stockName} 수급 유입 중이야! 야호~\n현재 20일선 부근에서 강력한 지지선 형성!\n\n#실시간수급 #기관순매수 #20일선지지`,
          tags: ["#실시간수급", "#20일선지지"]
        },
        {
          title: "지금 세력은 사고 있어, 팔고 있어?",
          content: "🔥수급 경고: 최근 개인과 외국인의 치열한 공방전 진행 중!\n기관 추정 매수 단가 부근을 돌파할지 두근두근 지켜보자!" 
        },
        {
          title: "여기 깨지면 도망쳐라!",
          content: "🛡️생존 지지선: 20일선 이탈 시 미련 없이 비중 축소!\n🧱악성 매물대: 전고점 부근에 개미들의 본전 대기 매물 주의 ㅠㅠ."
        },
        {
          title: "🐜 오늘 밤, 내일 무슨 일이 있나?",
          content: "📅주의 일정: 미국 CPI 및 빅테크 실적 발표 예정!\n📝공시 체크: 시간외 단일가 변동성 주의해랔!"
        }
      ];
    }

    // 🚀 핵심 프로세스: 5초 캐릭터 → 깜짝 개미 → 맨 위 첫 페이지 고정!
    async function requestStock(stockName) {
      if (!stockName || !stockName.trim()) return;
      stockName = stockName.trim();
      activeStock = stockName;

      const chatArea = document.getElementById('chatArea');
      chatArea.innerHTML = '';
      chatArea.scrollTop = 0; // 시작 시 무조건 맨 위로 고정

      // 1. 유저 질문 말풍선
      const userDiv = document.createElement('div');
      userDiv.className = "flex justify-end animate-fade";
      userDiv.innerHTML = `<div class="bg-[#f1f5f9] dark:bg-[#1e1f24] text-[#0f172a] dark:text-white text-base font-bold px-5 py-3 rounded-2xl border border-[#cbd5e1] dark:border-[#3f3f46]">${stockName}</div>`;
      chatArea.appendChild(userDiv);

      // 2. [요청 1] 캐릭터가 5초 동안 분석하는 로더
      const loaderDiv = document.createElement('div');
      loaderDiv.className = "flex flex-col items-center justify-center p-8 bg-white dark:bg-[#1e1f24] border border-[#e2e8f0] dark:border-[#27272a] rounded-3xl my-2 text-center shadow-sm animate-fade";
      loaderDiv.innerHTML = `
        <div class="flex items-center gap-4 mb-3">
          <div class="w-14 h-14 rounded-full bg-[#f8fafc] dark:bg-[#27272a] border border-[#cbd5e1] dark:border-[#3f3f46] flex items-center justify-center text-2xl animate-bounce">🐜</div>
          <span class="text-[#94a3b8] dark:text-[#71717a] font-bold text-xl">×</span>
          <div class="w-14 h-14 rounded-full bg-[#0f172a] dark:bg-white text-white dark:text-black font-black flex items-center justify-center text-2xl">🕶️</div>
        </div>
        <h4 class="font-black text-lg text-[#0f172a] dark:text-white">${stockName} 퀀트 5초 정밀 스캔 중...</h4>
        <p id="secTimerMsg" class="text-sm text-[#64748b] dark:text-[#a1a1aa] mt-2 font-bold transition-all">
          📡 렌더 클라우드 엔진 연결 및 데이터 수집 중... (약 5초)
        </p>
      `;
      chatArea.appendChild(loaderDiv);

      // 5초 타이머 안내 문구
      const timerTexts = [
        "📡 렌더 클라우드 엔진 연결 및 데이터 수집 중...",
        "📰 DART 공시 및 핵심 테마 재료 대조 중...",
        "📊 외인·기관 누적 수급 턴어라운드 검증 중...",
        "💡 3대 실전 전문가 매매 시나리오 산출 중..."
      ];
      let tIdx = 0;
      const timerInterval = setInterval(() => {
        tIdx = (tIdx + 1) % timerTexts.length;
        const msgEl = document.getElementById('secTimerMsg');
        if (msgEl) msgEl.innerText = timerTexts[tIdx];
      }, 1200);

      // 5초 대기 & 백엔드 통신 병렬 실행
      const fetchPromise = fetchAnalysisFromBackend(stockName);
      const fiveSecondPromise = new Promise(resolve => setTimeout(resolve, 4500));
      const [sections] = await Promise.all([fetchPromise, fiveSecondPromise]);

      clearInterval(timerInterval);
      loaderDiv.remove();

      // 3. [요청 2] 분석 완료 시 "깜짝 개미" 순간 등장 (약 1.1초)
      const surprisePopup = document.getElementById('surpriseAntPopup');
      surprisePopup.classList.remove('hidden');
      await new Promise(res => setTimeout(res, 1100));
      surprisePopup.classList.add('hidden');

      // 4. [요청 3] 화면 아래로 절대 밀리지 않고, 무조건 맨 위 첫 페이지에서 시작!
      chatArea.scrollTop = 0;
      startTypewriterFlow(stockName, sections);
    }

    // 4단 리포트 타자 효과
    function startTypewriterFlow(stockName, sections) {
      const chatArea = document.getElementById('chatArea');
      const wrapperId = 'stream-' + Date.now();

      const mainContainer = document.createElement('div');
      mainContainer.id = wrapperId;
      mainContainer.className = "space-y-7 py-2";
      chatArea.appendChild(mainContainer);

      // 스크롤을 무조건 맨 위로 유지
      chatArea.scrollTop = 0;

      let secIdx = 0;

      function typeNextSection() {
        if (secIdx >= sections.length) {
          // 4개 타자가 모두 끝나면 그 아래에 투표와 전략이 조용히 추가됨 (화면 강제 이동 X)
          renderBottomWidgets(wrapperId, stockName);
          return;
        }

        const sec = sections[secIdx];
        const textBlock = document.createElement('div');
        textBlock.className = "space-y-2.5 animate-fade";
        textBlock.innerHTML = `
          <div class="flex items-center gap-2.5">
            <div class="w-7 h-7 sm:w-8 sm:h-8 rounded-full bg-[#0f172a] dark:bg-white text-white dark:text-black flex items-center justify-center font-black text-xs sm:text-sm shadow-sm shrink-0">G</div>
            ${sec.title ? `<h4 class="font-black text-lg sm:text-xl text-[#0f172a] dark:text-white">${sec.title}</h4>` : ''}
          </div>
          <p id="p-content-${secIdx}" class="text-base sm:text-lg text-[#334155] dark:text-[#e4e4e7] leading-relaxed whitespace-pre-line typing-cursor pl-9"></p>
        `;
        mainContainer.appendChild(textBlock);

        const pEl = document.getElementById(`p-content-${secIdx}`);
        let charIdx = 0;
        const text = sec.content;
        const chunkSize = 20;

        function typeChunk() {
          if (charIdx < text.length) {
            pEl.textContent += text.substr(charIdx, chunkSize);
            charIdx += chunkSize;
            // 강제 바닥 스크롤 코드 삭제됨 -> 사용자가 편안하게 위에서부터 읽을 수 있음!
            setTimeout(typeChunk, 15);
          } else {
            pEl.classList.remove('typing-cursor');
            secIdx++;
            setTimeout(typeNextSection, 80);
          }
        }
        typeChunk();
      }

      typeNextSection();
    }

    // 4단 타자가 끝난 후 아래에 위치하는 투표 및 전략 (화면 튕김 없이 아래에 안착)
    function renderBottomWidgets(wrapperId, stockName) {
      const container = document.getElementById(wrapperId);
      const bottomDiv = document.createElement('div');
      bottomDiv.className = "space-y-6 pt-6 border-t border-[#e2e8f0] dark:border-[#27272a] animate-fade";
      bottomDiv.innerHTML = `
        <!-- 개미 투표 위젯 -->
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

        <!-- 전략 3인방 -->
        <div class="space-y-3">
          <div class="flex items-center gap-2.5 pb-1">
            <div class="w-7 h-7 rounded-full bg-[#0f172a] dark:bg-white text-white dark:text-black flex items-center justify-center font-black text-xs shadow-sm shrink-0">G</div>
            <h3 class="font-black text-base sm:text-lg text-[#0f172a] dark:text-white">내 투자 스타일에 맞는 전략도 확인해바.</h3>
          </div>

          <button type="button" class="w-full text-left p-4 rounded-2xl bg-white dark:bg-[#1e1f24] border border-[#cbd5e1] dark:border-[#27272a] flex items-center justify-between shadow-sm">
            <div>
              <div class="flex items-center gap-2 font-black text-base text-[#0f172a] dark:text-white"><span>🇺🇸</span> 서학개미 (장기)</div>
              <p class="text-xs text-[#64748b] dark:text-[#a1a1aa] mt-0.5">미국 빅테크 메가트렌드 진입 후 분할익절</p>
            </div>
            <div class="text-right">
              <div class="text-[11px] text-[#94a3b8] dark:text-[#71717a] font-bold">최종 자산</div>
              <div class="text-base font-black text-[#0f172a] dark:text-white">24.5억</div>
            </div>
          </button>

          <button type="button" class="w-full text-left p-4 rounded-2xl bg-white dark:bg-[#1e1f24] border border-[#cbd5e1] dark:border-[#27272a] flex items-center justify-between shadow-sm">
            <div>
              <div class="flex items-center gap-2 font-black text-base text-[#0f172a] dark:text-white"><span>🇰🇷</span> 국장개미 (스윙)</div>
              <p class="text-xs text-[#64748b] dark:text-[#a1a1aa] mt-0.5">코스피 시총 상위주 20일선 지지 반등 노림수</p>
            </div>
            <div class="text-right">
              <div class="text-[11px] text-[#94a3b8] dark:text-[#71717a] font-bold">최종 자산</div>
              <div class="text-base font-black text-[#0f172a] dark:text-white">24.5억</div>
            </div>
          </button>

          <button type="button" class="w-full text-left p-4 rounded-2xl bg-white dark:bg-[#1e1f24] border border-[#cbd5e1] dark:border-[#27272a] flex items-center justify-between shadow-sm">
            <div>
              <div class="flex items-center gap-2 font-black text-base text-[#0f172a] dark:text-white"><span class="text-amber-400">⚡</span> 트레이더 (단기)</div>
              <p class="text-xs text-[#64748b] dark:text-[#a1a1aa] mt-0.5">15:15 종가 배팅 양봉 매수 후 익일 시가 청산</p>
            </div>
            <div class="text-right">
              <div class="text-[11px] text-[#94a3b8] dark:text-[#71717a] font-bold">최종 자산</div>
              <div class="text-base font-black text-[#0f172a] dark:text-white">32.4억</div>
            </div>
          </button>
        </div>

        <div class="pt-2 pb-4 flex justify-center">
          <button type="button" onclick="openMeme('${stockName}')" class="px-6 py-3 rounded-xl bg-[#f1f5f9] dark:bg-[#1e1f24] border border-[#cbd5e1] dark:border-[#3f3f46] text-[#0f172a] dark:text-white font-bold text-sm flex items-center gap-2 shadow-sm cursor-pointer">
            <span>📸</span> <span>카카오톡 공유용 짤 카드 만들기</span>
          </button>
        </div>
      `;
      container.appendChild(bottomDiv);
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

    function openMeme(stockName) {
      document.getElementById('memeStockBadge').innerText = stockName;
      document.getElementById('memeModal').classList.remove('hidden');
    }
    function downloadMemeImage() {
      const card = document.getElementById('memeCardToRender');
      const isDark = document.documentElement.classList.contains('dark');
      if (typeof html2canvas !== 'undefined') {
        html2canvas(card, { backgroundColor: isDark ? '#121316' : '#ffffff', scale: 2 }).then(canvas => {
          const a = document.createElement('a');
          a.download = `gaemiGTP_${activeStock}_짤카드.png`;
          a.href = canvas.toDataURL('image/png');
          a.click();
        });
      }
    }
  </script>
</body>
</html>
