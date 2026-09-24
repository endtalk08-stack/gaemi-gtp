# 목표 파일 구조

```text
gaemiGTP/
├── app.py
├── frontend/
│   ├── shell/
│   │   ├── left-nav-rail/
│   │   ├── left-market-sidebar/
│   │   ├── left-context-sidebar/
│   │   ├── left-plugin-sidebar/
│   │   ├── main/
│   │   │   └── widget-dock/
│   │   └── right-panel/
│   ├── pages/
│   │   ├── home/
│   │   ├── stock-analysis/
│   │   ├── market/
│   │   ├── watchlist/
│   │   │   ├── watchlist.js
│   │   │   └── README.md
│   │   ├── dashboard/
│   │   ├── auto-trade/
│   │   └── custom-analysis/
│   ├── widgets/
│   │   ├── why-up/
│   │   ├── materials/
│   │   ├── price/
│   │   ├── volume/
│   │   ├── trading-value/
│   │   ├── news/
│   │   ├── event/
│   │   ├── chart/
│   │   ├── ranking/
│   │   ├── economic/
│   │   ├── earnings/
│   │   └── market-state/
│   ├── user/
│   └── admin/
│
└── backend/
    ├── data/
    ├── core/
    ├── analysis/
    ├── api/
    ├── backtest/
    ├── user/
    ├── admin/
    ├── database/
    ├── cache/
    └── utils/
```

이 구조는 큰 영역의 자리만 먼저 확정하는 목표 구조다.
실제 코드는 기능별로 검증하면서 하나씩 이동/연결한다.
