// Frontend is served by GitHub Pages; analysis API runs on Render.
const BACKEND_URL = 'https://gaemi-gtp.onrender.com';
    let activeAnalysisController = null;
    let activeStock = '삼성전자';
    let activeAnalysisRequestId = 0;
    let currentChartInstance = null;
    let currentAppMode = 'gaemi';
    let workspaceUIReady = false;