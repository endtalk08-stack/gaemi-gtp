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
          news_items: Array.isArray(data.news_items) ? data.news_items : [],
          disclosures: Array.isArray(data.disclosures) ? data.disclosures : [],
          us_filings: Array.isArray(data.us_filings) ? data.us_filings : [],
          ok: true
        };
      } catch (err) {
        if (err?.name === 'AbortError') return { sections: [], ok: false, aborted: true };
        return { sections: [], ok: false };
      }
    };
