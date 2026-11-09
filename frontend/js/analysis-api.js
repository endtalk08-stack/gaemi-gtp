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
        // Keep all other analysis sections unchanged, but let opted-in US
        // R2 news render even if the legacy Neon-dependent endpoint fails.
        const backendTask = (async () => {
          try {
            const response = await fetch(`${BACKEND_URL}/analyze?${params}`, { signal });
            if (!response.ok) throw new Error('서버 에러');
            return { data: await response.json(), succeeded: true };
          } catch (error) {
            if (error?.name === 'AbortError') throw error;
            return { data: {}, succeeded: false };
          }
        })();
        // 기존 뉴스/공시 수집 로직은 그대로 두고, 서버가 내려주는
        // 구조화 데이터만 프론트까지 전달한다. (표시용 변경만)
        // Optional R2-first news transport for US TOP20 only. The normal
        // /analyze response and the KR news panel remain unchanged.
        // Activate only after the Pages NEWS_R2 binding and routes are verified.
        let r2Base = String(window.ENV?.NEWS_STOCKS_R2_BASE_URL || '').trim();
        while (r2Base.endsWith('/')) r2Base = r2Base.slice(0, -1);
        const usSymbol = String(marketSelection?.symbol || '').trim().toUpperCase();
        const r2Task = (async () => {
          if (!(marketSelection?.market === 'us' && /^[A-Z][A-Z0-9.-]{0,14}$/.test(usSymbol)
              && ((r2Base.startsWith('/') && !r2Base.startsWith('//'))
                  || r2Base.startsWith('https://')))) return null;
          try {
            const response = await fetch(
              r2Base + '/news/stocks/us/' + encodeURIComponent(usSymbol),
              { signal, cache: 'no-cache' }
            );
            if (!response.ok) return null;
            const published = await response.json();
            if (published?.ok !== true || published.symbol !== usSymbol
                || !Array.isArray(published.items)) return null;
            const items = published.items.filter(item =>
              item && typeof item.title === 'string' && item.title.trim()
              && typeof item.url === 'string'
              && (item.url.startsWith('https://') || item.url.startsWith('http://'))
            );
            return items.length ? items : null;
          } catch (error) {
            if (error?.name === 'AbortError') throw error;
            return null;
          }
        })();
        const [{ data, succeeded }, r2PanelNews] = await Promise.all([backendTask, r2Task]);
        if (!succeeded && !r2PanelNews) return { sections: [], ok: false };
        return {
          sections: data.sections || [],
          paired_news_items: Array.isArray(data.paired_news_items) ? data.paired_news_items : [],
          ...(r2PanelNews?.length ? { panel_news_items: r2PanelNews } : {}),
          storyboard_news_items: Array.isArray(data.storyboard_news_items) ? data.storyboard_news_items : [],
          issue_briefs: Array.isArray(data.issue_briefs) ? data.issue_briefs : [],
          keyword_storyboard: Array.isArray(data.keyword_storyboard) ? data.keyword_storyboard : [],
          disclosures: Array.isArray(data.disclosures) ? data.disclosures : [],
          us_filings: Array.isArray(data.us_filings) ? data.us_filings : [],
          ok: (succeeded && data.ok !== false) || !!r2PanelNews
        };
      } catch (err) {
        if (err?.name === 'AbortError') return { sections: [], ok: false, aborted: true };
        return { sections: [], ok: false };
      }
    };
