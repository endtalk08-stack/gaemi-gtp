/* Nasdaq chart plugin — Render market-data read + Neon chart tags, no AI calls. */
(function () {
  'use strict';

  const SVG_NS = 'http://www.w3.org/2000/svg';
  const cache = { updatedAt: 0, result: null, promise: null };

  function backendUrl() {
    return window.location.hostname.endsWith('github.io')
      ? 'https://gaemi-gtp.onrender.com' : window.location.origin;
  }

  async function load() {
    if (cache.result && Date.now() - cache.updatedAt < 60000) return cache.result;
    if (cache.promise) return cache.promise;
    cache.promise = fetch(backendUrl() + '/api/market/nasdaq-chart', {
      method: 'GET', credentials: 'same-origin'
    }).then(async response => {
      if (!response.ok) throw new Error('nasdaq_chart_unavailable');
      const result = await response.json();
      if (!result || result.ok !== true || result.symbol !== '.IXIC'
        || !Array.isArray(result.points) || result.points.length < 2) {
        throw new Error('nasdaq_chart_invalid');
      }
      let previousDate = '';
      const points = [];
      for (const point of result.points.slice(-60)) {
        const date = String(point?.date || '');
        const close = Number(point?.close);
        if (!/^\\d{4}-\\d{2}-\\d{2}$/.test(date)
          || date <= previousDate || !Number.isFinite(close) || close <= 0) {
          throw new Error('nasdaq_chart_point_invalid');
        }
        previousDate = date;
        points.push({ date, close });
      }
      let annotation = null;
      const source = result.annotation;
      if (source && typeof source === 'object'
        && points.some(p => p.date === source.session_date_et)
        && Array.isArray(source.tags) && source.tags.length === 3
        && source.tags.every(tag => typeof tag === 'string'
          && /^#[^#\\s]{1,47}$/.test(tag))) {
        annotation = {
          date: source.session_date_et,
          tags: source.tags.slice(0, 3)
        };
      }
      cache.result = { points, annotation };
      cache.updatedAt = Date.now();
      return cache.result;
    }).finally(() => { cache.promise = null; });
    return cache.promise;
  }

  function element(tag, className, content) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (content !== undefined) node.textContent = content;
    return node;
  }

  function svgElement(tag, attrs) {
    const node = document.createElementNS(SVG_NS, tag);
    for (const [key, value] of Object.entries(attrs || {})) node.setAttribute(key, String(value));
    return node;
  }

  function formatPrice(value) {
    return value.toLocaleString('en-US', { maximumFractionDigits: 2, minimumFractionDigits: 2 });
  }

  function draw(host, data) {
    const { points, annotation } = data;
    const last = points[points.length - 1];
    const previous = points[points.length - 2];
    const percentage = previous.close
      ? ((last.close - previous.close) / previous.close * 100) : 0;
    const sign = percentage > 0 ? '+' : '';

    host.replaceChildren();
    const heading = element('div', 'nasdaq-chart__quote');
    heading.append(element('strong', '', formatPrice(last.close)));
    heading.append(element('span', percentage > 0 ? 'nasdaq-chart__up'
      : percentage < 0 ? 'nasdaq-chart__down' : '', sign + percentage.toFixed(2) + '%'));
    host.append(heading);

    const lows = points.map(p => p.close);
    const bottom = Math.min(...lows);
    const top = Math.max(...lows);
    const span = Math.max(top - bottom, 0.0001);
    const x = i => 14 + (i / (points.length - 1)) * 572;
    const y = price => 145 - ((price - bottom) / span) * 116;
    const svg = svgElement('svg', {
      viewBox: '0 0 600 170', preserveAspectRatio: 'none',
      role: 'img', 'aria-label': '최근 ' + points.length + '거래일 나스닥 종합 지수 차트'
    });
    svg.classList.add('nasdaq-chart__svg');
    const horizontal = svgElement('path', {
      d: 'M14 145 H586', class: 'nasdaq-chart__baseline'
    });
    svg.appendChild(horizontal);
    const path = svgElement('path', {
      d: points.map((p, i) => (i ? 'L' : 'M') + x(i).toFixed(2)
        + ' ' + y(p.close).toFixed(2)).join(' '),
      class: 'nasdaq-chart__line'
    });
    svg.appendChild(path);
    if (annotation) {
      const index = points.findIndex(row => row.date === annotation.date);
      if (index >= 0) {
        const position = { x: x(index), y: y(points[index].close) };
        const guide = svgElement('path', {
          d: 'M' + position.x + ' ' + position.y + ' V145',
          class: 'nasdaq-chart__guide'
        });
        const circle = svgElement('circle', {
          cx: position.x, cy: position.y, r: 5,
          class: 'nasdaq-chart__marker'
        });
        const title = svgElement('title');
        title.textContent = annotation.date + ' ' + annotation.tags.join(' ');
        circle.appendChild(title);
        svg.append(guide, circle);
        const label = svgElement('text', {
          x: Math.max(15, Math.min(450, position.x - 30)),
          y: Math.max(12, position.y - 12),
          class: 'nasdaq-chart__marker-label'
        });
        label.textContent = '미국장 이슈 3';
        svg.appendChild(label);
      }
    }
    host.appendChild(svg);
    host.appendChild(element('div', 'nasdaq-chart__dates',
      points[0].date + '  —  ' + last.date));
    if (annotation) {
      const tags = element('div', 'nasdaq-chart__tags');
      tags.appendChild(element('span', 'nasdaq-chart__date', annotation.date));
      for (const tag of annotation.tags) {
        tags.appendChild(element('span', 'nasdaq-chart__tag', tag));
      }
      host.appendChild(tags);
    } else {
      host.appendChild(element('p', 'nasdaq-chart__pending',
        '해당 거래일의 미국장 분석 해시태그가 저장되면 차트에 표시돼.'));
    }
  }

  function mount(host) {
    if (!host) return;
    host.replaceChildren(element('p', 'nasdaq-chart__pending', '나스닥 지수 불러오는 중…'));
    load().then(data => {
      if (host.isConnected) draw(host, data);
    }).catch(() => {
      if (host.isConnected) {
        host.replaceChildren(element('p', 'nasdaq-chart__pending',
          '나스닥 지수 원천 데이터를 불러올 수 없어.'));
      }
    });
  }

  window.GaemiGTPNasdaqWidget = { mount };
}());
