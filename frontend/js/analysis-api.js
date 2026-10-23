// gaemiGTP - 백엔드 분석 요청 전용
    window.GaemiGTPAnalysisAPI = window.GaemiGTPAnalysisAPI || {};

window.GaemiGTPAnalysisAPI.fetchAnalysisFromBackend = async function(stockName, signal, marketSelection = null) {
      try {
        const params = new URLSearchParams({ stock: stockName });
        // One read-only switch shared by the sidebar and central news display.
        // Both stored result channels remain available regardless of selection.
        const selectedMode = (() => {
          try { return localStorage.getItem('gaemiGTP_issue_mode_us_v1') || 'auto'; }
          catch (_) { return 'auto'; }
        })();
        params.set('issue_mode', ['auto', 'ai', 'code', 'both'].includes(selectedMode) ? selectedMode : 'auto');
        if (marketSelection?.market && marketSelection?.menu && marketSelection?.symbol) {
          params.set('market', marketSelection.market);
          params.set('menu', marketSelection.menu);
          params.set('symbol', marketSelection.symbol);
        }
        const response = await fetch(`${BACKEND_URL}/analyze?${params}`, { signal });
        if (!response.ok) throw new Error('서버 에러');
        const data = await response.json();
        // 기존 뉴스/공시 수집 로직은 그대로 두고, 서버가 내려주는
        // 구조화 데이터만 프론트까지 전달한다. (표시용 변경만)
        return {
          sections: data.sections || [],
          price_snapshot: data.price_snapshot && typeof data.price_snapshot === 'object' ? data.price_snapshot : null,
          paired_news_items: Array.isArray(data.paired_news_items) ? data.paired_news_items : [],
          storyboard_news_items: Array.isArray(data.storyboard_news_items) ? data.storyboard_news_items : [],
          issue_briefs: Array.isArray(data.issue_briefs) ? data.issue_briefs : [],
          issue_channels: {
            code: Array.isArray(data.issue_channels?.code) ? data.issue_channels.code : [],
            ai: Array.isArray(data.issue_channels?.ai) ? data.issue_channels.ai : []
          },
          issue_mode: String(data.issue_mode || 'auto'),
          issue_display_channel: String(data.issue_display_channel || 'unavailable'),
          price_reason: data.price_reason && typeof data.price_reason === 'object' ? data.price_reason : null,
          keyword_storyboard: Array.isArray(data.keyword_storyboard) ? data.keyword_storyboard : [],
          disclosures: Array.isArray(data.disclosures) ? data.disclosures : [],
          us_filings: Array.isArray(data.us_filings) ? data.us_filings : [],
          ok: data.ok !== false
        };
      } catch (err) {
        if (err?.name === 'AbortError') return { sections: [], ok: false, aborted: true };
        return { sections: [], ok: false };
      }
    };
