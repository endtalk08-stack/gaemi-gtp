/* gaemiGTP News Workspace — compact live feed v1
   확정 UI:
   - 주요뉴스 3개 세로
   - 일반뉴스 기본 5개 / 더보기 최대 10개 / 접기
   - 일반뉴스 2행 구조
   - 제목/출처/시간만 표시, 원문은 외부 링크 확인창으로 연결
*/
(function () {
  'use strict';

  const NEWS_HTML = `<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<style>
:root{--bg:#0f1012;--card:#1e1f20;--hover:#282a2c;--txt:#f2f2f2;--sub:#8e918f;--active:#2b3a5a;--activeTxt:#8ab4f8}
*{box-sizing:border-box}
html,body{margin:0;width:100%;min-height:100%;background:var(--bg);color:var(--txt);font-family:Pretendard,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
body{overflow-y:auto}
button,input{font:inherit}
.app{width:100%;max-width:600px;margin:0 auto;padding:20px}
.search{height:48px;display:flex;align-items:center;gap:10px;background:var(--card);border-radius:10px;padding:0 14px;margin-bottom:18px}
.search svg{width:17px;height:17px;stroke:var(--sub);fill:none;stroke-width:2}
.search input{flex:1;min-width:0;background:transparent;border:0!important;outline:0!important;color:var(--sub);font-size:13px}
.search button{border:0!important;outline:0!important;background:transparent;color:var(--sub);padding:4px;cursor:pointer}
.cats{display:flex;gap:6px;overflow-x:auto;scrollbar-width:none;margin-bottom:24px}
.cats::-webkit-scrollbar{display:none}
.cat{flex:0 0 auto;border:0!important;outline:0!important;background:var(--card);color:var(--sub);padding:7px 13px;border-radius:8px;font-size:11px;font-weight:800;cursor:pointer}
.cat.active{background:var(--active);color:var(--activeTxt)}
.headline{margin-bottom:28px}
.section-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}
.section-head strong{font-size:17px}
.counter{font-size:11px;color:var(--sub)}
.carousel{display:grid;grid-template-columns:32px minmax(0,1fr) 32px;gap:8px;align-items:center}
.arrow{width:32px;height:32px;border:0!important;outline:0!important;border-radius:50%;background:var(--card);color:var(--txt);cursor:pointer;display:flex;align-items:center;justify-content:center}
.arrow:disabled{opacity:.2;cursor:default}
.arrow svg{width:15px;height:15px;stroke:currentColor;fill:none;stroke-width:2.4}
.track{display:grid;grid-template-columns:1fr;gap:8px}
.hl-card{min-height:54px;background:var(--card);border-radius:8px;padding:10px 14px;display:flex;align-items:center;cursor:pointer}
.hl-title{color:var(--sub);font-size:13px;font-weight:800;line-height:1.35;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.dots{display:flex;justify-content:center;gap:5px;margin-top:10px}
.dot{width:6px;height:6px;border-radius:50%;background:#3a3a3a}
.dot.active{width:18px;border-radius:4px;background:#8ab4f8}
.news-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;gap:10px}
.news-head h2{font-size:18px;margin:0}
.filters{display:flex;gap:7px}
.filter{border:0!important;outline:0!important;background:var(--card);color:var(--sub);padding:7px 10px;border-radius:7px;font-size:11px;cursor:pointer}
.list{display:flex;flex-direction:column}
.item{height:68px;background:var(--card);border-radius:8px;padding:9px 12px;margin-bottom:7px;display:grid;grid-template-columns:minmax(0,1fr) auto;grid-template-rows:auto auto;column-gap:12px;row-gap:6px;align-items:center;overflow:hidden;cursor:pointer}
.item:hover,.hl-card:hover,.filter:hover,.arrow:hover{background:var(--hover)}
.meta-left{grid-column:1;grid-row:1;font-size:10px;color:var(--sub)}
.tag{display:inline-block;background:#282a2c;color:#a0a0a0;padding:2px 6px;border-radius:4px;font-weight:800}
.meta-right{grid-column:2;grid-row:1;font-size:10px;color:var(--sub);white-space:nowrap;text-align:right}
.title{grid-column:1/3;grid-row:2;min-width:0;color:var(--sub);font-size:12px;font-weight:800;line-height:1.35;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.more{width:100%;height:46px;border:0!important;outline:0!important;border-radius:8px;background:var(--card);color:var(--txt);font-size:12px;font-weight:800;cursor:pointer;margin-bottom:8px}
.more:hover{background:var(--hover)}
.empty{padding:60px 20px;text-align:center;color:var(--sub);font-size:13px}
.status{padding:50px 20px;text-align:center;color:var(--sub);font-size:12px}
@media(max-width:480px){.app{padding:14px}.arrow{width:28px;height:28px}.carousel{grid-template-columns:28px minmax(0,1fr) 28px}.cat{padding:6px 11px}.meta-right{max-width:150px;overflow:hidden;text-overflow:ellipsis}}
</style>
</head>
<body>
<div class="app">
  <div class="search">
    <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
    <input id="searchInput" placeholder="검색어를 입력하세요">
    <button id="favBtn" type="button" aria-label="관심 뉴스">☆</button>
  </div>

  <div class="cats" id="cats">
    ${['전체','증시','종목','경제지표','에너지','연준','일정','투자의견','실적발표'].map((c,i)=>`<button type="button" class="cat ${i===0?'active':''}" data-cat="${c}">${c}</button>`).join('')}
  </div>

  <section class="headline">
    <div class="section-head"><strong>주요뉴스 &gt;</strong><span class="counter" id="counter">1 / 1</span></div>
    <div class="carousel">
      <button class="arrow" id="prev" type="button" aria-label="이전 주요뉴스"><svg viewBox="0 0 24 24"><polyline points="15 18 9 12 15 6"/></svg></button>
      <div class="track" id="track"></div>
      <button class="arrow" id="next" type="button" aria-label="다음 주요뉴스"><svg viewBox="0 0 24 24"><polyline points="9 18 15 12 9 6"/></svg></button>
    </div>
    <div class="dots" id="dots"></div>
  </section>

  <div class="news-head">
    <h2>뉴스</h2>
    <div class="filters">
      <button class="filter" type="button">출처⌄</button>
      <button class="filter" type="button">전체·최신순⌄</button>
      <button class="filter" id="refresh" type="button" aria-label="새로고침">↻</button>
    </div>
  </div>

  <div class="list" id="list"><div class="status">뉴스를 불러오는 중...</div></div>
  <button class="more" id="more" type="button" hidden>더보기</button>
</div>

<script>
(function(){
  const INIT=5, MAX=10, PER=3;
  let category='전체', query='', items=[], visible=INIT, page=0, timer=null;

  const esc=(v)=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));

  function openArticle(item){
    const payload={
      title:item.title,
      source:item.source,
      display_datetime:item.display_datetime,
      link:item.link,
      original_link:item.original_link||item.link
    };
    try{
      if(parent && typeof parent.openExternalLinkModal==='function'){
        parent.openExternalLinkModal(payload);
        return;
      }
    }catch(_){}
    if(payload.original_link) window.open(payload.original_link,'_blank','noopener');
  }

  function renderHeadlines(){
    const headlineItems=items.slice(0,MAX);
    const total=Math.max(1,Math.ceil(headlineItems.length/PER));
    if(page>=total) page=0;
    const slice=headlineItems.slice(page*PER,page*PER+PER);
    const track=document.getElementById('track');
    if(!slice.length){
      track.innerHTML='<div class="status">주요뉴스가 없습니다.</div>';
    }else{
      track.innerHTML=slice.map((n,i)=>'<div class="hl-card" data-headline="'+(page*PER+i)+'"><div class="hl-title">'+esc(n.title)+'</div></div>').join('');
    }
    document.getElementById('counter').textContent=(page+1)+' / '+total;
    document.getElementById('prev').disabled=page===0;
    document.getElementById('next').disabled=page>=total-1;
    document.getElementById('dots').innerHTML=Array.from({length:total},(_,i)=>'<span class="dot '+(i===page?'active':'')+'"></span>').join('');
    track.querySelectorAll('[data-headline]').forEach(el=>{
      el.addEventListener('click',()=>openArticle(headlineItems[Number(el.dataset.headline)]));
    });
  }

  function renderList(){
    const list=document.getElementById('list');
    if(!items.length){
      list.innerHTML='<div class="empty">표시할 뉴스가 없습니다.</div>';
      document.getElementById('more').hidden=true;
      return;
    }
    const show=items.slice(0,visible);
    list.innerHTML=show.map((n,i)=>
      '<article class="item" data-index="'+i+'">'+
        '<div class="meta-left"><span class="tag">'+esc(n.category||'증시')+'</span></div>'+
        '<div class="meta-right">'+esc(n.source||'출처 확인')+(n.display_datetime?' · '+esc(n.display_datetime):'')+'</div>'+
        '<div class="title">'+esc(n.title)+'</div>'+
      '</article>'
    ).join('');
    list.querySelectorAll('[data-index]').forEach(el=>{
      el.addEventListener('click',()=>openArticle(show[Number(el.dataset.index)]));
    });

    const more=document.getElementById('more');
    if(items.length<=INIT){
      more.hidden=true;
    }else{
      more.hidden=false;
      more.textContent=visible>INIT?'접기':'더보기 ('+(Math.min(MAX,items.length)-INIT)+'개 더)';
    }
  }

  async function load(){
    const list=document.getElementById('list');
    list.innerHTML='<div class="status">뉴스를 불러오는 중...</div>';
    document.getElementById('more').hidden=true;
    try{
      const url='/news?category='+encodeURIComponent(category)+'&q='+encodeURIComponent(query)+'&limit='+MAX;
      const res=await fetch(url,{headers:{'Accept':'application/json'}});
      const data=await res.json();
      items=Array.isArray(data.items)?data.items:[];
      visible=INIT; page=0;
      renderHeadlines(); renderList();
    }catch(e){
      items=[];
      list.innerHTML='<div class="empty">뉴스를 불러오지 못했습니다.</div>';
      renderHeadlines();
    }
  }

  document.getElementById('cats').addEventListener('click',e=>{
    const btn=e.target.closest('[data-cat]');
    if(!btn)return;
    document.querySelectorAll('.cat').forEach(x=>x.classList.remove('active'));
    btn.classList.add('active');
    category=btn.dataset.cat;
    load();
  });

  document.getElementById('searchInput').addEventListener('input',e=>{
    clearTimeout(timer);
    timer=setTimeout(()=>{query=e.target.value.trim();load()},250);
  });

  document.getElementById('refresh').addEventListener('click',load);
  document.getElementById('prev').addEventListener('click',()=>{if(page>0){page--;renderHeadlines()}});
  document.getElementById('next').addEventListener('click',()=>{const t=Math.ceil(Math.min(MAX,items.length)/PER);if(page<t-1){page++;renderHeadlines()}});
  document.getElementById('more').addEventListener('click',()=>{visible=visible>INIT?INIT:Math.min(MAX,items.length);renderList()});

  load();
})();
</script>
</body>
</html>`;

  function mount(root) {
    if (!root || root.dataset.newsWorkspaceMounted === 'true') return;

    root.innerHTML = `
      <div style="width:100%;height:100%;min-height:0;background:#0f1012;">
        <iframe
          class="gaemi-news-workspace-frame"
          title="뉴스"
          style="display:block;width:100%;height:100%;border:0;outline:0;background:#0f1012;"
          scrolling="yes"
        ></iframe>
      </div>
    `;

    const frame = root.querySelector('.gaemi-news-workspace-frame');
    frame.srcdoc = NEWS_HTML;
    root.dataset.newsWorkspaceMounted = 'true';
  }

  window.GaemiGTPNews = { mount };
})();
