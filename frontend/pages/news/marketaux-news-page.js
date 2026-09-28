/* gaemiGTP right-panel news — domestic description value test only. */
(function () {
  'use strict';
  const BACKEND_URL = window.location.hostname.endsWith('github.io') ? 'https://gaemi-gtp.onrender.com' : '';
  let requestId = 0;
  function el(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;}
  function renderMessage(root,msg){root.replaceChildren(el('div','marketaux-news__status',msg));}
  function closeArticleModal(){document.querySelector('.news-article-modal')?.remove();document.body.classList.remove('news-modal-open');}
  function openArticleModal(item){
    closeArticleModal();
    const overlay=el('div','news-article-modal'),dialog=el('section','news-article-modal__dialog');dialog.setAttribute('role','dialog');dialog.setAttribute('aria-modal','true');
    const close=el('button','news-article-modal__close','×');close.type='button';close.addEventListener('click',closeArticleModal);
    const title=el('h2','news-article-modal__title',item.title||'제목 없는 기사');
    const meta=el('div','news-article-modal__meta');meta.append(el('span','',item.source||'뉴스'),el('span','',item.display_datetime||''));
    const content=el('section','news-article-modal__content');
    content.append(el('h3','news-article-modal__section-title','내용 설명'),el('p',item.description?'news-article-modal__summary':'news-article-modal__section-empty',item.description||'제공된 기사 설명이 없습니다.'));
    const actions=el('div','news-article-modal__actions'),original=el('a','news-article-modal__original','원문 기사 보기');original.href=item.original_link||item.link||'#';original.target='_blank';original.rel='noopener noreferrer';actions.appendChild(original);
    dialog.append(close,title,meta,content,actions);overlay.appendChild(dialog);overlay.addEventListener('click',e=>{if(e.target===overlay)closeArticleModal();});document.body.appendChild(overlay);document.body.classList.add('news-modal-open');close.focus();
  }
  function renderItems(root,items){const list=el('div','marketaux-news__list');if(!items.length)list.appendChild(el('div','marketaux-news__status','표시할 뉴스가 없습니다.'));items.forEach(item=>{const article=el('article','marketaux-news__item'),button=el('button','marketaux-news__article');button.type='button';button.addEventListener('click',()=>openArticleModal(item));button.appendChild(el('div','marketaux-news__title',item.title||'제목 없는 기사'));if(item.description)button.appendChild(el('div','marketaux-news__description',item.description));const meta=el('div','marketaux-news__meta');meta.append(el('span','marketaux-news__source',item.source||item.provider||'뉴스'),el('span','marketaux-news__time',item.display_datetime||''));button.appendChild(meta);article.appendChild(button);list.appendChild(article);});root.replaceChildren(list);}
  async function load(root){
    const current=++requestId;renderMessage(root,'뉴스를 불러오는 중입니다.');
    try{
      const response=await fetch(`${BACKEND_URL}/news?category=전체&limit=20`,{headers:{Accept:'application/json'}});
      const data=await response.json();
      if(current!==requestId)return;
      renderItems(root,Array.isArray(data.items)?data.items:[]);
    }catch(_){if(current===requestId)renderMessage(root,'뉴스를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.');}
  }
  function mount(root){if(!root)return;root.replaceChildren();const page=el('section','marketaux-news'),results=el('div','marketaux-news__results');page.appendChild(results);root.appendChild(page);load(results);}
  window.GaemiGTPMarketauxNews={mount};
})();
