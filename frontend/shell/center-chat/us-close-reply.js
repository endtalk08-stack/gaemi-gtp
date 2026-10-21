/* Shared US-market close presentation: original editorial + verified index table. */
(function () {
  'use strict';

  const INDEX_NAMES = ['다우존스', '나스닥 종합', 'S&P 500'];
  const priceFormat = new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 2, maximumFractionDigits: 2
  });

  function normalize(input) {
    if (!input || typeof input !== 'object') return null;
    // normalize() is deliberately idempotent. Both the gaemi follow-up and
    // the shared chat renderer validate first, then call plainText/render,
    // which must accept that already-normalized object too.
    const sessionDate = String(input.session_date_et || input.sessionDate || '');
    if (!/^\d{4}-\d{2}-\d{2}$/.test(sessionDate)) return null;
    const indices = input.market_indices || input.indices;
    const issues = input.issues;
    if (!Array.isArray(indices) || indices.length !== 3 || !Array.isArray(issues) || !issues.length) return null;
    const cleanIndices = [];
    for (let i = 0; i < 3; i += 1) {
      const item = indices[i];
      if (item?.name !== INDEX_NAMES[i]) return null;
      const close = Number(item.close);
      const pct = Number(item.change_pct ?? item.pct);
      if (!Number.isFinite(close) || close <= 0 || !Number.isFinite(pct) || Math.abs(pct) > 40) return null;
      cleanIndices.push({ name: INDEX_NAMES[i], close, pct });
    }
    const cleanIssues = issues.slice(0, 3).map(item => ({
      headline: String(item?.headline || '').trim().slice(0, 200),
      summary: String(item?.summary || '').trim().slice(0, 2600),
      tags: (Array.isArray(item?.tags) ? item.tags : [])
        .map(tag => String(tag || '').trim().replace(/^#+/, ''))
        .filter(Boolean).slice(0, 3)
    })).filter(item => item.headline && item.summary);
    if (!cleanIssues.length) return null;
    const responseFormat = (input.response_format || input.responseFormat) === "free_text_v1" ? "free_text_v1" : null;
    return { sessionDate, indices: cleanIndices, issues: cleanIssues, responseFormat };
  }

  function percent(item) {
    return (item.pct > 0 ? '+' : '') + item.pct.toFixed(2) + '%';
  }

  function plainText(presentation) {
    const data = normalize(presentation);
    if (!data) return '';
    const lines = [];
    for (let i = 0; i < data.issues.length; i += 1) {
      const issue = data.issues[i];
      lines.push(issue.headline);
      if (i === 0) {
        for (const index of data.indices) {
          lines.push(index.name + ' ' + priceFormat.format(index.close) + ' (' + percent(index) + ')');
        }
      }
      lines.push(issue.summary);
      if (issue.tags.length) lines.push(issue.tags.map(tag => '#' + tag).join(' '));
    }
    return lines.join('\n\n');
  }

  function indexTable(indices) {
    const table = document.createElement('table');
    table.className = 'gaemi-us-close-index-table';
    table.setAttribute('aria-label', '미국 3대 지수 정규장 마감');
    const head = document.createElement('thead');
    const headings = document.createElement('tr');
    for (const label of ['지수', '종가', '등락률']) {
      const cell = document.createElement('th');
      cell.scope = 'col';
      cell.textContent = label;
      headings.appendChild(cell);
    }
    head.appendChild(headings);
    table.appendChild(head);
    const body = document.createElement('tbody');
    for (const item of indices) {
      const tr = document.createElement('tr');
      const label = document.createElement('th');
      label.scope = 'row';
      label.textContent = item.name;
      const value = document.createElement('td');
      value.textContent = priceFormat.format(item.close);
      const delta = document.createElement('td');
      delta.className = item.pct > 0 ? 'gaemi-us-close-up' : item.pct < 0 ? 'gaemi-us-close-down' : '';
      delta.textContent = percent(item);
      tr.append(label, value, delta);
      body.appendChild(tr);
    }
    table.appendChild(body);
    return table;
  }

  // Same heading, paragraph and list recognition used by model-3 chat.
  // This only affects the new free-text US-close entries; legacy entries
  // keep their existing title / one-paragraph / tag presentation.
  function parseAnswerBlocks(text) {
    const lines = String(text || '').replace(/\\r\\n?/g, '\\n').split('\\n');
    const blocks = [];
    let paragraph = [];
    let list = null;
    const flushParagraph = () => {
      if (paragraph.length) blocks.push({ type: 'paragraph', text: paragraph.join('\\n') });
      paragraph = [];
    };
    const flushList = () => { if (list) blocks.push(list); list = null; };
    for (const line of lines) {
      if (!line.trim()) { flushParagraph(); flushList(); continue; }
      const markdownHeading = line.match(/^\\s{0,3}#{1,6}\\s+(.+?)\\s*#*\\s*$/);
      const boldHeading = line.match(/^\\s*\\*\\*(.{2,65}?)\\*\\*\\s*[:：]?\\s*$/);
      const item = line.match(/^\\s{0,3}([-*+]|\\d+[.)])\\s+(.+)$/);
      if (markdownHeading || boldHeading) {
        flushParagraph(); flushList();
        blocks.push({ type: 'heading', text: markdownHeading ? markdownHeading[1] : boldHeading[1] });
      } else if (item) {
        flushParagraph();
        const ordered = /^\\d/.test(item[1]);
        if (!list || list.ordered !== ordered) {
          flushList();
          list = { type: 'list', ordered, start: ordered ? Number.parseInt(item[1], 10) : 1, items: [] };
        }
        list.items.push(item[2]);
      } else {
        flushList();
        paragraph.push(line);
      }
    }
    flushParagraph(); flushList();
    return blocks;
  }

  async function render(node, presentation, { isActive, typeText } = {}) {
    const data = normalize(presentation);
    if (!node || !data || typeof isActive !== 'function' || typeof typeText !== 'function') return false;
    node.replaceChildren();
    node.classList.add('gaemi-us-close-reply');
    const type = async (element, text) => {
      if (!isActive()) return false;
      const typed = await typeText(element, text);
      return typed !== false && isActive();
    };
    for (let index = 0; index < data.issues.length; index += 1) {
      if (!isActive()) return false;
      const issue = data.issues[index];
      const section = document.createElement('section');
      section.className = 'gaemi-us-close-issue';
      const headline = document.createElement('p');
      headline.className = 'gaemi-us-close-title gtp-chat-copy';
      section.appendChild(headline);
      node.appendChild(section);
      if (!await type(headline, issue.headline)) return false;
      if (index === 0) {
        const wrap = document.createElement('div');
        wrap.className = 'gaemi-us-close-table-wrap';
        wrap.appendChild(indexTable(data.indices));
        section.appendChild(wrap);
        wrap.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
      if (data.responseFormat === 'free_text_v1') {
        const body = document.createElement('div');
        body.className = 'gaemi-us-close-body gtp-chat-copy';
        section.appendChild(body);
        for (const block of parseAnswerBlocks(issue.summary)) {
          if (!isActive()) return false;
          if (block.type === 'list') {
            const list = document.createElement(block.ordered ? 'ol' : 'ul');
            list.className = 'gaemi-us-close-list';
            if (block.ordered && block.start > 1) list.start = block.start;
            body.appendChild(list);
            for (const item of block.items) {
              const li = document.createElement('li');
              list.appendChild(li);
              if (!await type(li, item)) return false;
            }
          } else {
            const node = document.createElement(block.type === 'heading' ? 'div' : 'p');
            node.className = block.type === 'heading'
              ? 'gaemi-us-close-subheading' : 'gaemi-us-close-paragraph';
            body.appendChild(node);
            if (!await type(node, block.text)) return false;
          }
        }
      } else {
        const explanation = document.createElement('p');
        explanation.className = 'gaemi-us-close-summary gtp-chat-copy';
        section.appendChild(explanation);
        if (!await type(explanation, issue.summary)) return false;
      }
      if (issue.tags.length) {
        const tags = document.createElement('p');
        tags.className = 'gaemi-us-close-tags gtp-chat-copy';
        section.appendChild(tags);
        if (!await type(tags, issue.tags.map(tag => '#' + tag).join(' '))) return false;
      }
    }
    return isActive();
  }

  window.GaemiGTPUSCloseReply = { normalize, plainText, render };
}());
