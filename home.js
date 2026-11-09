document.addEventListener('DOMContentLoaded',async()=>{
  document.querySelectorAll('a[target="_blank"]').forEach(a=>a.rel='noopener noreferrer');
  const cards=[...document.querySelectorAll('.top-item, .more-card')];

  try{
    const self=[...document.scripts].find(s=>s.src.includes('/home.js'))?.src||location.href;
    const reportDate=document.body.dataset.reportDate||document.querySelector('.week-asof')?.textContent.trim()||document.querySelector('.topline span:last-child')?.textContent.trim()||'current';
    const shellUrl=new URL(self,location.href);
    const token=shellUrl.searchParams.get('v')||reportDate.replaceAll('-','');
    const moduleUrl=new URL('canonical-client.js',self);
    moduleUrl.searchParams.set('v',token);
    const mod=await import(moduleUrl.href);
    await mod.hydrateCanonicalAnalysis();
  }catch(err){console.warn('Canonical intelligence renderer unavailable',err);}

  cards.forEach(card=>{const all=[...card.querySelectorAll('details')];all.slice(1).forEach(d=>d.remove());});
  const analyses=[...document.querySelectorAll('.home-full-analysis')];
  analyses.forEach(d=>d.addEventListener('toggle',()=>{if(d.open)analyses.forEach(other=>{if(other!==d)other.open=false;});}));
});

// Current-day workspace: category tabs never switch into the History portal.
document.addEventListener('DOMContentLoaded',()=>{
  const NAV_SELECTOR='nav.global-category-nav';
  const nav=document.querySelector(NAV_SELECTOR);
  const homeMain=document.querySelector('main.home-main');
  if(!nav||!homeMain||!document.body.classList.contains('home-page'))return;

  const initialTitle=document.title;
  const rootUrl=new URL('./',location.href);rootUrl.search='';rootUrl.hash='';
  const dateFromNav=[...nav.querySelectorAll('a[data-category][href]')].map(a=>a.getAttribute('href')?.match(/20\d{2}-\d{2}-\d{2}/)?.[0]).find(Boolean)||'';
  const reportDate=document.body.dataset.reportDate||document.querySelector('.week-asof')?.textContent.trim()||dateFromNav;
  let controller=null;
  let categoryMain=null;

  function setActive(category){
    nav.querySelectorAll('a.global-category-link:not(.preference-bookmark-link):not(.global-history-link)').forEach(link=>{
      const key=link.dataset.category||'top5';
      link.classList.toggle('is-active',key===(category||'top5'));
    });
  }

  function prepareCategoryMain(main){
    main.querySelector('.category-bottom-nav')?.remove();
    main.querySelectorAll('a[target="_blank"]').forEach(a=>a.rel='noopener noreferrer');
    const details=[...main.querySelectorAll('details')];
    details.forEach(d=>{
      d.open=false;
      d.addEventListener('toggle',()=>{if(d.open)details.forEach(other=>{if(other!==d)other.open=false;});});
    });
  }

  function absolutizeContent(root,baseUrl){
    root.querySelectorAll('[src]').forEach(node=>{try{node.setAttribute('src',new URL(node.getAttribute('src'),baseUrl).href);}catch(_){}});
    root.querySelectorAll('a[href]').forEach(node=>{try{node.setAttribute('href',new URL(node.getAttribute('href'),baseUrl).href);}catch(_){}});
  }

  function ensureCategoryStyles(doc,targetUrl){
    const already=[...document.querySelectorAll('link[rel="stylesheet"][href]')].some(link=>new URL(link.href,location.href).pathname.endsWith('/category.css'));
    if(already)return Promise.resolve();
    const source=[...doc.querySelectorAll('link[rel="stylesheet"][href]')].find(link=>link.getAttribute('href').includes('category.css'));
    if(!source)return Promise.resolve();
    const link=document.createElement('link');link.rel='stylesheet';link.href=new URL(source.getAttribute('href'),targetUrl).href;
    return new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>{link.remove();reject(new Error('category style timeout'));},10000);
      link.onload=()=>{clearTimeout(timer);resolve();};
      link.onerror=()=>{clearTimeout(timer);link.remove();reject(new Error('category style unavailable'));};
      document.head.appendChild(link);
    });
  }

  async function showCategory(category,{push=true}={}){
    if(!reportDate||!category)return;
    if(![...nav.querySelectorAll('[data-category]')].some(link=>link.dataset.category===category)){
      showTop({push:false});
      return;
    }
    const sourceUrl=new URL(`${reportDate}/${category}/`,rootUrl);
    if(controller)controller.abort();
    controller=new AbortController();
    const request=controller;
    const timer=setTimeout(()=>request.abort(),15000);
    nav.setAttribute('aria-busy','true');
    try{
      const response=await fetch(sourceUrl.href,{credentials:'same-origin',signal:controller.signal});
      if(!response.ok)throw new Error(`HTTP ${response.status}`);
      const html=await response.text();
      const doc=new DOMParser().parseFromString(html,'text/html');
      const nextMain=doc.querySelector('main.category-main');
      if(!nextMain)throw new Error('category content missing');
      absolutizeContent(nextMain,sourceUrl.href);
      await ensureCategoryStyles(doc,sourceUrl.href);
      if(controller!==request)return;
      if(request.signal.aborted)throw new Error('category request timeout');
      document.querySelector('.workspace-error')?.remove();
      const imported=document.importNode(nextMain,true);
      prepareCategoryMain(imported);
      if(!imported.querySelector('[data-intel-role="card"],.category-empty')){
        const empty=document.createElement('div');empty.className='category-empty';empty.setAttribute('role','status');
        const heading=document.createElement('h1');heading.textContent=nav.querySelector(`[data-category="${CSS.escape(category)}"]`).textContent;
        const note=document.createElement('p');note.textContent=`${reportDate} 暫無符合品質標準的新情報，請查看其他分類或歷史文章。`;
        const link=document.createElement('a');link.href=new URL('history/',rootUrl).href;link.textContent='搜尋歷史文章 →';
        empty.append(heading,note,link);imported.append(empty);
      }
      if(categoryMain)categoryMain.replaceWith(imported);else homeMain.insertAdjacentElement('afterend',imported);
      categoryMain=imported;
      homeMain.hidden=true;
      setActive(category);
      const label=nav.querySelector(`a[data-category="${CSS.escape(category)}"]`)?.textContent.trim()||category;
      document.title=`${label}｜今天｜AI 3D Daily`;
      if(push){const current=new URL(rootUrl.href);current.searchParams.set('view',category);history.pushState({currentWorkspace:true,view:category},'',current.href);}
      window.scrollTo({top:0,behavior:'auto'});
    }catch(error){
      if(controller!==request)return;
      document.querySelector('.workspace-error')?.remove();
      const message=document.createElement('div');message.className='workspace-error';message.setAttribute('role','alert');
      const note=document.createElement('p');note.textContent='分類暫時無法載入，已保留目前內容。請稍後重試。';
      const retry=document.createElement('button');retry.type='button';retry.textContent='重新載入分類';retry.onclick=()=>{message.remove();showCategory(category,{push});};
      message.append(note,retry);nav.insertAdjacentElement('afterend',message);
    }finally{clearTimeout(timer);if(controller===request)nav.removeAttribute('aria-busy');}
  }

  function showTop({push=true}={}){
    if(controller)controller.abort();
    controller=null;
    nav.removeAttribute('aria-busy');
    document.querySelector('.workspace-error')?.remove();
    categoryMain?.remove();categoryMain=null;
    homeMain.hidden=false;
    setActive('top5');
    document.title=initialTitle;
    if(push)history.pushState({currentWorkspace:true,view:'top5'},'',rootUrl.href);
    window.scrollTo({top:0,behavior:'auto'});
  }

  function categoryFromLink(link){
    if(link.dataset.category)return link.dataset.category;
    const raw=link.getAttribute('href')||'';
    try{
      const view=new URL(raw,rootUrl.href).searchParams.get('view');
      if(view)return view;
    }catch(_){}
    const match=raw.match(/20\d{2}-\d{2}-\d{2}\/([^/]+)\/?/);
    return match?.[1]||'';
  }

  function normalizeCurrentWorkspaceLinks(){
    nav.querySelectorAll('a.global-category-link[data-category]').forEach(link=>{
      const category=link.dataset.category||'';
      if(category)link.setAttribute('href',`?view=${encodeURIComponent(category)}`);
    });
    document.querySelectorAll('a.category-nav-card[href]').forEach(link=>{
      const category=categoryFromLink(link);
      if(!category)return;
      link.dataset.category=category;
      link.setAttribute('href',`?view=${encodeURIComponent(category)}`);
    });
  }

  normalizeCurrentWorkspaceLinks();

  document.addEventListener('click',event=>{
    if(event.defaultPrevented||event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;
    const tab=event.target.closest(`${NAV_SELECTOR} a.global-category-link[href]:not(.preference-bookmark-link):not(.global-history-link)`);
    if(tab){
      event.preventDefault();
      const category=tab.dataset.category||'';
      category?showCategory(category,{push:true}):showTop({push:true});
      return;
    }
    const card=event.target.closest('a.category-nav-card[href]');
    if(card){const category=categoryFromLink(card);if(category){event.preventDefault();showCategory(category,{push:true});}}
  });

  window.addEventListener('popstate',()=>{
    const view=new URL(location.href).searchParams.get('view')||'top5';
    view==='top5'?showTop({push:false}):showCategory(view,{push:false});
  });

  const initialView=new URL(location.href).searchParams.get('view');
  if(initialView&&initialView!=='top5')showCategory(initialView,{push:false});
});

document.addEventListener('DOMContentLoaded',()=>{
  const library=document.querySelector('.today-library');
  if(!library)return;
  const rows=[...library.querySelectorAll('.library-row')];
  const search=library.querySelector('#today-search');
  const category=library.querySelector('#today-category');
  const freshness=library.querySelector('#today-freshness');
  function filter(){
    const query=search.value.trim().toLocaleLowerCase();let count=0;
    rows.forEach(row=>{
      row.hidden=!(row.textContent.toLocaleLowerCase().includes(query)&&
        (category.value==='all'||row.dataset.category===category.value)&&
        (freshness.value==='all'||row.dataset.freshness===freshness.value));
      if(!row.hidden)count++;
    });
    library.querySelector('#today-result-count').textContent=`顯示 ${count} / ${rows.length} 篇`;
    library.querySelector('#today-empty').hidden=count!==0;
  }
  search.addEventListener('input',filter);category.addEventListener('change',filter);freshness.addEventListener('change',filter);
  const toggle=document.createElement('button');toggle.type='button';toggle.className='reading-mode';
  let compact=false;try{compact=localStorage.getItem('ai3d-reading-mode')==='compact';}catch(_){}
  function paint(){document.body.classList.toggle('is-compact',compact);toggle.setAttribute('aria-pressed',String(compact));toggle.textContent=compact?'顯示文章圖片':'精簡閱讀';}
  toggle.addEventListener('click',()=>{compact=!compact;paint();try{localStorage.setItem('ai3d-reading-mode',compact?'compact':'visual');}catch(_){}});
  document.querySelector('.edition-links')?.append(toggle);paint();filter();
});
