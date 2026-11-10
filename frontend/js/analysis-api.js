// gaemiGTP - 백엔드 분석 요청 전용
    window.GaemiGTPAnalysisAPI = window.GaemiGTPAnalysisAPI || {};

window.GaemiGTPAnalysisAPI.fetchAnalysisFromBackend = async function(stockName, signal, marketSelection = null) {
      try {
        const params = new URLSearchParams({ stock: stockName });
        if (marketSelection?.market && marketSelection?.menu && marketSelection?.symbol) {
          params.set('market', marketSelection.market);
          params.set('menu', marketSelection.menu);
          params.set('symbol', marketSelection.symbol);
        }
        const endpoint = window.location.hostname === 'gaemigtp-main.pages.dev'
          ? window.location.origin : BACKEND_URL;
        const response = await fetch(`${endpoint}/analyze?${params}`, {
          signal, credentials: endpoint === window.location.origin ? 'same-origin' : 'omit',
          cache: 'no-store'
        });
        if (response.status === 401) return { sections: [], ok: false, error: 'private_access_required' };
        if (!response.ok) return { sections: [], ok: false, error: 'analysis_http_' + response.status };
        const data = await response.json();
        // 기존 뉴스/공시 수집 로직은 그대로 두고, 서버가 내려주는
        // 구조화 데이터만 프론트까지 전달한다. (표시용 변경만)
        return {
          sections: data.sections || [],
          price_snapshot: data.price_snapshot && typeof data.price_snapshot === 'object' ? data.price_snapshot : null,
          paired_news_items: Array.isArray(data.paired_news_items) ? data.paired_news_items : [],
          storyboard_news_items: Array.isArray(data.storyboard_news_items) ? data.storyboard_news_items : [],
          issue_briefs: Array.isArray(data.issue_briefs) ? data.issue_briefs : [],
          price_reason: data.price_reason && typeof data.price_reason === 'object' ? data.price_reason : null,
          keyword_storyboard: Array.isArray(data.keyword_storyboard) ? data.keyword_storyboard : [],
          disclosures: Array.isArray(data.disclosures) ? data.disclosures : [],
          us_filings: Array.isArray(data.us_filings) ? data.us_filings : [],
          ok: data.ok !== false,
          error: data.error || null
        };
      } catch (err) {
        if (err?.name === 'AbortError') return { sections: [], ok: false, aborted: true };
        return { sections: [], ok: false, error: 'analysis_request_failed' };
      }
    };
