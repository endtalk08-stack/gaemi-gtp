// 시각화 태그 및 목표가/손절가 바 생성 함수
function renderVisualizer(currentPrice, targetPrice, stopLossPrice, statusText = "관망") {
    // 현재가의 위치 비율 계산 (손절가~목표가 기준)
    let percentage = 50;
    if (targetPrice > stopLossPrice) {
        percentage = ((currentPrice - stopLossPrice) / (targetPrice - stopLossPrice)) * 100;
        percentage = Math.max(5, Math.min(95, percentage)); // 범위 제한
    }

    // 상태에 따른 태그 색상 설정
    let badgeClass = "badge-hold";
    if (statusText.includes("매수") || statusText.includes("긍정")) badgeClass = "badge-buy";
    if (statusText.includes("손절") || statusText.includes("위험")) badgeClass = "badge-danger";

    return `
        <!-- 1. 상태 태그 -->
        <div class="tag-container">
            <span class="badge ${badgeClass}">● ${statusText}</span>
            <span class="badge badge-info">목표 수익률 +${(((targetPrice - currentPrice) / currentPrice) * 100).toFixed(1)}%</span>
        </div>

        <!-- 2. 목표가 / 손절가 시각화 바 -->
        <div class="price-visualizer">
            <div style="font-weight: bold; font-size: 0.95rem; color: #374151;">🎯 주가 구간 분석</div>
            <div class="price-range-bar">
                <div class="price-progress" style="width: ${percentage}%;"></div>
                <div class="price-marker" style="left: ${percentage}%;">
                    <span class="marker-label">현재가 ${currentPrice.toLocaleString()}원</span>
                    <div class="marker-pin"></div>
                </div>
            </div>
            <div class="price-labels">
                <span style="color: #ef4444;">손절가 ${stopLossPrice.toLocaleString()}원</span>
                <span style="color: #10b981;">목표가 ${targetPrice.toLocaleString()}원</span>
            </div>
        </div>
    `;
}
