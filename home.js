document.addEventListener('DOMContentLoaded',async()=>{
  document.querySelectorAll('a[target="_blank"]').forEach(a=>a.rel='noopener noreferrer');
  const cards=[...document.querySelectorAll('.top-item, .more-card')];

  // Canonical Full Analysis is hydrated by one shared renderer used by both views.
  try{
    const self=[...document.scripts].find(s=>s.src.includes('/home.js'))?.src||location.href;
    const mod=await import(new URL('canonical-client.js?v=20260823-1',self).href);
    await mod.hydrateCanonicalAnalysis();
  }catch(err){console.warn('Canonical intelligence renderer unavailable',err);}

  // Keep exactly one analysis block and one open block at a time.
  cards.forEach(card=>{const all=[...card.querySelectorAll('details')];all.slice(1).forEach(d=>d.remove());});
  const analyses=[...document.querySelectorAll('.home-full-analysis')];
  analyses.forEach(d=>d.addEventListener('toggle',()=>{if(d.open)analyses.forEach(other=>{if(other!==d)other.open=false;});}));

  const STORE='ai3d-preferences-v1';let pref={votes:{},tags:{}};
  try{pref=Object.assign(pref,JSON.parse(localStorage.getItem(STORE)||'{}'));pref.votes=pref.votes||{};pref.tags=pref.tags||{};}catch(_){}
  const save=()=>{try{localStorage.setItem(STORE,JSON.stringify(pref));}catch(_){}};
  const hash=s=>{let h=2166136261;for(let i=0;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,16777619);}return(h>>>0).toString(36);};
  const tagsFor=card=>{const pills=[...card.querySelectorAll('.pill')].map(x=>x.textContent.trim()).filter(Boolean),title=(card.querySelector('h2,h4')?.textContent||'').toUpperCase(),inferred=[];['BLENDER','UNITY','UNREAL','CHARACTER','ENVIRONMENT','MATERIAL','SHADER','NPR','TOON','AI 3D','RIG','ANIMATION','SUBSTANCE','GEOMETRY NODES'].forEach(t=>{if(title.includes(t)||pills.some(p=>p.toUpperCase().includes(t)))inferred.push(t);});return[...new Set([...pills,...inferred])].slice(0,8);};
  cards.forEach(card=>{if(card.querySelector('.preference-vote'))return;const source=card.querySelector('a.source')?.href||'',title=card.querySelector('h2,h4')?.textContent?.trim()||'';if(!title)return;const id=card.dataset.intelId||hash(source||title),tags=tagsFor(card),wrap=document.createElement('div');wrap.className='preference-vote';wrap.innerHTML='<span>這類內容：</span><button type="button" data-v="1" aria-label="喜歡這類內容">👍</button><button type="button" data-v="-1" aria-label="少看這類內容">👎</button>';const paint=()=>{const v=pref.votes[id]?.vote||0;wrap.querySelector('[data-v="1"]').classList.toggle('is-up',v===1);wrap.querySelector('[data-v="-1"]').classList.toggle('is-down',v===-1);};wrap.querySelectorAll('button').forEach(btn=>btn.addEventListener('click',()=>{const next=Number(btn.dataset.v),old=pref.votes[id]?.vote||0,vote=old===next?0:next;if(old)(pref.votes[id]?.tags||[]).forEach(t=>pref.tags[t]=(pref.tags[t]||0)-old);if(vote){tags.forEach(t=>pref.tags[t]=(pref.tags[t]||0)+vote);pref.votes[id]={vote,tags,title,source,updatedAt:new Date().toISOString()};}else delete pref.votes[id];Object.keys(pref.tags).forEach(t=>{if(!pref.tags[t])delete pref.tags[t];});save();paint();}));const anchor=card.querySelector('a.source');if(anchor)anchor.insertAdjacentElement('afterend',wrap);else card.appendChild(wrap);paint();});
  window.ai3dPreferenceProfile=()=>JSON.parse(JSON.stringify(pref));
});
