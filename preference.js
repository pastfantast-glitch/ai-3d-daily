(()=>{
  if(window.__ai3dPreferenceV2)return;
  window.__ai3dPreferenceV2=true;

  const STORE='ai3d-preferences-v2';
  const LEGACY_STORE='ai3d-preferences-v1';
  const STYLE_ID='ai3d-preference-style-v2';
  const CARD_SELECTOR='[data-intel-role="card"][data-intel-id]';
  const caps={category:3,tool:5,topic:5,tag:5};
  const TOOL_NAMES=['Meshy','Tripo','Hunyuan3D','Hunyuan','Blender','Maya','3ds Max','ZBrush','Substance','Unreal Engine','Unreal','UE5','Unity','Cascadeur','Houdini','Arnold','ComfyUI','Rokoko','MetaHuman','MotionBuilder','Move AI','DeepMotion','AccuRIG','Godot','Bifrost','Cycles'];
  const TOPIC_RULES=[
    ['Retopology',/retopo|retopology|拓樸|重拓/i],['UV',/\buv\b|unwrap|拆\s*uv|uv拆/i],['Texture',/texture|textur|貼圖/i],['PBR',/\bpbr\b|roughness|metallic|normal bake/i],
    ['Multi-view',/multi[- ]?view|multiview|多視圖|四視圖/i],['Image-to-3D',/image[- ]?to[- ]?3d|image to 3d|圖像.?3d|圖片.?3d/i],['Text-to-3D',/text[- ]?to[- ]?3d|text to 3d|文字.?3d/i],
    ['Rigging',/rigging|\brig\b|綁定|骨架/i],['Animation',/animation|動畫|動作/i],['Mocap',/mocap|motion capture|動捕/i],['Retarget',/retarget|重定向/i],['Facial',/facial|face rig|臉部|表情/i],
    ['Shader',/shader|材質球|著色/i],['NPR / Toon',/\bnpr\b|toon|stylized rendering|卡通渲染|賽璐璐/i],['Rendering',/render|渲染|cycles|arnold/i],['Lighting',/lighting|light|燈光|光照|lumen/i],
    ['Character',/character|角色|human|人物/i],['Environment',/environment|world|場景|terrain|landscape|open world/i],['Prop / Hard Surface',/prop|hard.?surface|weapon|vehicle|mechanical|道具|硬表面|武器|載具|機械/i],
    ['Procedural',/procedural|geometry nodes|node.?based|程序化|幾何節點/i],['Optimization',/optimization|performance|lod|hlod|draw.?call|效能|優化/i],['Automation / Pipeline',/pipeline|automation|batch|api|workflow|流程|自動化/i]
  ];

  let profile=loadProfile();

  function emptyProfile(){return{schemaVersion:2,votes:{},weights:{category:{},tool:{},topic:{},tag:{}},updatedAt:null};}
  function clone(value){return JSON.parse(JSON.stringify(value));}
  function clamp(value,min,max){return Math.max(min,Math.min(max,value));}
  function clean(value){return String(value||'').replace(/\s+/g,' ').trim();}
  function unique(values){return [...new Set(values.map(clean).filter(Boolean))];}
  function legacyToV2(legacy){
    const next=emptyProfile();
    Object.entries(legacy?.votes||{}).forEach(([id,entry])=>{
      const vote=Number(entry?.vote)||0;if(!vote)return;
      const tags=unique(entry?.tags||[]);
      next.votes[id]={vote:vote>0?1:-1,title:clean(entry?.title),source:clean(entry?.source),category:'',features:{category:[],tools:[],topics:[],tags},updatedAt:entry?.updatedAt||new Date().toISOString()};
    });
    return recomputeWeights(next);
  }
  function loadProfile(){
    try{
      const raw=JSON.parse(localStorage.getItem(STORE)||'null');
      if(raw&&Number(raw.schemaVersion)===2&&raw.votes)return recomputeWeights(Object.assign(emptyProfile(),raw));
    }catch(_){}
    try{
      const legacy=JSON.parse(localStorage.getItem(LEGACY_STORE)||'null');
      if(legacy?.votes&&Object.keys(legacy.votes).length){const migrated=legacyToV2(legacy);localStorage.setItem(STORE,JSON.stringify(migrated));return migrated;}
    }catch(_){}
    return emptyProfile();
  }
  function ageFactor(iso){
    const time=Date.parse(iso||'');if(!Number.isFinite(time))return 1;
    const days=Math.max(0,(Date.now()-time)/86400000);
    if(days<=7)return 1;if(days<=30)return .7;if(days<=90)return .4;return .2;
  }
  function addWeight(bucket,key,delta){if(!key)return;bucket[key]=(bucket[key]||0)+delta;}
  function recomputeWeights(next=profile){
    const weights={category:{},tool:{},topic:{},tag:{}};
    Object.values(next.votes||{}).forEach(entry=>{
      const vote=Number(entry?.vote)||0;if(!vote)return;
      const base=(vote>0?1:-1.5)*ageFactor(entry.updatedAt);
      const f=entry.features||{};
      unique(f.category||[]).forEach(x=>addWeight(weights.category,x,base));
      unique(f.tools||[]).forEach(x=>addWeight(weights.tool,x,base));
      unique(f.topics||[]).forEach(x=>addWeight(weights.topic,x,base));
      unique(f.tags||[]).forEach(x=>addWeight(weights.tag,x,base));
    });
    Object.entries(weights).forEach(([group,bucket])=>Object.keys(bucket).forEach(key=>{bucket[key]=Number(clamp(bucket[key],-caps[group],caps[group]).toFixed(2));if(!bucket[key])delete bucket[key];}));
    next.weights=weights;return next;
  }
  function save(){
    profile.updatedAt=new Date().toISOString();recomputeWeights(profile);
    try{localStorage.setItem(STORE,JSON.stringify(profile));}catch(_){}
    window.dispatchEvent(new CustomEvent('ai3d:preference-change',{detail:{profile:clone(profile)}}));
  }
  function injectStyle(){
    if(document.getElementById(STYLE_ID))return;
    const style=document.createElement('style');style.id=STYLE_ID;style.textContent=`
      .preference-vote{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin-top:10px;padding-top:9px;border-top:1px solid rgba(129,149,181,.16);color:#8793a8;font-size:.72rem;font-weight:760}
      .preference-vote>span{margin-right:2px}.preference-vote button{display:inline-flex;align-items:center;justify-content:center;min-width:34px;height:30px;padding:0 9px;border:1px solid #2c3a50;border-radius:9px;background:#111a29;color:#9eabcb;cursor:pointer;font:inherit;transition:.15s ease}
      .preference-vote button:hover{border-color:#5f58a8;background:#172238;color:#e5e9f2}.preference-vote button.is-up{background:#183526;border-color:#2d6a4d;color:#80e0b2}.preference-vote button.is-down{background:#3a2024;border-color:#6b333b;color:#ff9aa7}
      .preference-vote button:focus-visible{outline:2px solid #8c80ff;outline-offset:2px}.preference-vote .preference-state{min-width:0;color:#748198;font-size:.68rem}
      @media(max-width:760px){.preference-vote{gap:6px}.preference-vote button{height:29px;min-width:33px;padding:0 8px}}
    `;document.head.append(style);
  }
  function currentCategory(card){
    const direct=clean(card.dataset.category);if(direct)return direct;
    const main=card.closest('.category-main');if(main?.dataset.category)return clean(main.dataset.category);
    const bodyCat=clean(document.body?.dataset.category);if(bodyCat)return bodyCat;
    return clean(document.querySelector('.global-category-link.is-active[data-category]')?.dataset.category);
  }
  function inferFeatures(card){
    const title=clean(card.querySelector('h2,h3,h4')?.textContent);
    const summary=clean(card.querySelector('.summary')?.textContent);
    const meta=clean(card.querySelector('.category-meta,.meta')?.textContent);
    const pills=[...card.querySelectorAll('.pill')].map(x=>clean(x.textContent));
    const text=[title,summary,meta,...pills].join(' ');
    const tools=TOOL_NAMES.filter(name=>new RegExp(name.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'i').test(text));
    const topics=TOPIC_RULES.filter(([,rule])=>rule.test(text)).map(([name])=>name);
    const category=currentCategory(card);
    return{category:category?[category]:[],tools:unique(tools),topics:unique(topics),tags:unique(pills.concat(meta?meta.split(/[·#]/).map(clean):[])).slice(0,10)};
  }
  function sourceFor(card){return clean(card.querySelector('a.source')?.href);}
  function titleFor(card){return clean(card.querySelector('h2,h3,h4')?.textContent);}
  function stateText(vote){return vote===1?'已提高這類內容權重':vote===-1?'已降低這類內容權重':'';}
  function paintCard(card){
    const id=clean(card.dataset.intelId);const wrap=card.querySelector('.preference-vote');if(!id||!wrap)return;
    const vote=Number(profile.votes[id]?.vote)||0;
    wrap.querySelector('[data-v="1"]')?.classList.toggle('is-up',vote===1);
    wrap.querySelector('[data-v="-1"]')?.classList.toggle('is-down',vote===-1);
    const state=wrap.querySelector('.preference-state');if(state)state.textContent=stateText(vote);
  }
  function paintId(id){document.querySelectorAll(`${CARD_SELECTOR}[data-intel-id="${CSS.escape(id)}"]`).forEach(paintCard);}
  function setVote(card,next){
    const id=clean(card.dataset.intelId);if(!id)return;
    const old=Number(profile.votes[id]?.vote)||0;const vote=old===next?0:next;
    if(!vote)delete profile.votes[id];
    else profile.votes[id]={vote,title:titleFor(card),source:sourceFor(card),category:currentCategory(card),features:inferFeatures(card),updatedAt:new Date().toISOString()};
    save();paintId(id);
  }
  function makeUI(card){
    const existing=card.querySelector('.preference-vote');if(existing)existing.remove();
    const wrap=document.createElement('div');wrap.className='preference-vote';wrap.dataset.preferenceId=clean(card.dataset.intelId);
    wrap.innerHTML='<span>這類內容：</span><button type="button" data-v="1" aria-label="喜歡這類內容" title="提高未來同類情報權重">👍</button><button type="button" data-v="-1" aria-label="少看這類內容" title="降低未來同類情報權重">👎</button><span class="preference-state" aria-live="polite"></span>';
    wrap.querySelectorAll('button').forEach(btn=>btn.addEventListener('click',()=>setVote(card,Number(btn.dataset.v))));
    const source=card.querySelector('a.source');if(source)source.insertAdjacentElement('afterend',wrap);else card.append(wrap);
    paintCard(card);
  }
  function enhance(root=document){root.querySelectorAll?.(CARD_SELECTOR).forEach(makeUI);if(root.matches?.(CARD_SELECTOR))makeUI(root);}
  function scoreFor(features={}){
    const f=features.features||features;let score=0;
    unique(f.category||[]).forEach(x=>score+=profile.weights.category[x]||0);
    unique(f.tools||[]).forEach(x=>score+=profile.weights.tool[x]||0);
    unique(f.topics||[]).forEach(x=>score+=profile.weights.topic[x]||0);
    unique(f.tags||[]).forEach(x=>score+=(profile.weights.tag[x]||0)*.5);
    return Number(clamp(score,-8,8).toFixed(2));
  }
  function init(){
    injectStyle();enhance(document);
    const observer=new MutationObserver(records=>records.forEach(record=>record.addedNodes.forEach(node=>{if(node.nodeType===1)enhance(node);})));observer.observe(document.body,{childList:true,subtree:true});
    window.addEventListener('storage',event=>{if(event.key!==STORE)return;profile=loadProfile();document.querySelectorAll(CARD_SELECTOR).forEach(paintCard);});
  }

  window.ai3dPreferenceProfile=()=>clone(recomputeWeights(profile));
  window.ai3dPreferenceScore=features=>scoreFor(features);
  window.ai3dPreferenceExport=()=>({schemaVersion:2,kind:'ai3d-preference-ranking-signal',profile:clone(recomputeWeights(profile))});
  window.ai3dPreferenceEnhance=root=>enhance(root||document);

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
