(()=>{
  const NAV_SELECTOR='nav.global-category-nav';
  let controller=null;

  function bodyIsCategory(doc=document){
    return !!doc.body?.classList.contains('category-page');
  }

  function repairCategoryLinks(doc=document,baseUrl=location.href){
    if(!bodyIsCategory(doc))return;
    const nav=doc.querySelector(NAV_SELECTOR);
    if(!nav)return;
    const category=doc.body?.dataset.category||'';
    const home=nav.querySelector('.archive-nav-home');
    if(home)home.setAttribute('href',new URL('../../',baseUrl).href);

    nav.querySelectorAll('.archive-nav-arrow[href]').forEach(link=>{
      const match=link.getAttribute('href').match(/20\d{2}-\d{2}-\d{2}/);
      if(match&&category)link.setAttribute('href',new URL(`../../${match[0]}/${category}/`,baseUrl).href);
    });

    const top=nav.querySelector('a.global-category-link:not([data-category])');
    if(top)top.setAttribute('href',new URL('../#top',baseUrl).href);

    doc.querySelectorAll('.category-bottom-nav a').forEach(link=>{
      if(link.textContent.trim()==='TOP5')link.setAttribute('href',new URL('../#top',baseUrl).href);
    });
  }

  function absolutizeNav(doc=document,baseUrl=location.href){
    const nav=doc.querySelector(NAV_SELECTOR);
    if(!nav)return;
    nav.querySelectorAll('a[href]').forEach(link=>{
      try{link.setAttribute('href',new URL(link.getAttribute('href'),baseUrl).href);}catch(_){}
    });
  }

  function workspaceDate(doc=document){
    return doc.body?.dataset.reportDate||'';
  }

  function isWorkspaceTab(url){
    const date=workspaceDate();
    if(!date||url.origin!==location.origin)return false;
    return url.pathname.includes(`/${date}/`);
  }

  function syncBody(nextBody){
    if(!nextBody)return;
    document.body.classList.toggle('archive-page',nextBody.classList.contains('archive-page'));
    document.body.classList.toggle('category-page',nextBody.classList.contains('category-page'));
    const attrs=['reportDate','category','previous','next'];
    attrs.forEach(key=>{
      const value=nextBody.dataset[key];
      if(value===undefined)delete document.body.dataset[key];
      else document.body.dataset[key]=value;
    });
  }

  function syncNav(nextNav){
    const nav=document.querySelector(NAV_SELECTOR);
    if(!nav||!nextNav)return;

    const currentTabs=[...nav.querySelectorAll('a.global-category-link')];
    const nextTabs=[...nextNav.querySelectorAll('a.global-category-link')];
    currentTabs.forEach((tab,index)=>{
      const next=nextTabs[index];
      if(!next)return;
      tab.classList.toggle('is-active',next.classList.contains('is-active'));
      if(next.hasAttribute('href'))tab.setAttribute('href',next.getAttribute('href'));
    });

    const currentControls=[...nav.querySelectorAll('.archive-nav-controls a[href]')];
    const nextControls=[...nextNav.querySelectorAll('.archive-nav-controls a[href]')];
    currentControls.forEach((link,index)=>{
      const next=nextControls[index];
      if(next)link.setAttribute('href',next.getAttribute('href'));
    });

    const inner=nav.querySelector('.global-category-nav-inner');
    const active=nav.querySelector('.global-category-link.is-active');
    if(inner&&active){
      const left=Math.max(0,active.offsetLeft-inner.clientWidth/2+active.clientWidth/2);
      inner.scrollTo({left,behavior:'auto'});
    }
  }

  function prepareDetails(root=document){
    const details=[...root.querySelectorAll('details')];
    details.forEach(detail=>{
      detail.open=false;
      if(detail.dataset.workspaceAccordion==='1')return;
      detail.dataset.workspaceAccordion='1';
      detail.addEventListener('toggle',()=>{
        if(detail.open)details.forEach(other=>{if(other!==detail)other.open=false;});
      });
    });
  }

  function ensureStyles(nextDoc,targetUrl){
    const loaded=new Set([...document.querySelectorAll('link[rel="stylesheet"][href]')].map(link=>new URL(link.getAttribute('href'),location.href).pathname));
    const pending=[];
    nextDoc.querySelectorAll('link[rel="stylesheet"][href]').forEach(link=>{
      let href;
      try{href=new URL(link.getAttribute('href'),targetUrl).href;}catch(_){return;}
      const pathname=new URL(href).pathname;
      if(loaded.has(pathname))return;
      loaded.add(pathname);
      const clone=document.createElement('link');
      clone.rel='stylesheet';clone.href=href;
      pending.push(new Promise(resolve=>{clone.onload=resolve;clone.onerror=resolve;}));
      document.head.append(clone);
    });
    return Promise.all(pending);
  }

  async function loadWorkspace(target,{push=true}={}){
    const url=target instanceof URL?target:new URL(target,location.href);
    if(!isWorkspaceTab(url)){location.assign(url.href);return;}

    if(controller)controller.abort();
    controller=new AbortController();
    const nav=document.querySelector(NAV_SELECTOR);
    nav?.setAttribute('aria-busy','true');

    try{
      const fetchUrl=new URL(url.href);fetchUrl.hash='';
      const response=await fetch(fetchUrl.href,{credentials:'same-origin',signal:controller.signal});
      if(!response.ok)throw new Error(`HTTP ${response.status}`);
      const html=await response.text();
      const nextDoc=new DOMParser().parseFromString(html,'text/html');
      const nextMain=nextDoc.querySelector('main');
      const currentMain=document.querySelector('main');
      const nextNav=nextDoc.querySelector(NAV_SELECTOR);
      if(!nextMain||!currentMain||!nextNav)throw new Error('workspace shell missing');

      repairCategoryLinks(nextDoc,url.href);
      absolutizeNav(nextDoc,url.href);
      await ensureStyles(nextDoc,url.href);

      if(push)history.pushState({archiveWorkspace:true},'',url.href);
      syncBody(nextDoc.body);
      syncNav(nextNav);
      const imported=document.importNode(nextMain,true);
      currentMain.replaceWith(imported);
      if(nextDoc.title)document.title=nextDoc.title;
      prepareDetails(imported);
      window.scrollTo({top:0,behavior:'auto'});
    }catch(error){
      if(error?.name==='AbortError')return;
      location.assign(url.href);
    }finally{
      nav?.removeAttribute('aria-busy');
    }
  }

  function onClick(event){
    if(event.defaultPrevented||event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;
    const link=event.target.closest(`${NAV_SELECTOR} a.global-category-link[href]`);
    if(!link)return;
    const url=new URL(link.href,location.href);
    if(!isWorkspaceTab(url))return;
    event.preventDefault();
    loadWorkspace(url,{push:true});
  }

  function init(){
    repairCategoryLinks();
    absolutizeNav();
    prepareDetails();
    history.scrollRestoration='manual';
    document.addEventListener('click',onClick);
    window.addEventListener('popstate',()=>loadWorkspace(new URL(location.href),{push:false}));
  }

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});
  else init();
})();
