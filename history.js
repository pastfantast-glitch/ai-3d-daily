document.addEventListener('DOMContentLoaded',()=>{
  const archive=document.querySelector('.history-list');
  const historySearch=document.querySelector('.history-search');
  if(!archive||!historySearch)return;

  let category='all',range='all';
  const entries=[...archive.querySelectorAll('.history-entry')];
  const daysBetween=(newest,date)=>Math.floor((new Date(newest+'T00:00:00')-new Date(date+'T00:00:00'))/86400000);
  const newest=entries.map(x=>x.dataset.historyDate).sort().at(-1)||'';

  const applyHistory=()=>{
    const query=historySearch.value.trim().toLowerCase();
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