// Plain-language company introduction; no duplicate stock title or visible source link.
(function () {
  'use strict';
  const TYPE_CHARS = 3;
  const TYPE_DELAY_MS = 36;

  function relatedSentence(data) {
    const peers = (Array.isArray(data.related) ? data.related : [])
      .map(item => String(item.name || '').trim() + ' (' + String(item.symbol || '').trim() + ')');
    return peers.length
      ? peers.join(' · ') + ' 등이 같은 업종에 속해 있어요.'
      : '현재 확인된 동일 업종 종목이 없어요.';
  }

  function readableText(data) {
    const intro = Array.isArray(data.paragraphs) ? data.paragraphs : [];
    const points = Array.isArray(data.highlights) ? data.highlights : [];
    return [
      ...intro,
      ...points.map(item => item.title + ': ' + item.description),
      relatedSentence(data)
    ].join('\n\n');
  }

  // Build inert DOM elements; no HTML string interpolation of provider data.
  function makeBlocks(data) {
    const blocks = [];
    for (const paragraph of data.paragraphs || []) {
      const p = document.createElement('p');
      p.className = 'gtp-chat-copy whitespace-pre-line';
      const node = document.createTextNode('');
      p.appendChild(node);
      blocks.push({ element: p, segments: [{ node, text: String(paragraph || '') }] });
    }
    for (const entry of data.highlights || []) {
      const p = document.createElement('p');
      p.className = 'gtp-chat-copy';
      const strong = document.createElement('strong');
      const node = document.createTextNode('');
      p.appendChild(strong);
      p.appendChild(node);
      blocks.push({
        element: p,
        segments: [
          { node: strong, text: String(entry.title || '') + ': ' },
          { node, text: String(entry.description || '') }
        ]
      });
    }
    const related = document.createElement('p');
    related.className = 'gtp-chat-copy';
    const relatedNode = document.createTextNode('');
    related.appendChild(relatedNode);
    blocks.push({ element: related, segments: [{ node: relatedNode, text: relatedSentence(data) }] });
    return blocks;
  }

  function valid(container, data) {
    return Boolean(container && data && data.symbol === 'MU');
  }

  function begin(container) {
    container.replaceChildren();
    container.className = 'gtp-chat-copy animate-fade space-y-4';
  }

  function render(container, data) {
    if (!valid(container, data)) return false;
    begin(container);
    for (const block of makeBlocks(data)) {
      for (const segment of block.segments) segment.node.textContent = segment.text;
      container.appendChild(block.element);
    }
    return true;
  }

  async function renderTyped(container, data, isActive = () => true) {
    if (!valid(container, data)) return false;
    begin(container);
    for (const block of makeBlocks(data)) {
      if (!isActive()) return false;
      container.appendChild(block.element);
      for (const segment of block.segments) {
        let cursor = 0;
        while (cursor < segment.text.length) {
          if (!isActive()) return false;
          segment.node.textContent += segment.text.slice(cursor, cursor + TYPE_CHARS);
          cursor += TYPE_CHARS;
          if (cursor < segment.text.length) {
            await new Promise(resolve => setTimeout(resolve, TYPE_DELAY_MS));
          }
        }
      }
    }
    return isActive();
  }

  window.GaemiGTPCompanyIntroPreview = { render, renderTyped, readableText };
}());
