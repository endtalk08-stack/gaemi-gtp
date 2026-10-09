// gaemiGTP - 백엔드 분석 요청 전용
    window.GaemiGTPAnalysisAPI = window.GaemiGTPAnalysisAPI || {};

window.GaemiGTPAnalysisAPI.fetchAnalysisFromBackend = async function(stockName, signal) {
      try {
        const response = await fetch(`${BACKEND_URL}/analyze?stock=${encodeURIComponent(stockName)}`, { signal });
        if (!response.ok) throw new Error('서버 에러');
        const data = await response.json();
        // 기존 뉴스/공시 수집 로직은 그대로 두고, 서버가 내려주는
        // 구조화 데이터만 프론트까지 전달한다. (표시용 변경만)
        return {
          sections: data.sections || [],
          paired_news_items: Array.isArray(data.paired_news_items) ? data.paired_news_items : [],
          storyboard_news_items: Array.isArray(data.storyboard_news_items) ? data.storyboard_news_items : [],
          issue_briefs: Array.isArray(data.issue_briefs) ? data.issue_briefs : [],
          news_test_articles: Array.isArray(data.news_test_articles) ? data.news_test_articles : [],
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
