// Plain-language company introduction. No price, sector field table or AI inference.
(function () {
  'use strict';
  function readableText(data) {
    const intro = Array.isArray(data.paragraphs) ? data.paragraphs : [];
    const points = Array.isArray(data.highlights) ? data.highlights : [];
    const related = Array.isArray(data.related) ? data.related : [];
    return [
      ...intro,
      ...points.map(item => item.title + ': ' + item.description),
      related.length
        ? related.map(item => item.name + ' (' + item.symbol + ')').join(' · ') + ' 등이 같은 업종에 속해 있어요.'
        : '현재 확인된 동일 업종 종목이 없어요.'
    ].join('\n\n');
  }
  function render(container, data) {
    if (!container || !data || data.symbol !== 'MU') return false;
    container.replaceChildren();
    container.className = 'gtp-chat-copy animate-fade space-y-4';
    const heading = document.createElement('h3');
    heading.className = 'gtp-chat-section-title gtp-dark-text font-bold';
    heading.textContent = data.name || '마이크론 테크놀로지';
    container.appendChild(heading);
    for (const paragraph of data.paragraphs || []) {
      const p = document.createElement('p');
      p.className = 'gtp-chat-copy whitespace-pre-line';
      p.textContent = paragraph;
      container.appendChild(p);
    }
    for (const entry of data.highlights || []) {
      const p = document.createElement('p');
      p.className = 'gtp-chat-copy';
      const bold = document.createElement('strong');
      bold.textContent = entry.title + ': ';
      p.appendChild(bold);
      p.appendChild(document.createTextNode(entry.description));
      container.appendChild(p);
    }
    const related = document.createElement('p');
    related.className = 'gtp-chat-copy';
    const peers = (data.related || []).map(item => item.name + ' (' + item.symbol + ')');
    related.textContent = peers.length
      ? peers.join(' · ') + ' 등이 같은 업종에 속해 있어요.'
      : '현재 확인된 동일 업종 종목이 없어요.';
    container.appendChild(related);
    if (data.source_url) {
      const link = document.createElement('a');
      link.href = data.source_url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.className = 'text-xs text-[#64748b] underline dark:text-[#a1a1aa]';
      link.textContent = '기업 공식 소개 · 출처';
      container.appendChild(link);
    }
    return true;
  }
  window.GaemiGTPCompanyIntroPreview = { render, readableText };
}());
