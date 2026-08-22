document.addEventListener('DOMContentLoaded',()=>{
  const search=document.querySelector('#news-search'),filters=[...document.querySelectorAll('.filter')],items=[...document.querySelectorAll('.searchable')],empty=document.querySelector('#empty-state');let active='all';
  const apply=()=>{const q=(search?.value||'').trim().toLowerCase();let shown=0;items.forEach(item=>{const cats=(item.dataset.category||'').split(/\s+/),text=(item.dataset.search||item.textContent||'').toLowerCase(),ok=(active==='all'||cats.includes(active))&&(!q||text.includes(q));item.hidden=!ok;if(ok)shown++;});if(empty)empty.hidden=shown!==0;};
  filters.forEach(btn=>btn.addEventListener('click',()=>{active=btn.dataset.filter||'all';filters.forEach(x=>x.classList.toggle('is-active',x===btn));apply();}));search?.addEventListener('input',apply);

  // HARD QA: exactly one full-analysis block per information card.
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

  document.querySelectorAll('.top-item, .more-card').forEach(card=>{
    const blocks=[...card.querySelectorAll('.home-full-analysis')];
    blocks.slice(1).forEach(el=>el.remove());
  });

  const all=[...document.querySelectorAll('.home-full-analysis')];
  all.forEach(d=>d.addEventListener('toggle',()=>{if(d.open)all.forEach(o=>{if(o!==d)o.open=false;});}));

  // Lightweight local preference voting. No account, no public counts.
  const STORE='ai3d-preferences-v1';
  let pref={votes:{},tags:{}};
  try{pref=Object.assign(pref,JSON.parse(localStorage.getItem(STORE)||'{}'));pref.votes=pref.votes||{};pref.tags=pref.tags||{};}catch(_){ }
  const save=()=>{try{localStorage.setItem(STORE,JSON.stringify(pref));}catch(_){}};
  const hash=s=>{let h=2166136261;for(let i=0;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,16777619);}return (h>>>0).toString(36);};
  const tagsFor=card=>{
    const pills=[...card.querySelectorAll('.pill')].map(x=>x.textContent.trim()).filter(Boolean);
    const title=(card.querySelector('h2,h4')?.textContent||'').toUpperCase();
    const inferred=[];
    ['BLENDER','UNITY','UNREAL','CHARACTER','ENVIRONMENT','MATERIAL','SHADER','NPR','TOON','AI 3D','RIG','ANIMATION','SUBSTANCE','GEOMETRY NODES'].forEach(t=>{if(title.includes(t)||pills.some(p=>p.toUpperCase().includes(t)))inferred.push(t);});
    return [...new Set([...pills,...inferred])].slice(0,8);
  };
  const style=document.createElement('style');style.textContent='.preference-vote{display:flex;align-items:center;gap:7px;margin-top:12px}.preference-vote span{font-size:.68rem;color:#7f8ba0;margin-right:2px}.preference-vote button{appearance:none;border:1px solid #2a3850;background:#101927;color:#9eabcb;border-radius:8px;padding:5px 9px;font-size:.76rem;line-height:1;cursor:pointer}.preference-vote button:hover{border-color:#596985;color:#d8e0ef}.preference-vote button.is-up{background:#15352f;border-color:#2a6a56;color:#7fe0ba}.preference-vote button.is-down{background:#3a2027;border-color:#6a3340;color:#ff9aaa}';document.head.appendChild(style);
  document.querySelectorAll('.top-item, .more-card').forEach(card=>{
    if(card.querySelector('.preference-vote'))return;
    const source=card.querySelector('a.source')?.href||'';
    const title=card.querySelector('h2,h4')?.textContent?.trim()||'';
    if(!title)return;
    const id=hash(source||title),tags=tagsFor(card),wrap=document.createElement('div');wrap.className='preference-vote';
    wrap.innerHTML='<span>這類內容：</span><button type="button" data-v="1" aria-label="喜歡這類內容">👍</button><button type="button" data-v="-1" aria-label="少看這類內容">👎</button>';
    const paint=()=>{const v=pref.votes[id]?.vote||0;wrap.querySelector('[data-v="1"]').classList.toggle('is-up',v===1);wrap.querySelector('[data-v="-1"]').classList.toggle('is-down',v===-1);};
    wrap.querySelectorAll('button').forEach(btn=>btn.addEventListener('click',()=>{
      const next=Number(btn.dataset.v),old=pref.votes[id]?.vote||0,vote=old===next?0:next;
      if(old){(pref.votes[id]?.tags||[]).forEach(t=>pref.tags[t]=(pref.tags[t]||0)-old);}
      if(vote){tags.forEach(t=>pref.tags[t]=(pref.tags[t]||0)+vote);pref.votes[id]={vote,tags,title,source,updatedAt:new Date().toISOString()};}else delete pref.votes[id];
      Object.keys(pref.tags).forEach(t=>{if(!pref.tags[t])delete pref.tags[t];});save();paint();
    }));
    const anchor=card.querySelector('a.source');if(anchor)anchor.insertAdjacentElement('afterend',wrap);else card.appendChild(wrap);paint();
  });
  window.ai3dPreferenceProfile=()=>JSON.parse(JSON.stringify(pref));
});