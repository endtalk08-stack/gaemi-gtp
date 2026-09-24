(function(){
  const NEWS_HTML = `<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>News App - 완성형</title>
    <style>
        :root {
            --bg-color: #131314;
            --card-bg: #1E1F20;
            --card-hover: #282A2C;
            --text-main: #F2F2F2;
            --text-sub: #8E918F;
            --border-color: #282A2C;
            --accent-color: #ffffff;
            --positive-color: #22C55E;
            --negative-color: #EC4899;
            --like-color: #FF5A5A;
            --dislike-color: #5A9BFF;
            --star-color: #FFD24D;
            --chip-active-bg: #2B3A5A;
            --chip-active-text: #8AB4F8;
            --bar-gradient: linear-gradient(90deg, #5B7FFF 0%, #A78BFA 100%);
            --bar-track: #2A2A2E;
        }

        * {
            margin: 0; padding: 0; box-sizing: border-box;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            -webkit-tap-highlight-color: transparent;
        }

        body {
            background-color: var(--bg-color);
            color: var(--text-main);
            display: flex;
            justify-content: center;
            padding: 20px;
            min-height: 100vh;
        }

        .app-container {
            width: 100%;
            max-width: 600px;
            background-color: var(--bg-color);
            position: relative;
        }

        .icon {
            width: 18px; height: 18px;
            stroke: currentColor;
            stroke-width: 2;
            stroke-linecap: round;
            stroke-linejoin: round;
            fill: none;
            display: block;
        }
        .icon-sm { width: 14px; height: 14px; }
        .icon-lg { width: 22px; height: 22px; }

        /* 검색 바 */
        .search-bar {
            display: flex; align-items: center; gap: 10px;
            background-color: var(--card-bg);
            border-radius: 10px;
            padding: 12px 14px;
            margin-bottom: 18px;
            cursor: text;
            transition: background-color 0.2s;
        }
        .search-bar:hover { background-color: var(--card-hover); }
        .search-bar .icon { color: var(--text-sub); flex-shrink: 0; }
        .search-bar input {
            flex: 1; background: none; border: none;
            color: var(--text-main); font-size: 14px; outline: none;
        }
        .search-bar input::placeholder { color: var(--text-sub); }

        /* 실시간 트렌드 헤더 */
        .realtime-header {
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 12px; padding: 10px 8px;
            border-radius: 8px; cursor: pointer;
            transition: background-color 0.2s;
        }
        .realtime-header:hover { background-color: var(--card-bg); }
        .realtime-title {
            display: flex; align-items: center; gap: 8px;
            font-size: 14px; font-weight: bold;
        }
        .realtime-title .live-dot {
            width: 6px; height: 6px;
            background-color: #22C55E;
            border-radius: 50%;
            box-shadow: 0 0 8px #22C55E;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
        }
        .realtime-count {
            font-size: 12px; color: var(--text-sub);
            background-color: var(--card-bg);
            padding: 2px 8px; border-radius: 10px;
            font-weight: bold;
        }
        .realtime-more {
            display: flex; align-items: center; gap: 4px;
            font-size: 12px; color: var(--text-sub);
            padding: 4px 8px; border-radius: 6px;
        }

        /* 카테고리 탭 */
        .category-tabs {
            display: flex; gap: 6px; margin-bottom: 24px;
            overflow-x: auto;
            scrollbar-width: none; -ms-overflow-style: none;
            padding-bottom: 2px;
        }
        .category-tabs::-webkit-scrollbar { display: none; }
        .category-tab {
            flex-shrink: 0;
            background-color: var(--card-bg);
            color: var(--text-sub);
            border: 1px solid transparent;
            padding: 7px 14px; border-radius: 8px;
            font-size: 12px; font-weight: bold;
            cursor: pointer; transition: all 0.2s;
            white-space: nowrap;
        }
        .category-tab:hover { background-color: var(--card-hover); color: var(--text-main); }
        .category-tab.active {
            background-color: var(--chip-active-bg);
            color: var(--chip-active-text);
        }

        /* 화면 1: 뉴스 목록 */
        #list-view { display: block; }

        /* 주요뉴스 캐러셀 */
        .headline-section { margin-bottom: 30px; }
        .section-header { 
            display: flex; justify-content: space-between; align-items: center; 
            margin-bottom: 15px; font-size: 18px; font-weight: bold; 
        }
        .section-header span { color: var(--text-sub); font-size: 14px; }

        .headline-carousel {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .carousel-arrow {
            width: 32px; height: 32px;
            border-radius: 50%;
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            color: var(--text-main);
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            flex-shrink: 0;
            transition: all 0.2s;
        }
        .carousel-arrow:hover {
            background-color: var(--card-hover);
            border-color: #3A3A3A;
        }
        .carousel-arrow:disabled {
            opacity: 0.25;
            cursor: not-allowed;
        }
        .carousel-arrow svg {
            width: 16px; height: 16px;
            stroke: currentColor;
            stroke-width: 2.5;
            stroke-linecap: round; stroke-linejoin: round;
            fill: none;
        }

        .carousel-viewport { flex: 1; min-width: 0; }

        .carousel-track {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            animation: slideFade 0.35s ease;
        }

        @keyframes slideFade {
            from { opacity: 0; transform: translateX(10px); }
            to { opacity: 1; transform: translateX(0); }
        }

        .headline-card { 
            background-color: var(--card-bg); 
            border-radius: 8px; padding: 15px; 
            display: flex; flex-direction: column; 
            justify-content: space-between; min-height: 140px;
            cursor: pointer;
            transition: background-color 0.2s;
        }
        .headline-card:hover { background-color: var(--card-hover); }
        .headline-card.blue-tint { background-color: #1E1F20; }

        .card-top { 
            display: flex; justify-content: space-between; 
            font-size: 11px; color: var(--text-sub); 
            margin-bottom: 10px; 
        }
        .tag { 
            background-color: #282A2C; color: #a0a0a0; 
            padding: 2px 6px; border-radius: 4px; 
            font-weight: bold; margin-right: 5px; 
        }
        .headline-title { 
            font-size: 14px; font-weight: bold; 
            line-height: 1.4; margin-bottom: 15px; 
            flex-grow: 1;
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }
        .card-bottom { 
            display: flex; justify-content: flex-end; 
            align-items: center; gap: 4px; 
            font-size: 11px; color: var(--text-sub); 
        }

        /* 인디케이터 */
        .carousel-dots {
            display: flex;
            justify-content: center;
            gap: 6px;
            margin-top: 12px;
        }
        .carousel-dot {
            width: 6px; height: 6px;
            border-radius: 50%;
            background-color: #3A3A3A;
            cursor: pointer;
            transition: all 0.2s;
        }
        .carousel-dot.active {
            background-color: #8AB4F8;
            width: 18px;
            border-radius: 3px;
        }

        /* 뉴스 리스트 */
        .news-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
        .news-header h2 { font-size: 18px; }
        .filters { display: flex; gap: 8px; }
        .filter-btn { 
            display: flex; align-items: center; gap: 4px; 
            background-color: var(--card-bg); color: var(--text-main); 
            border: 1px solid var(--border-color); 
            padding: 6px 10px; border-radius: 6px; 
            font-size: 12px; cursor: pointer; 
        }
        .filter-btn:hover { background-color: var(--card-hover); }

        .news-list { display: flex; flex-direction: column; }
        .news-item { 
            background-color: var(--card-bg); border-radius: 8px; 
            padding: 15px; margin-bottom: 10px; 
            cursor: pointer; transition: background-color 0.2s; 
        }
        .news-item:hover { background-color: var(--card-hover); }
        .news-item-top { 
            display: flex; justify-content: space-between; 
            font-size: 12px; color: var(--text-sub); margin-bottom: 8px; 
        }
        .news-item-title { 
            font-size: 15px; font-weight: bold; 
            line-height: 1.4; margin-bottom: 8px; 
        }
        .news-item-bottom { 
            display: flex; justify-content: space-between; 
            align-items: center; font-size: 12px; color: var(--text-sub); 
        }
        .news-item-bottom div { display: flex; align-items: center; gap: 4px; }
        .ticker { 
            background-color: #282A2C; padding: 2px 6px; 
            border-radius: 4px; font-size: 11px; 
        }
        .hidden-news { display: none; }

        .load-more-btn { 
            width: 100%; background-color: var(--card-bg); 
            color: var(--text-main); border: none; 
            border-radius: 8px; padding: 15px; margin-bottom: 10px; 
            font-size: 14px; font-weight: bold; cursor: pointer; 
            transition: background-color 0.2s; text-align: center; 
        }
        .load-more-btn:hover { background-color: var(--card-hover); }

        /* 화면 2: 뉴스 상세 */
        #detail-view {
            display: none;
            flex-direction: column;
            animation: fadeIn 0.3s ease-in-out;
            padding-bottom: 40px;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .detail-top-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        .icon-btn { 
            background: none; border: none; 
            color: var(--text-sub); cursor: pointer; 
            padding: 5px; border-radius: 6px;
            display: flex; align-items: center; justify-content: center;
            transition: all 0.2s;
        }
        .icon-btn:hover { color: var(--text-main); background-color: var(--card-hover); }
        .left-actions, .right-actions { display: flex; gap: 10px; }

        /* 🌟 뉴스 요약 카드 (출처 제목 아래로 이동) */
        .news-preview-card {
            background-color: var(--card-bg);
            border-radius: 10px;
            padding: 16px;
            margin-bottom: 24px;
        }
        .preview-top {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 10px;
            gap: 10px;
        }
        .preview-tag {
            background-color: #282A2C;
            color: #a0a0a0;
            padding: 3px 8px;
            border-radius: 5px;
            font-size: 11px;
            font-weight: bold;
            flex-shrink: 0;
        }
        .preview-time {
            font-size: 12px;
            color: var(--text-sub);
            flex-shrink: 0;
        }
        .preview-title {
            font-size: 15px;
            font-weight: bold;
            line-height: 1.4;
            color: var(--text-main);
            margin-bottom: 8px;
        }
        /* 🌟 출처 - 제목 바로 아래 */
        .preview-source {
            font-size: 12px;
            color: var(--text-sub);
            font-weight: bold;
            margin-bottom: 12px;
        }
        .preview-bottom {
            display: flex;
            justify-content: flex-end;
            align-items: center;
            font-size: 12px;
            color: var(--text-sub);
        }
        .preview-views {
            display: flex;
            align-items: center;
            gap: 4px;
        }

        .info-section { margin-bottom: 22px; }
        .info-section-title {
            font-size: 13px;
            color: var(--text-sub);
            margin-bottom: 10px;
            font-weight: bold;
        }
        .info-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }
        .info-chip {
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 13px;
            color: var(--text-main);
            font-weight: bold;
            cursor: pointer;
            transition: all 0.2s;
        }
        .info-chip:hover {
            background-color: var(--card-hover);
            border-color: #3A3A3A;
        }

        /* 관련 종목 */
        .stock-list-rows {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        .stock-row-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            background-color: var(--card-bg);
            border-radius: 8px;
            padding: 12px 14px;
            transition: background-color 0.2s;
        }
        .stock-row-item:hover { background-color: var(--card-hover); }
        .stock-row-left {
            display: flex;
            align-items: center;
            gap: 10px;
            min-width: 0;
            flex: 1;
        }
        .stock-row-ticker {
            font-size: 14px;
            font-weight: bold;
            color: var(--text-main);
            font-variant-numeric: tabular-nums;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .fav-btn {
            background: none;
            border: none;
            cursor: pointer;
            padding: 6px;
            border-radius: 6px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s;
            flex-shrink: 0;
        }
        .fav-btn:hover { background-color: rgba(255, 210, 77, 0.1); }
        .fav-btn svg {
            width: 20px; height: 20px;
            fill: none;
            stroke: var(--text-sub);
            stroke-width: 2;
            stroke-linejoin: round;
            stroke-linecap: round;
            transition: all 0.2s;
        }
        .fav-btn.favorited svg {
            fill: var(--star-color);
            stroke: var(--star-color);
        }
        .fav-btn.favorited {
            animation: starPop 0.3s ease;
        }
        @keyframes starPop {
            0% { transform: scale(1); }
            50% { transform: scale(1.25); }
            100% { transform: scale(1); }
        }

        /* 감정 통계 */
        .sentiment-stats {
            display: flex;
            align-items: center;
            gap: 20px;
            padding: 18px 4px;
            margin-bottom: 24px;
            font-size: 14px;
            color: var(--text-sub);
        }
        .stat-item {
            display: flex;
            align-items: center;
            gap: 6px;
            font-weight: bold;
            cursor: pointer;
            transition: color 0.2s;
        }
        .stat-item:hover { color: var(--text-main); }
        .stat-item .icon { width: 18px; height: 18px; }
        .stat-item.like .icon { stroke: var(--like-color); }
        .stat-item.dislike .icon { stroke: var(--dislike-color); }
        .stat-item.up .icon { stroke: #22C55E; }
        .stat-views {
            margin-left: auto;
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 13px;
            color: var(--text-sub);
        }

        /* 영향도 */
        .impact-section { margin-bottom: 20px; }
        .impact-title-box {
            background-color: var(--card-bg);
            border-radius: 10px;
            padding: 18px 20px;
            margin-bottom: 14px;
            text-align: center;
            font-size: 15px;
            font-weight: bold;
            color: var(--text-main);
            line-height: 1.4;
        }
        .impact-cards {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }
        .impact-card {
            background-color: var(--card-bg);
            border-radius: 10px;
            padding: 32px 16px;
            text-align: center;
            transition: all 0.2s;
            cursor: pointer;
        }
        .impact-card:hover { background-color: var(--card-hover); }
        .impact-icon-wrap {
            width: 52px; height: 52px;
            border-radius: 50%;
            background-color: #131314;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 16px;
        }
        .impact-icon-wrap .icon { width: 24px; height: 24px; }
        .impact-card.positive .impact-icon-wrap .icon { stroke: var(--positive-color); }
        .impact-card.negative .impact-icon-wrap .icon { stroke: var(--negative-color); }
        .impact-label {
            font-size: 14px;
            font-weight: bold;
            margin-bottom: 8px;
        }
        .impact-card.positive .impact-label { color: var(--positive-color); }
        .impact-card.negative .impact-label { color: var(--negative-color); }
        .impact-percent {
            font-size: 26px;
            font-weight: bold;
            letter-spacing: -0.5px;
            line-height: 1;
        }
        .impact-card.positive .impact-percent { color: var(--positive-color); }
        .impact-card.negative .impact-percent { color: var(--negative-color); }

        /* 토스트 */
        .toast {
            position: fixed;
            bottom: 30px;
            left: 50%;
            transform: translateX(-50%) translateY(100px);
            background-color: #2B3A5A;
            color: #8AB4F8;
            padding: 12px 24px;
            border-radius: 24px;
            font-size: 13px;
            font-weight: bold;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
            opacity: 0;
            transition: all 0.3s ease;
            z-index: 200;
            pointer-events: none;
            white-space: nowrap;
        }
        .toast.show {
            opacity: 1;
            transform: translateX(-50%) translateY(0);
        }

        /* 🌟 플로팅 버튼 삭제됨 */

        /* 실시간 트렌드 모달 */
        .trend-modal {
            position: fixed; top: 0; left: 0; right: 0; bottom: 0;
            background-color: var(--bg-color);
            z-index: 100; display: none;
            flex-direction: column; align-items: center;
            animation: slideUp 0.25s ease;
            overflow-y: auto;
        }
        @keyframes slideUp {
            from { transform: translateY(20px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }
        .trend-modal.open { display: flex; }
        .trend-modal-inner { width: 100%; max-width: 600px; padding: 20px; }
        .trend-modal-header {
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 16px; padding: 0 4px;
        }
        .trend-modal-title {
            display: flex; align-items: center; gap: 8px;
            font-size: 14px; font-weight: bold;
        }
        .trend-modal-title .live-dot {
            width: 6px; height: 6px;
            background-color: #22C55E;
            border-radius: 50%;
            box-shadow: 0 0 8px #22C55E;
            animation: pulse 2s infinite;
        }
        .trend-close-btn {
            background: none; border: none; color: var(--text-sub);
            cursor: pointer; padding: 5px; border-radius: 6px;
            display: flex; align-items: center; justify-content: center;
            transition: all 0.2s;
        }
        .trend-close-btn:hover { color: var(--text-main); background-color: var(--card-bg); }

        .trend-tabs {
            display: grid; grid-template-columns: 1fr 1fr;
            background-color: var(--card-bg);
            border-radius: 10px; padding: 4px; margin-bottom: 20px;
        }
        .trend-tab {
            background: none; border: none; color: var(--text-sub);
            padding: 12px 0; font-size: 14px; font-weight: bold;
            cursor: pointer; border-radius: 7px;
            transition: all 0.2s;
        }
        .trend-tab:hover { color: var(--text-main); }
        .trend-tab.active {
            background-color: #131314;
            color: var(--text-main);
            box-shadow: 0 0 0 1px #3B4A6B;
        }
        .trend-updated {
            font-size: 11px; color: var(--text-sub);
            margin-bottom: 16px; padding-left: 4px;
        }
        .trend-updated .time { color: var(--text-main); font-weight: bold; }
        .trend-list {
            display: grid; grid-template-columns: 1fr 1fr;
            gap: 14px 20px;
        }
        .trend-item { display: flex; align-items: center; gap: 10px; }
        .trend-rank { font-size: 13px; font-weight: bold; min-width: 14px; text-align: center; }
        .trend-keyword {
            font-size: 13px; font-weight: bold;
            min-width: 48px; max-width: 60px;
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        .trend-bar-wrap {
            flex: 1; height: 5px;
            background-color: var(--bar-track);
            border-radius: 3px; overflow: hidden; min-width: 40px;
        }
        .trend-bar {
            height: 100%;
            background: var(--bar-gradient);
            border-radius: 3px;
        }
        .trend-change { font-size: 10px; font-weight: bold; min-width: 26px; text-align: right; }
        .trend-change.up { color: #22C55E; }
        .trend-change.down { color: #8E918F; }
        .trend-change.same { color: var(--text-sub); }
        .trend-new-badge {
            display: inline-block; font-size: 8px; font-weight: bold;
            color: #8AB4F8; border: 1px solid #3A4A6B;
            padding: 1px 4px; border-radius: 3px;
            min-width: 26px; text-align: center;
        }

        @media (max-width: 480px) {
            .impact-card { padding: 26px 12px; }
            .impact-percent { font-size: 22px; }
            .impact-icon-wrap { width: 46px; height: 46px; }
            .impact-icon-wrap .icon { width: 20px; height: 20px; }
            .sentiment-stats { gap: 14px; padding: 14px 0; font-size: 12px; }
            .category-tab { padding: 6px 12px; font-size: 11px; }
            .carousel-arrow { width: 28px; height: 28px; }
            .carousel-arrow svg { width: 14px; height: 14px; }
        }
    </style>
</head>
<body>

<div class="app-container">
    
    <!-- 화면 1: 뉴스 목록 -->
    <div id="list-view">
        <div class="search-bar">
            <svg class="icon" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
            <input type="text" placeholder="검색어를 입력하세요">
        </div>

        <div class="realtime-header" onclick="openTrendModal()">
            <div class="realtime-title">
                <span class="live-dot"></span>
                실시간 트렌드
                <span class="realtime-count">10</span>
            </div>
            <div class="realtime-more">
                라이브
                <svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M7 17L17 7"></path><polyline points="7 7 17 7 17 17"></polyline></svg>
            </div>
        </div>

        <div class="category-tabs">
            <button class="category-tab active">속보</button>
            <button class="category-tab">증시</button>
            <button class="category-tab">종목</button>
            <button class="category-tab">경제지표</button>
            <button class="category-tab">에너지</button>
            <button class="category-tab">연준</button>
            <button class="category-tab">일정</button>
            <button class="category-tab">투자의견</button>
            <button class="category-tab">실적발표</button>
        </div>

        <!-- 주요뉴스 캐러셀 -->
        <div class="headline-section">
            <div class="section-header">
                <div>주요뉴스 <span>&gt;</span></div>
                <span id="headlineCounter" style="font-size:12px; color: var(--text-sub); font-weight: normal;">1 / 5</span>
            </div>

            <div class="headline-carousel">
                <button class="carousel-arrow" id="prevBtn" onclick="prevHeadline()" title="이전">
                    <svg viewBox="0 0 24 24"><polyline points="15 18 9 12 15 6"></polyline></svg>
                </button>

                <div class="carousel-viewport">
                    <div class="carousel-track" id="headlineTrack"></div>
                </div>

                <button class="carousel-arrow" id="nextBtn" onclick="nextHeadline()" title="다음">
                    <svg viewBox="0 0 24 24"><polyline points="9 18 15 12 9 6"></polyline></svg>
                </button>
            </div>

            <div class="carousel-dots" id="headlineDots"></div>
        </div>

        <div class="news-section">
            <div class="news-header">
                <h2>뉴스</h2>
                <div class="filters">
                    <button class="filter-btn">출처 <svg class="icon icon-sm" viewBox="0 0 24 24"><polyline points="6 9 12 15 18 9"></polyline></svg></button>
                    <button class="filter-btn">전체 · 최신순 <svg class="icon icon-sm" viewBox="0 0 24 24"><polyline points="6 9 12 15 18 9"></polyline></svg></button>
                    <button class="filter-btn"><svg class="icon icon-sm" viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg></button>
                </div>
            </div>

            <div class="news-list" id="newsList">
                <div class="news-item" onclick="openDetail(1)">
                    <div class="news-item-top"><div><span class="tag">증시</span> · 한국경제</div><div>방금 전</div></div>
                    <div class="news-item-title">미중, AI·무역 협상 진전…'미중 AI 대화' 출범 합의</div>
                    <div class="news-item-bottom"><div></div><div><svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg> 7</div></div>
                </div>
                <div class="news-item" onclick="openDetail(2)">
                    <div class="news-item-top"><div><span class="tag">에너지</span> · 한국일보</div><div>방금 전</div></div>
                    <div class="news-item-title">트럼프, 이란 대통령과 회담 가능성 열어둬… 국제 유가 급등</div>
                    <div class="news-item-bottom"><div class="ticker">$WTI</div><div><svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg> 251</div></div>
                </div>
                <div class="news-item" onclick="openDetail(3)">
                    <div class="news-item-top"><div><span class="tag">연준</span> · 매일경제</div><div>1분 전</div></div>
                    <div class="news-item-title">연준 인사들, 금리 동결 시사… 인플레 둔화 속도 주시</div>
                    <div class="news-item-bottom"><div></div><div><svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg> 4</div></div>
                </div>
                <div class="news-item" onclick="openDetail(4)">
                    <div class="news-item-top"><div><span class="tag">종목</span> · 조선비즈</div><div>3분 전</div></div>
                    <div class="news-item-title">테슬라, 신형 모델 Y 생산 일정 6개월 앞당긴다</div>
                    <div class="news-item-bottom"><div class="ticker">$TSLA</div><div><svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg> 22</div></div>
                </div>
                <div class="news-item" onclick="openDetail(5)">
                    <div class="news-item-top"><div><span class="tag">종목</span> · 이데일리</div><div>5분 전</div></div>
                    <div class="news-item-title">애플, AI 탑재 신형 아이패드 다음 달 공개 예정</div>
                    <div class="news-item-bottom"><div class="ticker">$AAPL</div><div><svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg> 112</div></div>
                </div>
                <div class="news-item hidden-news" onclick="openDetail(6)"><div class="news-item-top"><div><span class="tag">종목</span> · 머니투데이</div><div>10분 전</div></div><div class="news-item-title">엔비디아, 차세대 GPU 블랙웰 울트라 발표 임박</div><div class="news-item-bottom"><div class="ticker">$NVDA</div><div><svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg> 89</div></div></div>
                <div class="news-item hidden-news" onclick="openDetail(7)"><div class="news-item-top"><div><span class="tag">에너지</span> · 서울경제</div><div>15분 전</div></div><div class="news-item-title">국제 유가 3% 급락… 중동 긴장 완화 기대감</div><div class="news-item-bottom"><div class="ticker">$WTI</div><div><svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg> 45</div></div></div>
                <div class="news-item hidden-news" onclick="openDetail(8)"><div class="news-item-top"><div><span class="tag">연준</span> · 헤럴드경제</div><div>20분 전</div></div><div class="news-item-title">일본은행, 예상대로 금리 동결… 엔화 약세 지속</div><div class="news-item-bottom"><div class="ticker">$JPY</div><div><svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg> 302</div></div></div>
                <div class="news-item hidden-news" onclick="openDetail(9)"><div class="news-item-top"><div><span class="tag">증시</span> · 파이낸셜뉴스</div><div>30분 전</div></div><div class="news-item-title">나스닥 사상 최고치 경신… 기술주 랠리 이어져</div><div class="news-item-bottom"><div class="ticker">$QQQ</div><div><svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg> 18</div></div></div>
                <div class="news-item hidden-news" onclick="openDetail(10)"><div class="news-item-top"><div><span class="tag">투자의견</span> · 연합뉴스</div><div>1시간 전</div></div><div class="news-item-title">비트코인 10만 달러 돌파… 기관 자금 유입 가속</div><div class="news-item-bottom"><div class="ticker">$BTC</div><div><svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg> 520</div></div></div>
            </div>

            <button class="load-more-btn" id="loadMoreBtn">더보기</button>
        </div>
    </div>

    <!-- 화면 2: 뉴스 상세 -->
    <div id="detail-view">
        <div class="detail-top-bar">
            <div class="left-actions">
                <button class="icon-btn" onclick="closeDetail()" title="뒤로가기">
                    <svg class="icon icon-lg" viewBox="0 0 24 24"><line x1="19" y1="12" x2="5" y2="12"></line><polyline points="12 19 5 12 12 5"></polyline></svg>
                </button>
            </div>
            <div class="right-actions">
                <button class="icon-btn" title="알림">
                    <svg class="icon" viewBox="0 0 24 24"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 0 1-3.46 0"></path></svg>
                </button>
                <button class="icon-btn" title="저장">
                    <svg class="icon" viewBox="0 0 24 24"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path></svg>
                </button>
                <button class="icon-btn" title="공유">
                    <svg class="icon" viewBox="0 0 24 24"><path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"></path><polyline points="16 6 12 2 8 6"></polyline><line x1="12" y1="2" x2="12" y2="15"></line></svg>
                </button>
                <button class="icon-btn" title="다음 기사">
                    <svg class="icon" viewBox="0 0 24 24"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
                </button>
            </div>
        </div>

        <!-- 🌟 뉴스 요약 카드 (출처가 제목 아래로) -->
        <div class="news-preview-card">
            <div class="preview-top">
                <span class="preview-tag" id="detail-tag">증시</span>
                <span class="preview-time" id="detail-time">방금 전</span>
            </div>
            <div class="preview-title" id="detail-title">뉴스 제목이 들어갈 자리입니다.</div>
            <div class="preview-source" id="detail-source">한국경제</div>
            <div class="preview-bottom">
                <span class="preview-views">
                    <svg class="icon icon-sm" viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                    <span id="detail-views">251</span>
                </span>
            </div>
        </div>

        <div class="info-section">
            <div class="info-section-title">관련 이슈</div>
            <div class="info-chip-row" id="detail-related-issues"></div>
        </div>

        <div class="info-section">
            <div class="info-section-title">관련 종목</div>
            <div class="stock-list-rows" id="detail-related-stocks"></div>
        </div>

        <div class="info-section">
            <div class="info-section-title">관련 산업·테마</div>
            <div class="info-chip-row" id="detail-related-industries"></div>
        </div>

        <div class="sentiment-stats">
            <div class="stat-item like">
                <svg class="icon" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
                </svg>
                <span id="stat-like">6</span>
            </div>
            <div class="stat-item up">
                <svg class="icon" viewBox="0 0 24 24"><polyline points="18 15 12 9 6 15"></polyline></svg>
                <span id="stat-up">54</span>
            </div>
            <div class="stat-item dislike">
                <svg class="icon" viewBox="0 0 24 24"><polyline points="6 9 12 15 18 9"></polyline></svg>
                <span id="stat-down">160</span>
            </div>
            <div class="stat-views">
                <span>조회</span>
                <span id="stat-views">4,687</span>
                <svg class="icon icon-sm" viewBox="0 0 24 24" style="stroke: var(--text-sub);">
                    <line x1="5" y1="12" x2="19" y2="12"></line>
                    <polyline points="12 5 19 12 12 19"></polyline>
                </svg>
            </div>
        </div>

        <div class="impact-section">
            <div class="impact-title-box">
                이 뉴스가 해당 종목에 미치는 영향은?
            </div>
            <div class="impact-cards">
                <div class="impact-card positive">
                    <div class="impact-icon-wrap">
                        <svg class="icon" viewBox="0 0 24 24"><line x1="7" y1="17" x2="17" y2="7"></line><polyline points="7 7 17 7 17 17"></polyline></svg>
                    </div>
                    <div class="impact-label">긍정적</div>
                    <div class="impact-percent" id="impact-positive">25%</div>
                </div>
                <div class="impact-card negative">
                    <div class="impact-icon-wrap">
                        <svg class="icon" viewBox="0 0 24 24"><line x1="7" y1="7" x2="17" y2="17"></line><polyline points="17 7 17 17 7 17"></polyline></svg>
                    </div>
                    <div class="impact-label">부정적</div>
                    <div class="impact-percent" id="impact-negative">75%</div>
                </div>
            </div>
        </div>
        <!-- 🌟 플로팅 화살표 버튼 삭제됨 -->
    </div>

</div>

<div class="toast" id="toast">관심종목에 추가되었습니다</div>

<!-- 실시간 트렌드 모달 -->
<div class="trend-modal" id="trendModal">
    <div class="trend-modal-inner">
        <div class="trend-modal-header">
            <div class="trend-modal-title">
                <span class="live-dot"></span>
                실시간 트렌드
            </div>
            <button class="trend-close-btn" onclick="closeTrendModal()">
                <svg class="icon" viewBox="0 0 24 24"><polyline points="18 15 12 9 6 15"></polyline></svg>
            </button>
        </div>

        <div class="trend-tabs">
            <button class="trend-tab active" data-tab="realtime">실시간</button>
            <button class="trend-tab" data-tab="today">오늘</button>
        </div>

        <div class="trend-updated">
            마지막 갱신 <span class="time" id="trendTime">04:21 KST</span>
        </div>

        <div class="trend-list" id="trendList"></div>
    </div>
</div>

<script>
    const FAV_KEY = 'news_app_favorites';
    
    function getFavorites() {
        try { return JSON.parse(localStorage.getItem(FAV_KEY)) || []; }
        catch (e) { return []; }
    }
    function saveFavorites(favs) {
        localStorage.setItem(FAV_KEY, JSON.stringify(favs));
    }
    function isFavorite(ticker) {
        return getFavorites().includes(ticker);
    }
    function toggleFavorite(ticker) {
        let favs = getFavorites();
        if (favs.includes(ticker)) {
            favs = favs.filter(t => t !== ticker);
            showToast(\`\${ticker} 관심종목에서 제거\`);
        } else {
            favs.push(ticker);
            showToast(\`⭐ \${ticker} 관심종목에 추가\`);
        }
        saveFavorites(favs);
        renderRelatedStocks();
    }

    let toastTimer;
    function showToast(msg) {
        const toast = document.getElementById('toast');
        toast.textContent = msg;
        toast.classList.add('show');
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => toast.classList.remove('show'), 1800);
    }

    /* 주요뉴스 캐러셀 */
    const headlineData = [
        { id: 1,  tag: '증시', time: '11:19', views: '23K',   source: '한국경제', title: '미중, AI·무역 협상 진전…\\'미중 AI 대화\\' 출범 합의' },
        { id: 2,  tag: '에너지', time: '22:41', views: '47.4K', source: '한국일보', title: '트럼프, 이란 대통령과 회담 가능성 열어둬' },
        { id: 3,  tag: '연준', time: '21:15', views: '18.2K', source: '매일경제', title: '연준 인사들, 금리 동결 시사… 인플레 둔화 속도 주시' },
        { id: 4,  tag: '종목', time: '20:48', views: '32.1K', source: '조선비즈', title: '테슬라, 신형 모델 Y 생산 일정 6개월 앞당긴다' },
        { id: 5,  tag: '종목', time: '19:22', views: '12.5K', source: '이데일리', title: '애플, AI 탑재 신형 아이패드 다음 달 공개 예정' },
        { id: 6,  tag: '종목', time: '18:05', views: '8.9K',  source: '머니투데이', title: '엔비디아, 차세대 GPU 블랙웰 울트라 발표 임박' },
        { id: 7,  tag: '에너지', time: '17:33', views: '5.4K', source: '서울경제', title: '국제 유가 3% 급락… 중동 긴장 완화 기대감' },
        { id: 8,  tag: '연준', time: '16:11', views: '4.2K',  source: '헤럴드경제', title: '일본은행, 예상대로 금리 동결… 엔화 약세 지속' },
        { id: 9,  tag: '증시', time: '15:42', views: '9.8K',  source: '파이낸셜뉴스', title: '나스닥 사상 최고치 경신… 기술주 랠리 이어져' },
        { id: 10, tag: '투자의견', time: '14:18', views: '15.3K', source: '연합뉴스', title: '비트코인 10만 달러 돌파… 기관 자금 유입 가속' }
    ];

    const CARDS_PER_PAGE = 2;
    const TOTAL_PAGES = Math.ceil(headlineData.length / CARDS_PER_PAGE);
    let currentPage = 0;

    function renderHeadlineCarousel() {
        const start = currentPage * CARDS_PER_PAGE;
        const pageItems = headlineData.slice(start, start + CARDS_PER_PAGE);
        const track = document.getElementById('headlineTrack');
        const dotsBox = document.getElementById('headlineDots');
        const counter = document.getElementById('headlineCounter');
        const prevBtn = document.getElementById('prevBtn');
        const nextBtn = document.getElementById('nextBtn');

        track.innerHTML = pageItems.map((item, i) => \`
            <div class="headline-card \${i % 2 === 1 ? 'blue-tint' : ''}" onclick="openDetail(\${item.id})">
                <div>
                    <div class="card-top">
                        <div><span class="tag">\${item.tag}</span></div>
                        <div>\${item.time}</div>
                    </div>
                    <div class="headline-title">\${item.title}</div>
                </div>
                <div class="card-bottom">
                    <svg class="icon icon-sm" viewBox="0 0 24 24">
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                        <circle cx="12" cy="12" r="3"></circle>
                    </svg>
                    \${item.views}
                </div>
            </div>
        \`).join('');

        track.style.animation = 'none';
        void track.offsetWidth;
        track.style.animation = 'slideFade 0.35s ease';

        dotsBox.innerHTML = Array.from({ length: TOTAL_PAGES }, (_, i) => 
            \`<div class="carousel-dot \${i === currentPage ? 'active' : ''}" onclick="goToPage(\${i})"></div>\`
        ).join('');

        counter.textContent = \`\${currentPage + 1} / \${TOTAL_PAGES}\`;
        prevBtn.disabled = currentPage === 0;
        nextBtn.disabled = currentPage === TOTAL_PAGES - 1;
    }

    function prevHeadline() {
        if (currentPage > 0) { currentPage--; renderHeadlineCarousel(); }
    }
    function nextHeadline() {
        if (currentPage < TOTAL_PAGES - 1) { currentPage++; renderHeadlineCarousel(); }
    }
    function goToPage(page) {
        currentPage = page;
        renderHeadlineCarousel();
    }

    /* 트렌드 */
    const trendData = {
        realtime: [
            { rank: 1, name: '국제', value: 92, change: 'up', delta: 1 },
            { rank: 2, name: '구글', value: 78, change: 'down', delta: 1 },
            { rank: 3, name: '메타', value: 68, change: 'new' },
            { rank: 4, name: '반도체', value: 58, change: 'down', delta: 1 },
            { rank: 5, name: '전쟁', value: 48, change: 'up', delta: 1 },
            { rank: 6, name: '전쟁이', value: 38, change: 'new' },
            { rank: 7, name: '금리', value: 32, change: 'up', delta: 2 },
            { rank: 8, name: '엔비디아', value: 28, change: 'down', delta: 1 },
            { rank: 9, name: '환율', value: 22, change: 'same' },
            { rank: 10, name: 'AI', value: 18, change: 'up', delta: 3 }
        ],
        today: [
            { rank: 1, name: '연준', value: 95, change: 'up', delta: 2 },
            { rank: 2, name: 'CPI', value: 88, change: 'new' },
            { rank: 3, name: '테슬라', value: 76, change: 'up', delta: 1 },
            { rank: 4, name: '실적', value: 65, change: 'down', delta: 2 },
            { rank: 5, name: '애플', value: 52, change: 'up', delta: 1 },
            { rank: 6, name: '금값', value: 45, change: 'new' },
            { rank: 7, name: '원유', value: 38, change: 'down', delta: 3 },
            { rank: 8, name: '나스닥', value: 30, change: 'up', delta: 1 },
            { rank: 9, name: '비트코인', value: 24, change: 'down', delta: 1 },
            { rank: 10, name: '국채', value: 16, change: 'same' }
        ]
    };

    let currentTrendTab = 'realtime';

    function renderTrendList() {
        const list = document.getElementById('trendList');
        const data = trendData[currentTrendTab];

        list.innerHTML = data.map(item => {
            let changeHTML = '';
            if (item.change === 'up') changeHTML = \`<span class="trend-change up">▲\${item.delta}</span>\`;
            else if (item.change === 'down') changeHTML = \`<span class="trend-change down">▼\${item.delta}</span>\`;
            else if (item.change === 'new') changeHTML = \`<span class="trend-new-badge">NEW</span>\`;
            else changeHTML = \`<span class="trend-change same">-</span>\`;

            return \`
                <div class="trend-item">
                    <span class="trend-rank">\${item.rank}</span>
                    <span class="trend-keyword">\${item.name}</span>
                    <div class="trend-bar-wrap"><div class="trend-bar" style="width: \${item.value}%"></div></div>
                    \${changeHTML}
                </div>
            \`;
        }).join('');

        const now = new Date();
        document.getElementById('trendTime').innerText = 
            \`\${String(now.getHours()).padStart(2,'0')}:\${String(now.getMinutes()).padStart(2,'0')} KST\`;
    }

    function openTrendModal() {
        document.getElementById('trendModal').classList.add('open');
        document.body.style.overflow = 'hidden';
        renderTrendList();
    }
    function closeTrendModal() {
        document.getElementById('trendModal').classList.remove('open');
        document.body.style.overflow = '';
    }

    document.querySelectorAll('.trend-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.trend-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            currentTrendTab = tab.dataset.tab;
            renderTrendList();
        });
    });

    let currentRelatedStocks = [];

    document.addEventListener('DOMContentLoaded', () => {
        const loadMoreBtn = document.getElementById('loadMoreBtn');
        const hiddenItems = document.querySelectorAll('.hidden-news');

        loadMoreBtn.addEventListener('click', () => {
            hiddenItems.forEach(item => item.style.display = 'block');
            loadMoreBtn.style.display = 'none';
        });

        document.querySelectorAll('.category-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.category-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
            });
        });

        renderHeadlineCarousel();
    });

    function openDetail(newsId) {
        const d = getMockData(newsId);
        
        document.getElementById('detail-tag').innerText = d.tag;
        document.getElementById('detail-time').innerText = d.time;
        document.getElementById('detail-title').innerText = d.title;
        document.getElementById('detail-source').innerText = d.source;
        document.getElementById('detail-views').innerText = d.views;

        document.getElementById('detail-related-issues').innerHTML = 
            d.relatedIssues.map(i => \`<span class="info-chip">\${i}</span>\`).join('');

        currentRelatedStocks = d.relatedStocks;
        renderRelatedStocks();

        document.getElementById('detail-related-industries').innerHTML = 
            d.relatedIndustries.map(i => \`<span class="info-chip">\${i}</span>\`).join('');

        document.getElementById('stat-like').innerText = d.stats.like;
        document.getElementById('stat-up').innerText = d.stats.up;
        document.getElementById('stat-down').innerText = d.stats.down;
        document.getElementById('stat-views').innerText = d.stats.views;
        document.getElementById('impact-positive').innerText = d.impact.positive + '%';
        document.getElementById('impact-negative').innerText = d.impact.negative + '%';

        document.getElementById('list-view').style.display = 'none';
        document.getElementById('detail-view').style.display = 'flex';
        window.scrollTo(0, 0);
    }

    function renderRelatedStocks() {
        const box = document.getElementById('detail-related-stocks');
        
        if (!currentRelatedStocks.length) {
            box.innerHTML = \`<div class="stock-row-item"><div class="stock-row-left"><span class="stock-row-ticker">-</span></div></div>\`;
            return;
        }

        box.innerHTML = currentRelatedStocks.map(stock => {
            const fav = isFavorite(stock);
            return \`
                <div class="stock-row-item">
                    <div class="stock-row-left">
                        <span class="stock-row-ticker">\${stock}</span>
                    </div>
                    <button class="fav-btn \${fav ? 'favorited' : ''}" 
                            onclick="toggleFavorite('\${stock}')" 
                            aria-label="관심등록">
                        <svg viewBox="0 0 24 24">
                            <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
                        </svg>
                    </button>
                </div>
            \`;
        }).join('');
    }

    function closeDetail() {
        document.getElementById('detail-view').style.display = 'none';
        document.getElementById('list-view').style.display = 'block';
        window.scrollTo(0, 0);
    }

    function getMockData(id) {
        const newsData = {
            1: { 
                tag: "증시", time: "11:19", 
                title: "미중, AI·무역 협상 진전…'미중 AI 대화' 출범 합의", 
                source: "한국경제", views: "23K",
                relatedIssues: ["#미중정상회담", "#AI협력"], 
                relatedStocks: ["$SPY", "$QQQ"], 
                relatedIndustries: ["AI·데이터", "반도체"], 
                stats: { like: 18, up: 98, down: 32, views: "23,142" }, 
                impact: { positive: 82, negative: 18 } 
            },
            2: { 
                tag: "에너지", time: "22:41", 
                title: "트럼프, 이란 대통령과 회담 가능성 열어둬", 
                source: "한국일보", views: "47.4K",
                relatedIssues: ["#중동정세", "#지정학적리스크"], 
                relatedStocks: ["$WTI", "$XOM"], 
                relatedIndustries: ["에너지", "정유"], 
                stats: { like: 24, up: 142, down: 210, views: "47,392" }, 
                impact: { positive: 35, negative: 65 } 
            },
            3: { 
                tag: "연준", time: "21:15", 
                title: "연준 인사들, 금리 동결 시사… 인플레 둔화 속도 주시", 
                source: "매일경제", views: "18.2K",
                relatedIssues: ["#연준", "#금리동결", "#인플레이션"], 
                relatedStocks: ["$TLT", "$SPY"], 
                relatedIndustries: ["금융", "채권"], 
                stats: { like: 12, up: 68, down: 92, views: "18,215" }, 
                impact: { positive: 42, negative: 58 } 
            },
            4: { 
                tag: "종목", time: "20:48", 
                title: "테슬라, 신형 모델 Y 생산 일정 6개월 앞당긴다", 
                source: "조선비즈", views: "32.1K",
                relatedIssues: ["#테슬라", "#전기차", "#생산확대"], 
                relatedStocks: ["$TSLA", "$RIVN"], 
                relatedIndustries: ["자동차", "2차전지"], 
                stats: { like: 42, up: 182, down: 44, views: "32,108" }, 
                impact: { positive: 86, negative: 14 } 
            },
            5: { 
                tag: "종목", time: "19:22", 
                title: "애플, AI 탑재 신형 아이패드 다음 달 공개 예정", 
                source: "이데일리", views: "12.5K",
                relatedIssues: ["#애플", "#AI", "#아이패드"], 
                relatedStocks: ["$AAPL", "$TSM"], 
                relatedIndustries: ["소프트웨어", "AI·데이터"], 
                stats: { like: 28, up: 128, down: 26, views: "12,543" }, 
                impact: { positive: 88, negative: 12 } 
            },
            6: { 
                tag: "종목", time: "18:05", 
                title: "엔비디아, 차세대 GPU 블랙웰 울트라 발표 임박", 
                source: "머니투데이", views: "8.9K",
                relatedIssues: ["#엔비디아", "#GPU", "#AI반도체"], 
                relatedStocks: ["$NVDA", "$AMD", "$TSM"], 
                relatedIndustries: ["반도체", "AI·데이터"], 
                stats: { like: 34, up: 156, down: 22, views: "8,932" }, 
                impact: { positive: 92, negative: 8 } 
            },
            7: { 
                tag: "에너지", time: "17:33", 
                title: "국제 유가 3% 급락… 중동 긴장 완화 기대감", 
                source: "서울경제", views: "5.4K",
                relatedIssues: ["#국제유가", "#중동정세"], 
                relatedStocks: ["$WTI", "$CVX"], 
                relatedIndustries: ["에너지", "정유"], 
                stats: { like: 8, up: 46, down: 68, views: "5,421" }, 
                impact: { positive: 55, negative: 45 } 
            },
            8: { 
                tag: "연준", time: "16:11", 
                title: "일본은행, 예상대로 금리 동결… 엔화 약세 지속", 
                source: "헤럴드경제", views: "4.2K",
                relatedIssues: ["#일본은행", "#엔화", "#금리"], 
                relatedStocks: ["$JPY", "$FXY"], 
                relatedIndustries: ["금융", "환율"], 
                stats: { like: 5, up: 28, down: 42, views: "4,218" }, 
                impact: { positive: 48, negative: 52 } 
            },
            9: { 
                tag: "증시", time: "15:42", 
                title: "나스닥 사상 최고치 경신… 기술주 랠리 이어져", 
                source: "파이낸셜뉴스", views: "9.8K",
                relatedIssues: ["#나스닥", "#기술주", "#사상최고"], 
                relatedStocks: ["$QQQ", "$NVDA"], 
                relatedIndustries: ["반도체", "소프트웨어"], 
                stats: { like: 26, up: 118, down: 32, views: "9,821" }, 
                impact: { positive: 78, negative: 22 } 
            },
            10: { 
                tag: "투자의견", time: "14:18", 
                title: "비트코인 10만 달러 돌파… 기관 자금 유입 가속", 
                source: "연합뉴스", views: "15.3K",
                relatedIssues: ["#비트코인", "#가상자산", "#기관투자"], 
                relatedStocks: ["$COIN", "$MSTR"], 
                relatedIndustries: ["가상자산", "핀테크"], 
                stats: { like: 52, up: 198, down: 38, views: "15,342" }, 
                impact: { positive: 84, negative: 16 } 
            }
        };
        return newsData[id] || newsData[1];
    }
</script>

</body>
</html>`;

  function renderNewsWidget(root){
    root.innerHTML = `<div class="news-widget-shell"><iframe class="news-widget-frame" title="뉴스" loading="eager"></iframe></div>`;
    const frame = root.querySelector('.news-widget-frame');
    frame.srcdoc = NEWS_HTML;
  }

  window.NewsWidget={render:renderNewsWidget};
})();
