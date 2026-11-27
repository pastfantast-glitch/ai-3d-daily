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
document.addEventListener('DOMContentLoaded',async()=>{
  const NAV_SELECTOR='nav.global-category-nav';
  const nav=document.querySelector(NAV_SELECTOR);
  const homeMain=document.querySelector('main.home-main');
  if(!nav||!homeMain||!document.body.classList.contains('home-page'))return;

  const initialTitle=document.title;
  const rootUrl=new URL('./',location.href);rootUrl.search='';rootUrl.hash='';
  const dateFromNav=[...nav.querySelectorAll('a[data-category][href]')].map(a=>a.getAttribute('href')?.match(/20\d{2}-\d{2}-\d{2}/)?.[0]).find(Boolean)||'';
  const reportDate=document.body.dataset.reportDate||document.querySelector('.week-asof')?.textContent.trim()||dateFromNav;
  let controller=null;
  let categoryMain=null,managed=null;
  try{const mod=await import('./category-navigation.mjs?v=20261127-categories1');managed=await mod.prepareNavigation(nav,reportDate);}catch(error){console.warn('Managed navigation unavailable; retaining verified static categories',error);}


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
    if(!managed?.has(category)&&![...nav.querySelectorAll('[data-category]')].some(link=>link.dataset.category===category)){
      showTop({push:false});
      return;
    }
    if(managed?.has(category)){
      if(controller)controller.abort();controller=null;
      const next=managed.render(category);prepareCategoryMain(next);
      if(categoryMain)categoryMain.replaceWith(next);else homeMain.insertAdjacentElement('afterend',next);
      categoryMain=next;homeMain.hidden=true;setActive(category);document.title=`${managed.label(category)}｜${reportDate}｜AI 3D Daily`;
      if(push){const url=new URL(rootUrl);url.searchParams.set('view',category);history.pushState({currentWorkspace:true,view:category},'',url);}
      window.scrollTo({top:0,behavior:'auto'});return;
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
      if(!category)document.dispatchEvent(new Event('home-library-reset'));
      category?showCategory(category,{push:true}):showTop({push:true});
      return;
    }
    if(event.target.closest('.edition-links a[href="#all-intelligence"]')){
      event.preventDefault();
      const target=new URL(rootUrl.href);target.hash='all-intelligence';
      history.pushState({currentWorkspace:true,view:'top5'},'',target.href);
      showTop({push:false});
      document.querySelector('#all-intelligence')?.scrollIntoView({block:'start'});
      return;
    }
    const card=event.target.closest('a.category-nav-card[href]');
    if(card){const category=categoryFromLink(card);if(category){event.preventDefault();showCategory(category,{push:true});}}
  });

  window.addEventListener('popstate',()=>{
    const view=new URL(location.href).searchParams.get('view')||'top5';
    view==='top5'?showTop({push:false}):showCategory(view,{push:false});
    if(view==='top5'&&location.hash==='#all-intelligence')document.querySelector('#all-intelligence')?.scrollIntoView({block:'start'});
  });

  const initialView=new URL(location.href).searchParams.get('view');
  if(initialView&&initialView!=='top5')showCategory(initialView,{push:false});
});

document.addEventListener('DOMContentLoaded',()=>{
  const library=document.querySelector('.today-library');
  if(!library||!library.matches('#more[data-card-library="all"]'))return;
  const topSection=document.querySelector('#today');
  const topList=topSection.querySelector('.top-list');
  const grid=library.querySelector('.more-grid');
  const featured=[...topList.querySelectorAll('[data-library-id]')];
  const rows=[...featured,...grid.querySelectorAll('[data-library-id]')].sort((a,b)=>Number(a.dataset.rank)-Number(b.dataset.rank));
  const featuredSet=new Set(featured);
  const searchable=new Map(rows.map(row=>[row,row.textContent.toLocaleLowerCase()]));
  const search=library.querySelector('#today-search');
  const category=library.querySelector('#today-category');
  const freshness=library.querySelector('#today-freshness');
  const more=library.querySelector('#today-load-more');
  let limit=10;
  function filter(){
    const query=search.value.trim().toLocaleLowerCase();
    const kind=library.querySelector('#today-kind')?.value||'all';
    const active=Boolean(query||category.value!=='all'||freshness.value!=='all'||kind!=='all');
    topSection.hidden=active;
    featured.forEach(card=>{
      card.classList.toggle('top-item',!active);card.classList.toggle('more-card',active);
      if(!active){card.hidden=false;topList.append(card);}
    });
    const candidates=rows.filter(row=>active||!featuredSet.has(row));
    candidates.forEach(row=>grid.append(row));
    const matches=candidates.filter(row=>searchable.get(row).includes(query)&&
      (category.value==='all'||(row.dataset.categoryIds||row.dataset.category||'').split(' ').includes(category.value))&&
      (freshness.value==='all'||row.dataset.freshness===freshness.value)&&
      (kind==='all'||row.dataset.contentKind===kind));
    const visible=new Set(matches.slice(0,limit));
    candidates.forEach(row=>{row.hidden=!visible.has(row);});
    library.querySelector('#today-result-count').textContent=active?
      `符合 ${matches.length} 篇，已顯示 ${visible.size} 篇（搜尋本期全部 ${rows.length} 篇）`:
      `精選之外共 ${matches.length} 篇，已顯示 ${visible.size} 篇`;
    library.querySelector('#today-empty').hidden=matches.length!==0;
    more.hidden=limit>=matches.length;
    more.textContent=`顯示更多（還有 ${Math.max(0,matches.length-limit)} 篇）`;
  }
  const reset=()=>{limit=10;filter();};
  let searchTimer;search.addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(reset,120);});
  library.addEventListener('change',event=>{if(event.target.matches('select'))reset();});
  document.addEventListener('home-library-reset',()=>{
    clearTimeout(searchTimer);search.value='';
    library.querySelectorAll('select').forEach(select=>{select.value='all';});
    reset();
  });
  library.addEventListener('content-kind-ready',filter);
  more.addEventListener('click',()=>{limit+=10;filter();});
  const toggle=document.createElement('button');toggle.type='button';toggle.className='reading-mode';
  let compact=false;try{compact=localStorage.getItem('ai3d-reading-mode')==='compact';}catch(_){}
  function paint(){document.body.classList.toggle('is-compact',compact);toggle.setAttribute('aria-pressed',String(compact));toggle.textContent=compact?'顯示文章圖片':'精簡閱讀';}
  toggle.addEventListener('click',()=>{compact=!compact;paint();try{localStorage.setItem('ai3d-reading-mode',compact?'compact':'visual');}catch(_){}});
  document.querySelector('.edition-links')?.append(toggle);paint();filter();
});

// Source freshness and collection date are different facts. Never label an old
// announcement as today's news simply because this is its first appearance.
document.addEventListener('DOMContentLoaded',async()=>{
  const date=document.body.dataset.reportDate;
  const library=document.querySelector('.today-library');
  if(!date||!library)return;
  const intro=document.querySelector('.edition-summary');
  const heading=library.querySelector('h2');
  if(heading)heading.textContent='今天還有什麼';
  if(intro)intro.textContent='收錄日期與來源發布日期分別標示。';
  try{
    const response=await fetch(new URL(`data/daily/${date}.json`,location.href));
    if(!response.ok)throw new Error('canonical unavailable');
    const data=await response.json();
    if(data.date!==date||!Array.isArray(data.items))throw new Error('edition mismatch');
    const labels={news:'新消息（近 7 日來源）',practice:'近期實作／參考',historical:'歷史精選',unknown:'日期待核對'};
    const counts={news:0,practice:0,historical:0,unknown:0};let sameDay=0;
    data.items.forEach(item=>{
      const dates=[item.source_published_at];
      const match=(item.source_url||'').match(/\/(20\d{2})\/(\d{2})(?:\/|$)/);
      if(match){const end=new Date(Date.UTC(Number(match[1]),Number(match[2]),0));dates.push(end.toISOString().slice(0,10));}
      const valid=dates.filter(d=>/^20\d{2}-\d{2}-\d{2}$/.test(d||'')).sort();
      const source=valid[0];const age=source?(Date.parse(date)-Date.parse(source))/86400000:NaN;
      const news=/發布|更新|推出|發表|新研究|release|launch|announc/i.test(item.title||'');
      const kind=!Number.isFinite(age)||age<0?'unknown':age>180?'historical':item.content_kind==='historical'?'historical':age<=7&&(item.content_kind==='news'||(!item.content_kind&&news))?'news':'practice';
      counts[kind]++;if(source===date)sameDay++;
      const row=document.querySelector(`[data-library-id="${CSS.escape(item.id)}"]`);
      if(row){row.dataset.contentKind=kind;const tag=document.createElement('span');tag.className='content-kind';tag.textContent=` · ${labels[kind]}`;row.querySelector('.library-meta')?.append(tag);}
    });
    const mix=document.createElement('p');mix.className='content-mix';mix.setAttribute('role','status');
    mix.textContent=Object.entries(counts).filter(([key,n])=>key!=='unknown'||n).map(([key,n])=>`${labels[key]} ${n} 篇`).join(' · ');
    library.querySelector('.library-controls').before(mix);
    const select=document.createElement('select');select.id='today-kind';select.setAttribute('aria-label','篩選內容類型');
    for(const [value,label] of [['all','全部內容類型'],...Object.entries(labels)]){const option=document.createElement('option');option.value=value;option.textContent=label;select.append(option);}
    library.querySelector('.library-controls').append(select);
    if(intro)intro.textContent=`本期有 ${sameDay} 篇來源發布於同日。收錄不代表事件發生於當日。`;
    library.dispatchEvent(new Event('content-kind-ready'));
    const explanation=document.createElement('p');explanation.className='library-meta';
    explanation.textContent='新消息依近 7 日來源日期及標題更新訊號分類；其他近 180 日內容列為實作／參考。超過 180 日列為歷史精選，請留意原始年份與版本。';
    mix.after(explanation);
  }catch(error){console.warn('Content mix unavailable',error);}
});
