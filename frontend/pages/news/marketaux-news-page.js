/* gaemiGTP right-panel news — search + article intelligence surface. */
(function () {
  'use strict';

  const CATEGORIES = ['전체','증시','종목','경제지표','에너지','연준','일정','투자의견','실적발표'];
  const BACKEND_URL = window.location.hostname.endsWith('github.io') ? 'https://gaemi-gtp.onrender.com' : '';
  let selectedCategory = '전체';
  let searchQuery = '';
  let requestId = 0;

  function el(tag, cls, text) { const n=document.createElement(tag); if(cls)n.className=cls; if(text!==undefined)n.textContent=text; return n; }
  function renderMessage(root,msg){ root.replaceChildren(el('div','marketaux-news__status',msg)); }
  function closeArticleModal(){ document.querySelector('.news-article-modal')?.remove(); document.body.classList.remove('news-modal-open'); }
  function unique(values){ return [...new Set(values.filter(Boolean))]; }

  function inferIntelligence(item){
    const text=`${item.title||''} ${item.description||''}`.toLowerCase();
    const issues=[]; const stocks=[]; const themes=[];
    const issueRules=[['금리·통화정책',['금리','연준','fomc','파월']],['물가·경제지표',['cpi','pce','물가','gdp','고용']],['실적발표',['실적','영업이익','매출','earnings']],['반도체 업황',['반도체','hbm','메모리','dram']],['AI 투자',['ai','인공지능']],['유가·에너지',['유가','원유','천연가스','에너지']],['환율',['환율','달러','원화']],['정책·규제',['정부','정책','규제','법안']]];
    const stockRules=[['삼성전자',['삼성전자']],['SK하이닉스',['sk하이닉스','하이닉스']],['NAVER',['naver','네이버']],['현대차',['현대차','현대자동차']],['기아',['기아']],['엔비디아',['엔비디아','nvidia']],['테슬라',['테슬라','tesla']],['애플',['애플','apple']]];
    const themeRules=[['반도체',['반도체','hbm','dram','메모리']],['AI·소프트웨어',['ai','인공지능','소프트웨어']],['자동차',['자동차','현대차','기아','전기차']],['2차전지',['2차전지','배터리']],['에너지',['유가','원유','에너지','천연가스']],['금융',['은행','증권','보험','금융']],['바이오·헬스케어',['바이오','제약','의료','헬스케어']],['인터넷·플랫폼',['네이버','카카오','플랫폼']],['방산',['방산','무기','국방']],['조선',['조선','선박']]];
    issueRules.forEach(([label,words])=>{if(words.some(w=>text.includes(w)))issues.push(label);});
    stockRules.forEach(([label,words])=>{if(words.some(w=>text.includes(w)))stocks.push(label);});
    themeRules.forEach(([label,words])=>{if(words.some(w=>text.includes(w)))themes.push(label);});
    return { issues:unique(issues), stocks:unique(stocks), themes:unique(themes) };
  }

  function addIntelSection(parent,title,values,emptyText){
    const section=el('section','news-article-modal__intel');
    section.appendChild(el('h3','news-article-modal__section-title',title));
    if(values.length){ const chips=el('div','news-article-modal__chips'); values.forEach(v=>chips.appendChild(el('span','news-article-modal__chip',v))); section.appendChild(chips); }
    else section.appendChild(el('p','news-article-modal__section-empty',emptyText));
    parent.appendChild(section);
  }

  function openArticleModal(item){
    closeArticleModal();
    const intel=inferIntelligence(item);
    const overlay=el('div','news-article-modal'); const dialog=el('section','news-article-modal__dialog');
    dialog.setAttribute('role','dialog'); dialog.setAttribute('aria-modal','true'); dialog.setAttribute('aria-label',item.title||'뉴스 기사');
    const close=el('button','news-article-modal__close','×'); close.type='button'; close.setAttribute('aria-label','닫기'); close.addEventListener('click',closeArticleModal);
    const title=el('h2','news-article-modal__title',item.title||'제목 없는 기사');
    const meta=el('div','news-article-modal__meta'); meta.append(el('span','',item.source||'뉴스'),el('span','',item.display_datetime||''));
    const content=el('section','news-article-modal__content'); content.append(el('h3','news-article-modal__section-title','내용 설명'),el('p',item.description?'news-article-modal__summary':'news-article-modal__section-empty',item.description||'제공된 기사 설명이 없습니다. 원문에서 내용을 확인할 수 있습니다.'));
    dialog.append(close,title,meta,content);
    addIntelSection(dialog,'관련 이슈',intel.issues,'기사 제목과 설명에서 직접 연결되는 이슈를 찾지 못했습니다.');
    addIntelSection(dialog,'관련 종목',intel.stocks,'기사에서 직접 언급된 주요 종목이 없습니다.');
    addIntelSection(dialog,'관련 산업·테마',intel.themes,'기사에서 직접 연결되는 산업·테마를 찾지 못했습니다.');
    const actions=el('div','news-article-modal__actions'); const original=el('a','news-article-modal__original','원문 기사 보기'); original.href=item.original_link||item.link||'#'; original.target='_blank'; original.rel='noopener noreferrer'; actions.appendChild(original); dialog.appendChild(actions);
    overlay.appendChild(dialog); overlay.addEventListener('click',e=>{if(e.target===overlay)closeArticleModal();});
    const key=e=>{if(e.key==='Escape'){closeArticleModal();document.removeEventListener('keydown',key);}}; document.addEventListener('keydown',key); document.body.appendChild(overlay); document.body.classList.add('news-modal-open'); close.focus();
  }

  function renderItems(root,items){
    const list=el('div','marketaux-news__list'); if(!items.length)list.appendChild(el('div','marketaux-news__status','표시할 뉴스가 없습니다.'));
    items.forEach(item=>{ const article=el('article','marketaux-news__item'); const button=el('button','marketaux-news__article'); button.type='button'; button.addEventListener('click',()=>openArticleModal(item)); const meta=el('div','marketaux-news__meta'); meta.append(el('span','marketaux-news__category',item.category||selectedCategory),el('span','marketaux-news__source',item.source||item.provider||'뉴스'),el('span','marketaux-news__time',item.display_datetime||'')); button.append(meta,el('div','marketaux-news__title',item.title||'제목 없는 기사')); if(item.description)button.appendChild(el('div','marketaux-news__description',item.description)); article.appendChild(button); list.appendChild(article); }); root.replaceChildren(list);
  }

  async function load(root){
    const current=++requestId; renderMessage(root,'뉴스를 불러오는 중입니다.');
    try{ const params=new URLSearchParams({category:selectedCategory,limit:'20'}); if(searchQuery)params.set('query',searchQuery); const response=await fetch(`${BACKEND_URL}/news?${params}`,{headers:{Accept:'application/json'}}); const payload=await response.json(); if(current!==requestId)return; if(!response.ok||!Array.isArray(payload.items)){renderMessage(root,'뉴스를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.');return;} renderItems(root,payload.items); }
    catch(_){if(current===requestId)renderMessage(root,'뉴스를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.');}
  }

  function mount(root){
    if(!root)return; root.replaceChildren(); const page=el('section','marketaux-news'); const results=el('div','marketaux-news__results');
    const search=el('form','marketaux-news__search'); const icon=el('span','marketaux-news__search-icon','⌕'); const input=el('input','marketaux-news__search-input'); input.type='search'; input.placeholder='뉴스, 종목, 이슈 검색'; input.value=searchQuery; input.setAttribute('aria-label','뉴스 검색'); const clear=el('button','marketaux-news__search-clear','×'); clear.type='button'; clear.setAttribute('aria-label','검색어 지우기'); clear.hidden=!searchQuery; input.addEventListener('input',()=>{clear.hidden=!input.value;}); clear.addEventListener('click',()=>{input.value=''; searchQuery=''; clear.hidden=true; input.focus(); load(results);}); search.addEventListener('submit',e=>{e.preventDefault();searchQuery=input.value.trim();clear.hidden=!searchQuery;load(results);}); search.append(icon,input,clear);
    const categories=el('div','marketaux-news__categories'); CATEGORIES.forEach(category=>{ const button=el('button',`marketaux-news__filter${category===selectedCategory?' is-active':''}`,category); button.type='button'; button.addEventListener('click',()=>{if(selectedCategory===category)return;selectedCategory=category;categories.querySelectorAll('.marketaux-news__filter').forEach(f=>f.classList.toggle('is-active',f.textContent===selectedCategory));load(results);}); categories.appendChild(button); });
    page.append(search,categories,results); root.appendChild(page); load(results);
  }
  window.GaemiGTPMarketauxNews={mount};
})();
