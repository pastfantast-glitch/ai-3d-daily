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

  let articles=[];try{articles=JSON.parse(document.querySelector('#history-article-index')?.textContent||'[]');}catch(_){}
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
  const applyHistory=()=>{
    const query=historySearch.value.trim().toLowerCase();
    const articleMode=Boolean(query||category!=='all');
    if(results){
      results.hidden=!articleMode;archive.hidden=articleMode;
      matched=articles.filter(item=>(category==='all'||item.category===category)&&
        (range==='all'||daysBetween(newest,item.date)<Number(range))&&
        (!query||`${item.title} ${item.summary} ${item.date} ${item.sourceDate}`.toLowerCase().includes(query)));
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

  historySearch.addEventListener('input',applyHistory);
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