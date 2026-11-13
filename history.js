document.addEventListener('DOMContentLoaded',()=>{
  // History is a portal, not a dated archive workspace. Its global TOP5/category
  // tabs always return to today's current workspace. A dated archive mode starts
  // only after the user explicitly selects a date from the History list.
  const nav=document.querySelector('nav.global-category-nav');
  if(nav){
    nav.querySelectorAll('a.global-category-link[data-category]').forEach(link=>{
      const category=link.dataset.category||'';
      if(category)link.setAttribute('href',`../?view=${encodeURIComponent(category)}`);
    });
    const top=nav.querySelector('a.global-category-link:not([data-category]):not(.global-history-link)');
    if(top)top.setAttribute('href','../#today');
  }

  const archive=document.querySelector('.history-list');
  const historySearch=document.querySelector('.history-search');
  if(!archive||!historySearch)return;

  let category='all',range='all';
  const entries=[...archive.querySelectorAll('.history-entry')];
  const daysBetween=(newest,date)=>Math.floor((new Date(newest+'T00:00:00')-new Date(date+'T00:00:00'))/86400000);
  const newest=entries.map(x=>x.dataset.historyDate).sort().at(-1)||'';

  let index=[];try{index=JSON.parse(document.querySelector('#history-article-index')?.textContent||'[]');}catch(_){}
  const normalize=items=>items.map(item=>({...item,searchText:`${item.title} ${item.summary} ${item.date} ${item.sourceDate}`.toLowerCase()}));
  let articles=Array.isArray(index)?normalize(index):[];
  const monthly=Array.isArray(index)?[]:(index.schema_version===2?index.months:[])||[];
  const loaded=new Map();
  async function loadMonths(){
    const required=monthly.filter(m=>range==='all'||daysBetween(newest,`${m.month}-01`)<=Number(range)+31);
    // Bounded concurrency and cached immutable month indexes; no fetch for archive browsing.
    const queue=required.filter(m=>!loaded.has(m.month));
    await Promise.all(Array.from({length:Math.min(3,queue.length)},async()=>{
      while(queue.length){const entry=queue.shift();
        const url=new URL(entry.url,location.href);
        if(url.origin!==location.origin||!/^indexes\/20\d{2}-\d{2}\.json$/.test(entry.url))throw new Error('invalid index URL');
        const response=await fetch(url);if(!response.ok)throw new Error(`index HTTP ${response.status}`);
        const rows=await response.json();if(!Array.isArray(rows)||rows.length!==entry.count)throw new Error('index count mismatch');
        loaded.set(entry.month,normalize(rows));
      }
    }));
    articles=required.flatMap(m=>loaded.get(m.month)||[]);
  }
  const results=document.querySelector('.history-article-results');
  let matched=[],limit=50;
  function renderArticles(){
    if(!results)return;
    const list=results.querySelector('.library-list');list.replaceChildren();
    matched.slice(0,limit).forEach(item=>{
      const row=document.createElement('article');row.className='library-row';
      const link=document.createElement('a');link.className='library-link';link.href=item.url;link.textContent=item.title;
      const meta=document.createElement('p');meta.className='library-meta';meta.textContent=`收錄 ${item.date} · 來源 ${item.sourceDate||'日期待核對'}`;
      const summary=document.createElement('p');summary.className='library-summary';summary.textContent=item.summary;
      row.append(link,meta,summary);list.append(row);
    });
    results.querySelector('.history-result-count').textContent=matched.length?`找到 ${matched.length} 篇，顯示 ${Math.min(limit,matched.length)} 篇`:'找不到符合條件的文章，請調整搜尋或篩選條件。';
    results.querySelector('.history-load-more').hidden=matched.length<=limit;
  }
  results?.querySelector('.history-load-more').addEventListener('click',()=>{limit+=50;renderArticles();});
  let requestId=0;
  const applyHistory=async()=>{
    const request=++requestId;
    const query=historySearch.value.trim().toLowerCase();
    const articleMode=Boolean(query||category!=='all');
    if(results){
      results.hidden=!articleMode;archive.hidden=articleMode;
      if(articleMode&&monthly.length){
        results.querySelector('.history-result-count').textContent='載入月份索引…';
        results.querySelector('.library-list').replaceChildren();
        results.querySelector('.history-load-more').hidden=true;
        try{await loadMonths();}catch(error){
          if(request===requestId)results.querySelector('.history-result-count').textContent='月份索引載入失敗，請重新輸入或切換篩選重試；也可清空搜尋瀏覽日期。';
          return;
        }
        if(request!==requestId)return;
      }
      matched=articles.filter(item=>(category==='all'||item.category===category)&&
        (range==='all'||daysBetween(newest,item.date)<Number(range))&&
        (!query||item.searchText.includes(query)));
      limit=50;renderArticles();
    }
    let visible=0;
    entries.forEach(a=>{
      const cats=(a.dataset.historyCategories||'').split(/\s+/).filter(Boolean);
      const inCategory=category==='all'||cats.includes(category);
      const inRange=range==='all'||daysBetween(newest,a.dataset.historyDate)<Number(range);
      const inSearch=!query||(a.dataset.historySearch||a.textContent.toLowerCase()).includes(query);
      a.hidden=!(inCategory&&inRange&&inSearch);
      if(!a.hidden)visible++;
    });
    archive.querySelectorAll('.archive-month').forEach(month=>{
      const any=[...month.querySelectorAll('.history-entry')].some(a=>!a.hidden);
      month.hidden=!any;
      if(any&&(query||category!=='all'||range!=='all'))month.open=true;
    });
    archive.querySelectorAll('.archive-year').forEach(year=>{
      const any=[...year.querySelectorAll('.archive-month')].some(month=>!month.hidden);
      year.hidden=!any;
      if(any&&(query||category!=='all'||range!=='all'))year.open=true;
    });
    const empty=archive.querySelector('.history-empty');
    if(empty)empty.hidden=visible!==0;
  };

  let searchTimer;historySearch.addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(applyHistory,150);});
  document.querySelectorAll('[data-history-category]').forEach(btn=>btn.addEventListener('click',()=>{
    category=btn.dataset.historyCategory;
    document.querySelectorAll('[data-history-category]').forEach(x=>x.classList.toggle('is-active',x===btn));
    applyHistory();
  }));
  document.querySelectorAll('[data-history-range]').forEach(btn=>btn.addEventListener('click',()=>{
    range=btn.dataset.historyRange;
    document.querySelectorAll('[data-history-range]').forEach(x=>x.classList.toggle('is-active',x===btn));
    applyHistory();
  }));
});