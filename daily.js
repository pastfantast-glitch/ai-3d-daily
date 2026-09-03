document.addEventListener('DOMContentLoaded',async()=>{
  document.body.classList.add('archive-page');
  const date=document.body.dataset.reportDate||document.querySelector('.topline span:last-child')?.textContent.trim()||'';
  const previous=document.body.dataset.previous||'',next=document.body.dataset.next||'';

  // Same canonical renderer as homepage: Full Analysis + local Visual Evidence share one stable-ID source.
  // The module inherits daily.js' cache-bust token, keeping archive runtime and shell revisions aligned.
  try{
    const self=[...document.scripts].find(s=>s.src.includes('/daily.js'))?.src||location.href;
    const shellUrl=new URL(self,location.href);
    const token=shellUrl.searchParams.get('v')||(date||'current').replaceAll('-','');
    const moduleUrl=new URL('canonical-client.js',self);
    moduleUrl.searchParams.set('v',token);
    const mod=await import(moduleUrl.href);
    await mod.hydrateCanonicalAnalysis();
  }catch(err){console.warn('Canonical intelligence renderer unavailable',err);}

  const head=document.querySelector('.site-head');if(head&&!head.querySelector('.archive-note')){const note=document.createElement('div');note.className='archive-note';note.textContent='ARCHIVE DATABASE · 當日完整快照';const stats=head.querySelector('.stats');stats?stats.before(note):head.querySelector('.page')?.append(note);}
  const details=[...document.querySelectorAll('details')];details.forEach(d=>d.open=false);details.forEach(d=>d.addEventListener('toggle',()=>{if(d.open)details.forEach(o=>{if(o!==d)o.open=false;});}));document.querySelector('.jumpbar')?.setAttribute('hidden','');

  // Historical reports use one sticky bar only: date controls on the left, the
  // shared TOP5/category navigation on the right. Remove any legacy second bar.
  document.querySelectorAll('.dailybar').forEach(el=>el.remove());
  const nav=document.querySelector('nav.global-category-nav'),inner=nav?.querySelector('.global-category-nav-inner');
  if(inner&&!inner.querySelector('.archive-nav-controls')){
    const controls=document.createElement('div');controls.className='archive-nav-controls';
    const prev=previous?`<a class="archive-nav-arrow" href="../${previous}/" aria-label="前一日日報">←</a>`:'';
    const nxt=next?`<a class="archive-nav-arrow" href="../${next}/" aria-label="後一日日報">→</a>`:'';
    controls.innerHTML=`<a class="archive-nav-home" href="../">← 首頁</a><div class="archive-nav-date">${prev}<span>${date}</span>${nxt}</div>`;
    inner.prepend(controls);
    const divider=document.createElement('span');divider.className='archive-nav-divider';divider.setAttribute('aria-hidden','true');controls.after(divider);
  }

  document.querySelectorAll('a[target="_blank"]').forEach(a=>{const rel=new Set((a.getAttribute('rel')||'').split(/\s+/).filter(Boolean));rel.add('noopener');rel.add('noreferrer');a.setAttribute('rel',[...rel].join(' '));});
});
