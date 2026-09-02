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

  // Historical Intelligence Library: text search + V2 category + date window.
  const archive=document.querySelector('.history-list');
  const historySearch=document.querySelector('.history-search');
  if(archive&&historySearch){
    let category='all',range='all';
    const entries=[...archive.querySelectorAll('.history-entry')];
    const daysBetween=(newest,date)=>Math.floor((new Date(newest+'T00:00:00')-new Date(date+'T00:00:00'))/86400000);
    const newest=entries.map(x=>x.dataset.historyDate).sort().at(-1)||'';
    const applyHistory=()=>{
      const query=historySearch.value.trim().toLowerCase();let visible=0;
      entries.forEach(a=>{
        const cats=(a.dataset.historyCategories||'').split(/\s+/).filter(Boolean);
        const inCategory=category==='all'||cats.includes(category);
        const inRange=range==='all'||daysBetween(newest,a.dataset.historyDate)<Number(range);
        const inSearch=!query||(a.dataset.historySearch||a.textContent.toLowerCase()).includes(query);
        a.hidden=!(inCategory&&inRange&&inSearch);if(!a.hidden)visible++;
      });
      archive.querySelectorAll('.archive-month').forEach(m=>{const any=[...m.querySelectorAll('.history-entry')].some(a=>!a.hidden);m.hidden=!any;if(any&&(query||category!=='all'||range!=='all'))m.open=true;});
      archive.querySelectorAll('.archive-year').forEach(y=>{const any=[...y.querySelectorAll('.archive-month')].some(m=>!m.hidden);y.hidden=!any;if(any&&(query||category!=='all'||range!=='all'))y.open=true;});
      const empty=archive.querySelector('.history-empty');if(empty)empty.hidden=visible!==0;
    };
    historySearch.addEventListener('input',applyHistory);
    document.querySelectorAll('[data-history-category]').forEach(btn=>btn.addEventListener('click',()=>{category=btn.dataset.historyCategory;document.querySelectorAll('[data-history-category]').forEach(x=>x.classList.toggle('is-active',x===btn));applyHistory();}));
    document.querySelectorAll('[data-history-range]').forEach(btn=>btn.addEventListener('click',()=>{range=btn.dataset.historyRange;document.querySelectorAll('[data-history-range]').forEach(x=>x.classList.toggle('is-active',x===btn));applyHistory();}));
  }

  const STORE='ai3d-preferences-v1';let pref={votes:{},tags:{}};
  try{pref=Object.assign(pref,JSON.parse(localStorage.getItem(STORE)||'{}'));pref.votes=pref.votes||{};pref.tags=pref.tags||{};}catch(_){}
  const save=()=>{try{localStorage.setItem(STORE,JSON.stringify(pref));}catch(_){}};
  const hash=s=>{let h=2166136261;for(let i=0;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,16777619);}return(h>>>0).toString(36);};
  const tagsFor=card=>{const pills=[...card.querySelectorAll('.pill')].map(x=>x.textContent.trim()).filter(Boolean),title=(card.querySelector('h2,h4')?.textContent||'').toUpperCase(),inferred=[];['BLENDER','UNITY','UNREAL','CHARACTER','ENVIRONMENT','MATERIAL','SHADER','NPR','TOON','AI 3D','RIG','ANIMATION','SUBSTANCE','GEOMETRY NODES'].forEach(t=>{if(title.includes(t)||pills.some(p=>p.toUpperCase().includes(t)))inferred.push(t);});return[...new Set([...pills,...inferred])].slice(0,8);};
  cards.forEach(card=>{if(card.querySelector('.preference-vote'))return;const source=card.querySelector('a.source')?.href||'',title=card.querySelector('h2,h4')?.textContent?.trim()||'';if(!title)return;const id=card.dataset.intelId||hash(source||title),tags=tagsFor(card),wrap=document.createElement('div');wrap.className='preference-vote';wrap.innerHTML='<span>這類內容：</span><button type="button" data-v="1" aria-label="喜歡這類內容">👍</button><button type="button" data-v="-1" aria-label="少看這類內容">👎</button>';const paint=()=>{const v=pref.votes[id]?.vote||0;wrap.querySelector('[data-v="1"]').classList.toggle('is-up',v===1);wrap.querySelector('[data-v="-1"]').classList.toggle('is-down',v===-1);};wrap.querySelectorAll('button').forEach(btn=>btn.addEventListener('click',()=>{const next=Number(btn.dataset.v),old=pref.votes[id]?.vote||0,vote=old===next?0:next;if(old)(pref.votes[id]?.tags||[]).forEach(t=>pref.tags[t]=(pref.tags[t]||0)-old);if(vote){tags.forEach(t=>pref.tags[t]=(pref.tags[t]||0)+vote);pref.votes[id]={vote,tags,title,source,updatedAt:new Date().toISOString()};}else delete pref.votes[id];Object.keys(pref.tags).forEach(t=>{if(!pref.tags[t])delete pref.tags[t];});save();paint();}));const anchor=card.querySelector('a.source');if(anchor)anchor.insertAdjacentElement('afterend',wrap);else card.appendChild(wrap);paint();});
  window.ai3dPreferenceProfile=()=>JSON.parse(JSON.stringify(pref));
});
