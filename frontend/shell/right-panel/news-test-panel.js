/* News Test Panel
   책임: 수집 기사에서 추출한 사실만으로 만든 기사형 테스트 결과를 렌더링한다.
   원문 제목·설명·출처는 이 패널에 표시하지 않는다. */
(function () {
  'use strict';

  function render(root, articles) {
    if (!root) return;
    root.replaceChildren();
    const section = document.createElement('section');
    section.className = 'news-test-panel';
    section.setAttribute('aria-label', '뉴스 테스트');

    if (!articles.length) {
      const empty = document.createElement('p');
      empty.className = 'news-test-panel__empty';
      empty.textContent = '분석할 뉴스가 없습니다. 종목을 다시 분석해 주세요.';
      section.appendChild(empty);
      root.appendChild(section);
      return;
    }

    articles.forEach((item) => {
      const article = document.createElement('article');
      article.className = 'news-test-panel__article';

      const headline = document.createElement('h3');
      headline.className = 'news-test-panel__headline';
      const time = document.createElement('time');
      time.className = 'news-test-panel__time';
      time.textContent = String(item?.time || '').trim();
      const title = document.createElement('span');
      title.textContent = String(item?.headline || '').trim();
      headline.append(time, title);

      const body = document.createElement('p');
      body.className = 'news-test-panel__body';
      body.textContent = String(item?.body || '').trim();

      article.append(headline);
      if (body.textContent) article.appendChild(body);

      const tags = Array.isArray(item?.tags) ? item.tags.map((tag) => String(tag || '').trim().replace(/^#/, '')).filter(Boolean) : [];
      if (tags.length) {
        const tagLine = document.createElement('p');
        tagLine.className = 'news-test-panel__tags';
        tagLine.textContent = tags.map((tag) => `#${tag}`).join('  ');
        article.appendChild(tagLine);
      }

      const stocks = Array.isArray(item?.stock_names) ? item.stock_names.map((name) => String(name || '').trim()).filter(Boolean) : [];
      if (stocks.length) {
        const label = document.createElement('p');
        label.className = 'news-test-panel__stocks-label';
        label.textContent = '관련 종목';
        const list = document.createElement('ul');
        list.className = 'news-test-panel__stocks';
        stocks.forEach((name) => {
          const stock = document.createElement('li');
          stock.textContent = name;
          list.appendChild(stock);
        });
        article.append(label, list);
      }

      section.appendChild(article);
    });
    root.appendChild(section);
  }

  window.GaemiGTPNewsTestPanel = { render };
}());
