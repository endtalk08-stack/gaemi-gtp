/* Analysis Data Store
   The API response is kept separate from chat and widget presentation.
   Stable section ids are the contract between backend and every renderer. */
(function () {
  'use strict';

  const SECTION_IDS_BY_LEGACY_TITLE = [
    ['오늘은 왜', 'why-up'],
    ['큰손들은', 'supply'],
    ['여기 깨지면', 'levels'],
    ['오늘 밤, 이번주', 'calendar'],
  ];

  let snapshot = {
    stockName: '',
    sections: {},
    newsItems: [],
    disclosures: [],
    usFilings: [],
  };

  function sectionId(section) {
    if (typeof section?.id === 'string' && section.id) return section.id;
    const title = String(section?.title || '');
    const found = SECTION_IDS_BY_LEGACY_TITLE.find(([prefix]) => title.includes(prefix));
    return found ? found[1] : null;
  }

  function set(stockName, result) {
    const sections = {};
    (Array.isArray(result?.sections) ? result.sections : []).forEach(section => {
      const id = sectionId(section);
      if (id) sections[id] = { ...section, id };
    });
    snapshot = {
      stockName: String(stockName || ''),
      sections,
      newsItems: Array.isArray(result?.news_items) ? result.news_items : [],
      disclosures: Array.isArray(result?.disclosures) ? result.disclosures : [],
      usFilings: Array.isArray(result?.us_filings) ? result.us_filings : [],
    };
    window.dispatchEvent(new CustomEvent('gaemi-analysis-data-change'));
  }

  function get() {
    return {
      ...snapshot,
      sections: { ...snapshot.sections },
      newsItems: [...snapshot.newsItems],
      disclosures: [...snapshot.disclosures],
      usFilings: [...snapshot.usFilings],
    };
  }

  window.GaemiGTPAnalysisData = { set, get };
}());
