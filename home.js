document.addEventListener('DOMContentLoaded',()=>{
  const search=document.querySelector('#news-search'),filters=[...document.querySelectorAll('.filter')],items=[...document.querySelectorAll('.searchable')],empty=document.querySelector('#empty-state');let active='all';
  const apply=()=>{const q=(search?.value||'').trim().toLowerCase();let shown=0;items.forEach(item=>{const cats=(item.dataset.category||'').split(/\s+/),text=(item.dataset.search||item.textContent||'').toLowerCase(),ok=(active==='all'||cats.includes(active))&&(!q||text.includes(q));item.hidden=!ok;if(ok)shown++;});if(empty)empty.hidden=shown!==0;};
  filters.forEach(btn=>btn.addEventListener('click',()=>{active=btn.dataset.filter||'all';filters.forEach(x=>x.classList.toggle('is-active',x===btn));apply();}));search?.addEventListener('input',apply);

  // The HTML owns the analysis content. JS only normalizes styling and behavior.
  // One information card must render exactly one full-analysis block.
  document.querySelectorAll('.top-item details, .more-card details').forEach(d=>{
    d.classList.add('home-full-analysis');
    const body=d.querySelector('.detail-body');
    if(body)body.classList.add('home-analysis-body');
  });

  // Defensive QA for legacy/generated markup: keep only the first analysis block.
  document.querySelectorAll('.top-item, .more-card').forEach(card=>{
    const analyses=[...card.querySelectorAll(':scope details')];
    analyses.slice(1).forEach(d=>d.remove());
  });

  const all=[...document.querySelectorAll('.home-full-analysis')];
  all.forEach(d=>d.addEventListener('toggle',()=>{if(d.open)all.forEach(o=>{if(o!==d)o.open=false;});}));
});