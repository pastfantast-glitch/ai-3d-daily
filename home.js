document.addEventListener('DOMContentLoaded',()=>{
  const search=document.querySelector('#news-search'),filters=[...document.querySelectorAll('.filter')],items=[...document.querySelectorAll('.searchable')],empty=document.querySelector('#empty-state');let active='all';
  const apply=()=>{const q=(search?.value||'').trim().toLowerCase();let shown=0;items.forEach(item=>{const cats=(item.dataset.category||'').split(/\s+/),text=(item.dataset.search||item.textContent||'').toLowerCase(),ok=(active==='all'||cats.includes(active))&&(!q||text.includes(q));item.hidden=!ok;if(ok)shown++;});if(empty)empty.hidden=shown!==0;};
  filters.forEach(btn=>btn.addEventListener('click',()=>{active=btn.dataset.filter||'all';filters.forEach(x=>x.classList.toggle('is-active',x===btn));apply();}));search?.addEventListener('input',apply);

  // HARD QA: exactly one full-analysis block per information card.
  // Remove any legacy/generated duplicate first, regardless of its class or visual style.
  document.querySelectorAll('.top-item, .more-card').forEach(card=>{
    const candidates=[...card.querySelectorAll('details')].filter(d=>{
      const label=(d.querySelector('summary')?.textContent||'').trim();
      return label.includes('完整分析');
    });
    candidates.slice(1).forEach(d=>d.remove());
    const primary=candidates[0];
    if(primary){
      primary.classList.add('home-full-analysis');
      const body=primary.querySelector('.detail-body');
      if(body)body.classList.add('home-analysis-body');
    }
  });

  // Final defensive pass: a legacy injected analysis may use a wrapper rather than <details>.
  document.querySelectorAll('.top-item, .more-card').forEach(card=>{
    const blocks=[...card.querySelectorAll('.home-full-analysis')];
    blocks.slice(1).forEach(el=>el.remove());
  });

  const all=[...document.querySelectorAll('.home-full-analysis')];
  all.forEach(d=>d.addEventListener('toggle',()=>{if(d.open)all.forEach(o=>{if(o!==d)o.open=false;});}));
});