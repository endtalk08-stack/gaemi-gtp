(function(){
  const NEWS = [
    {id:101,cat:'증시',source:'한국경제',time:'방금 전',title:'연준 의장 긴급 기자회견… 시장 예상 뒤집어',views:'12.5K',url:'https://www.hankyung.com'},
    {id:102,cat:'종목',source:'연합뉴스',time:'1분 전',title:'중국, 미국산 반도체 관세 25% 부과 발표',views:'8.9K',url:'https://www.yna.co.kr'},
    {id:1,cat:'증시',source:'한국경제',time:'11:19',title:"미중, AI·무역 협상 진전…'미중 AI 대화' 출범 합의",views:'23K',url:'https://www.hankyung.com'},
    {id:9,cat:'증시',source:'파이낸셜뉴스',time:'15:42',title:'나스닥 사상 최고치 경신… 기술주 랠리 이어져',views:'9.8K',url:'https://www.fnnews.com'},
    {id:4,cat:'종목',source:'조선비즈',time:'20:48',title:'테슬라, 신형 모델 Y 생산 일정 6개월 앞당긴다',views:'32.1K',url:'https://biz.chosun.com'},
    {id:5,cat:'종목',source:'이데일리',time:'19:22',title:'애플, AI 탑재 신형 아이패드 다음 달 공개 예정',views:'12.5K',url:'https://www.edaily.co.kr'},
    {id:6,cat:'종목',source:'머니투데이',time:'18:05',title:'엔비디아, 차세대 GPU 블랙웰 울트라 발표 임박',views:'8.9K',url:'https://www.mt.co.kr'},
    {id:103,cat:'경제지표',source:'매일경제',time:'10분 전',title:'미국 CPI 예상치 상회… 3.2% 기록',views:'6.2K',url:'https://www.mk.co.kr'},
    {id:104,cat:'경제지표',source:'헤럴드경제',time:'25분 전',title:'한국 GDP 성장률 0.6%… 예상치 부합',views:'3.4K',url:'https://biz.heraldcorp.com'},
    {id:2,cat:'에너지',source:'한국일보',time:'22:41',title:'트럼프, 이란 대통령과 회담 가능성 열어둬',views:'47.4K',url:'https://www.hankookilbo.com'},
    {id:7,cat:'에너지',source:'서울경제',time:'17:33',title:'국제 유가 3% 급락… 중동 긴장 완화 기대감',views:'5.4K',url:'https://www.sedaily.com'},
    {id:3,cat:'연준',source:'매일경제',time:'21:15',title:'연준 인사들, 금리 동결 시사… 인플레 둔화 속도 주시',views:'18.2K',url:'https://www.mk.co.kr'},
    {id:8,cat:'연준',source:'헤럴드경제',time:'16:11',title:'일본은행, 예상대로 금리 동결… 엔화 약세 지속',views:'4.2K',url:'https://biz.heraldcorp.com'},
    {id:105,cat:'일정',source:'연합뉴스',time:'2시간 전',title:'FOMC 회의 다음 주 개최… 금리 결정 임박',views:'7.8K',url:'https://www.yna.co.kr'},
    {id:106,cat:'일정',source:'한국경제',time:'3시간 전',title:'엔비디아 GTC 컨퍼런스 3월 개최 예정',views:'5.1K',url:'https://www.hankyung.com'},
    {id:107,cat:'투자의견',source:'머니투데이',time:'4시간 전',title:'골드만삭스, S&P500 목표가 6,200으로 상향',views:'6.9K',url:'https://www.mt.co.kr'},
    {id:108,cat:'실적발표',source:'조선비즈',time:'5시간 전',title:'테슬라 4분기 실적 예상치 상회… 시간외 5% 급등',views:'11.2K',url:'https://biz.chosun.com'},
    {id:109,cat:'실적발표',source:'이데일리',time:'6시간 전',title:'애플, 아이폰 판매 호조로 사상 최대 매출',views:'9.7K',url:'https://www.edaily.co.kr'}
  ];

  const categories=['전체','증시','종목','경제지표','에너지','연준','일정','투자의견','실적발표'];
  const escapeHtml = s => String(s ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));

  function renderNewsWidget(root){
    let category='전체', query='', limit=6;
    root.innerHTML = `
      <section class="news-widget">
        <div class="news-widget-head">
          <div><div class="news-widget-title">📰 뉴스</div><div class="news-widget-sub">주요 뉴스 · 재료 뉴스</div></div>
          <button class="news-widget-refresh" type="button" title="새로고침" aria-label="뉴스 새로고침">↻</button>
        </div>
        <div class="news-widget-tools">
          <input class="news-widget-search" type="search" placeholder="뉴스 검색" aria-label="뉴스 검색">
          <div class="news-widget-cats">${categories.map(c=>`<button type="button" data-cat="${escapeHtml(c)}" class="news-widget-cat ${c==='전체'?'active':''}">${escapeHtml(c)}</button>`).join('')}</div>
        </div>
        <div class="news-widget-list"></div>
        <button class="news-widget-more" type="button">더보기</button>
      </section>`;

    const list=root.querySelector('.news-widget-list');
    const more=root.querySelector('.news-widget-more');
    const search=root.querySelector('.news-widget-search');
    const refresh=root.querySelector('.news-widget-refresh');

    function filtered(){
      const q=query.trim().toLowerCase();
      return NEWS.filter(n => (category==='전체'||n.cat===category) && (!q || n.title.toLowerCase().includes(q)||n.source.toLowerCase().includes(q)));
    }
    function paint(){
      const items=filtered();
      const visible=items.slice(0,limit);
      list.innerHTML=visible.length ? visible.map(n=>`<button type="button" class="news-widget-item" data-news-id="${n.id}">
        <div class="news-widget-item-top"><span class="news-widget-tag">${escapeHtml(n.cat)}</span><span>${escapeHtml(n.time)}</span></div>
        <div class="news-widget-item-title">${escapeHtml(n.title)}</div>
        <div class="news-widget-item-bottom"><span>${escapeHtml(n.source)}</span><span>◉ ${escapeHtml(n.views)}</span></div>
      </button>`).join('') : '<div class="news-widget-empty">검색 결과가 없습니다.</div>';
      more.hidden=items.length<=limit;
    }
    root.querySelectorAll('.news-widget-cat').forEach(btn=>btn.addEventListener('click',()=>{
      category=btn.dataset.cat; limit=6;
      root.querySelectorAll('.news-widget-cat').forEach(b=>b.classList.toggle('active',b===btn));
      paint();
    }));
    search.addEventListener('input',()=>{query=search.value;limit=6;paint();});
    more.addEventListener('click',()=>{limit+=6;paint();});
    refresh.addEventListener('click',()=>{refresh.classList.add('spin');setTimeout(()=>refresh.classList.remove('spin'),450);paint();});
    list.addEventListener('click',e=>{
      const item=e.target.closest('[data-news-id]'); if(!item)return;
      const n=NEWS.find(x=>String(x.id)===item.dataset.newsId); if(n) showNewsDetail(root,n);
    });
    paint();
  }

  function showNewsDetail(root,n){
    root.querySelector('.news-widget').innerHTML=`
      <div class="news-widget-detail">
        <div class="news-widget-detail-head"><button type="button" class="news-widget-back">← 뉴스</button><span>${escapeHtml(n.time)}</span></div>
        <div class="news-widget-detail-tag">${escapeHtml(n.cat)}</div>
        <h3>${escapeHtml(n.title)}</h3>
        <div class="news-widget-detail-source">${escapeHtml(n.source)} · 조회 ${escapeHtml(n.views)}</div>
        <div class="news-widget-detail-section"><b>관련 정보</b><div class="news-widget-chip-row"><span>#${escapeHtml(n.cat)}</span><span>#뉴스</span></div></div>
        <a class="news-widget-original" href="${escapeHtml(n.url)}" target="_blank" rel="noopener noreferrer">기사 원문 ↗</a>
      </div>`;
    root.querySelector('.news-widget-back').addEventListener('click',()=>renderNewsWidget(root));
  }

  window.NewsWidget={render:renderNewsWidget};
})();
