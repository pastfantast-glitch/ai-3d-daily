document.addEventListener('DOMContentLoaded',async()=>{
  document.body.classList.add('archive-page');
  const date=document.body.dataset.reportDate||document.querySelector('.topline span:last-child')?.textContent.trim()||'';
  const previous=document.body.dataset.previous||'',next=document.body.dataset.next||'';

  // Same canonical renderer as homepage: one source, one semantic hierarchy.
  try{
    const self=[...document.scripts].find(s=>s.src.includes('/daily.js'))?.src||location.href;
    const mod=await import(new URL('canonical-client.js?v=20260823-1',self).href);
    await mod.hydrateCanonicalAnalysis();
  }catch(err){console.warn('Canonical intelligence renderer unavailable',err);}

  const head=document.querySelector('.site-head');if(head&&!head.querySelector('.archive-note')){const note=document.createElement('div');note.className='archive-note';note.textContent='ARCHIVE DATABASE · 當日完整快照';const stats=head.querySelector('.stats');stats?stats.before(note):head.querySelector('.page')?.append(note);}
  const details=[...document.querySelectorAll('details')];details.forEach(d=>d.open=false);details.forEach(d=>d.addEventListener('toggle',()=>{if(d.open)details.forEach(o=>{if(o!==d)o.open=false;});}));document.querySelector('.jumpbar')?.setAttribute('hidden','');
  if(!document.querySelector('.dailybar')){const prev=previous?`<a class="day-link" href="../${previous}/" aria-label="前一日日報">←</a>`:'',nxt=next?`<a class="day-link" href="../${next}/" aria-label="後一日日報">→</a>`:'',sections=[['top','TOP 5'],['categories','分類追蹤'],['try','實測']].filter(([id])=>document.getElementById(id)),bar=document.createElement('nav');bar.className='dailybar';bar.setAttribute('aria-label','歷史日報導覽');bar.innerHTML=`<div class="dailybar-inner"><div class="daily-id"><a class="daily-home" href="../">← 首頁</a><div class="date-nav">${prev}<span class="daily-date">${date}</span>${nxt}</div></div><div class="daily-nav">${sections.map(([id,label])=>`<a href="#${id}" data-section="${id}">${label}</a>`).join('')}</div></div>`;document.body.prepend(bar);}
  const links=[...document.querySelectorAll('.daily-nav a[data-section]')],sections=links.map(a=>document.getElementById(a.dataset.section)).filter(Boolean),activate=id=>links.forEach(a=>a.classList.toggle('is-active',a.dataset.section===id));let ticking=false;const update=()=>{const y=window.scrollY+84;let current=sections[0]?.id||'top';sections.forEach(s=>{if(s.offsetTop<=y)current=s.id;});activate(current);ticking=false;};window.addEventListener('scroll',()=>{if(!ticking){requestAnimationFrame(update);ticking=true;}},{passive:true});update();document.querySelectorAll('a[target="_blank"]').forEach(a=>{const rel=new Set((a.getAttribute('rel')||'').split(/\s+/).filter(Boolean));rel.add('noopener');rel.add('noreferrer');a.setAttribute('rel',[...rel].join(' '));});
});
