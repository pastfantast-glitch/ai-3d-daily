(()=>{
  if(window.__ai3dCloudSyncV3)return;
  window.__ai3dCloudSyncV3=true;

  const ENDPOINT='https://epumcdxfkcujulqrcjrw.supabase.co/functions/v1/ai3d-sync';
  const PROFILE_STORE='ai3d-preferences-v2';
  const BOOKMARK_STORE='ai3d-bookmarks-v1';
  const CRED_STORE='ai3d-cloud-sync-v1';
  const DIRTY_STORE='ai3d-cloud-sync-dirty-v1';
  const STYLE_ID='ai3d-cloud-sync-style-v3';
  const POLL_MS=60000;
  let busy=false;
  let pushTimer=0;
  let pollTimer=0;
  let lastRemoteUpdatedAt='';

  function readJson(key,fallback=null){try{return JSON.parse(localStorage.getItem(key)||'null')??fallback;}catch(_){return fallback;}}
  function writeJson(key,value){if(value===null||value===undefined)localStorage.removeItem(key);else localStorage.setItem(key,JSON.stringify(value));}
  function state(){return{profile:readJson(PROFILE_STORE),bookmarks:readJson(BOOKMARK_STORE)};}
  function credentials(){return readJson(CRED_STORE);}
  function setCredentials(value){writeJson(CRED_STORE,value);paint();}
  function makeSecret(){const bytes=new Uint8Array(32);crypto.getRandomValues(bytes);let s='';for(const b of bytes)s+=String.fromCharCode(b);return btoa(s).replaceAll('+','-').replaceAll('/','_').replace(/=+$/,'');}
  function codeFrom(c){return c?`${c.sync_id}.${c.secret}`:'';}
  function parseCode(value){const m=String(value||'').trim().match(/^([0-9a-f-]{36})\.([A-Za-z0-9_-]{32,})$/i);return m?{sync_id:m[1],secret:m[2]}:null;}
  function shortId(c=credentials()){return c?.sync_id?c.sync_id.slice(0,4).toUpperCase():'';}
  function same(a,b){try{return JSON.stringify(a)===JSON.stringify(b);}catch(_){return false;}}
  function ts(value){const n=Date.parse(value||'');return Number.isFinite(n)?n:0;}

  async function call(payload){
    const controller=new AbortController();
    const timer=setTimeout(()=>controller.abort(),8000);
    try{
      const res=await fetch(ENDPOINT,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:controller.signal,cache:'no-store'});
      const body=await res.json().catch(()=>({}));
      if(!res.ok)throw new Error(body?.error||`HTTP ${res.status}`);
      return body;
    }finally{clearTimeout(timer);}
  }

  function newer(a,b,key='updatedAt'){
    if(!a)return b;if(!b)return a;
    return ts(a?.[key])>=ts(b?.[key])?a:b;
  }
  function mergeForLink(local,remote){
    const l=local&&typeof local==='object'?local:{};
    const r=remote&&typeof remote==='object'?remote:{};
    const lp=l.profile&&typeof l.profile==='object'?l.profile:null;
    const rp=r.profile&&typeof r.profile==='object'?r.profile:null;
    const profile=Object.assign({schemaVersion:2,votes:{},weights:{category:{},tool:{},topic:{},tag:{}},updatedAt:null},newer(lp,rp)||{});
    profile.votes={};
    const voteIds=new Set([...Object.keys(lp?.votes||{}),...Object.keys(rp?.votes||{})]);
    voteIds.forEach(id=>{const v=newer(lp?.votes?.[id],rp?.votes?.[id]);if(v)profile.votes[id]=v;});
    profile.updatedAt=new Date(Math.max(ts(lp?.updatedAt),ts(rp?.updatedAt),Date.now())).toISOString();

    const lb=l.bookmarks&&typeof l.bookmarks==='object'?l.bookmarks:null;
    const rb=r.bookmarks&&typeof r.bookmarks==='object'?r.bookmarks:null;
    const bookmarks={schemaVersion:1,items:{},updatedAt:null};
    const bookmarkIds=new Set([...Object.keys(lb?.items||{}),...Object.keys(rb?.items||{})]);
    bookmarkIds.forEach(id=>{
      const a=lb?.items?.[id],b=rb?.items?.[id];
      if(!a)bookmarks.items[id]=b;
      else if(!b)bookmarks.items[id]=a;
      else bookmarks.items[id]=ts(a.savedAt)>=ts(b.savedAt)?a:b;
    });
    bookmarks.updatedAt=new Date(Math.max(ts(lb?.updatedAt),ts(rb?.updatedAt),Date.now())).toISOString();
    return{profile,bookmarks};
  }

  function applyRemote(remote,{source='pull'}={}){
    if(!remote||typeof remote!=='object')return false;
    const local=state();
    if(same(local,remote))return false;
    if(remote.profile)writeJson(PROFILE_STORE,remote.profile);
    if(remote.bookmarks)writeJson(BOOKMARK_STORE,remote.bookmarks);
    localStorage.removeItem(DIRTY_STORE);
    try{window.ai3dPreferenceReloadFromStorage?.({remote:true,source});}catch(err){console.warn('Preference reload after cloud sync failed',err);}
    window.dispatchEvent(new CustomEvent('ai3d:cloud-sync-applied',{detail:{source,remote:true}}));
    return true;
  }

  async function register(){
    if(busy)return;busy=true;paint('建立同步…');
    try{
      const secret=makeSecret();
      const out=await call({action:'register',secret,state:state()});
      setCredentials({sync_id:out.sync_id,secret});
      localStorage.removeItem(DIRTY_STORE);
      paint();
      alert(`雲端同步已建立。\n\n這台裝置代號：${shortId()}\n\n請在另一台裝置點 ☁ →「連結另一台裝置」，貼上這台的同步碼。只需要配對一次。`);
    }catch(err){console.warn('AI3D cloud sync register failed',err);paint('同步失敗');alert('目前無法建立雲端同步，本機收藏仍可正常使用。');}
    finally{busy=false;paint();}
  }

  async function pull({silent=false}={}){
    const c=credentials();if(!c||busy)return false;
    if(localStorage.getItem(DIRTY_STORE)==='1')return false;
    busy=true;if(!silent)paint('同步中…');
    try{
      const out=await call({action:'pull',...c});
      lastRemoteUpdatedAt=String(out.updated_at||lastRemoteUpdatedAt||'');
      const changed=applyRemote(out.state,{source:'pull'});
      if(!silent)paint(changed?'已更新':'已同步');
      return changed;
    }catch(err){console.warn('AI3D cloud sync pull failed',err);if(!silent)paint('離線');return false;}
    finally{busy=false;if(silent)paint();}
  }

  async function pushNow({silent=false,force=false}={}){
    const c=credentials();if(!c||busy)return false;
    if(!force&&localStorage.getItem(DIRTY_STORE)!=='1')return true;
    busy=true;if(!silent)paint('同步中…');
    try{
      const out=await call({action:'push',...c,state:state()});
      lastRemoteUpdatedAt=String(out.updated_at||lastRemoteUpdatedAt||'');
      localStorage.removeItem(DIRTY_STORE);
      if(!silent)paint('已同步');
      return true;
    }catch(err){localStorage.setItem(DIRTY_STORE,'1');console.warn('AI3D cloud sync push failed',err);if(!silent)paint('待同步');return false;}
    finally{busy=false;if(silent)paint();}
  }

  function queuePush(event){
    if(event?.detail?.remote)return;
    if(!credentials())return;
    localStorage.setItem(DIRTY_STORE,'1');
    clearTimeout(pushTimer);pushTimer=setTimeout(()=>pushNow({silent:true}),700);
    paint('待同步');
  }

  async function importCode(){
    const value=prompt('貼上另一台裝置的 AI 3D Daily 同步碼：');
    if(value===null)return;
    const next=parseCode(value);
    if(!next){alert('同步碼格式不正確。');return;}
    if(busy)return;busy=true;paint('連結裝置…');
    try{
      const out=await call({action:'pull',...next});
      const merged=mergeForLink(state(),out.state);
      writeJson(PROFILE_STORE,merged.profile);
      writeJson(BOOKMARK_STORE,merged.bookmarks);
      setCredentials(next);
      const pushed=await call({action:'push',...next,state:merged});
      lastRemoteUpdatedAt=String(pushed.updated_at||out.updated_at||'');
      localStorage.removeItem(DIRTY_STORE);
      try{window.ai3dPreferenceReloadFromStorage?.({remote:true,source:'link'});}catch(err){console.warn(err);}
      window.dispatchEvent(new CustomEvent('ai3d:cloud-sync-applied',{detail:{source:'link',remote:true}}));
      paint();
      alert(`裝置已連結完成。\n\n共同同步代號：${shortId(next)}\n\n這台現有收藏也已合併到共同雲端資料。之後兩台會自動同步。`);
    }catch(err){console.warn('AI3D cloud sync import failed',err);paint('連結失敗');alert('同步碼無效或目前無法連線。');}
    finally{busy=false;paint();}
  }

  async function menu(){
    const c=credentials();
    if(!c){
      const choice=prompt('這台裝置尚未連結雲端。\n\n1 = 建立新的共同同步資料\n2 = 連結另一台已啟用同步的裝置\n\n若你已經在電腦或手機其中一台建立過同步，請在另一台選 2。','2');
      if(choice==='1')return register();
      if(choice==='2')return importCode();
      return;
    }
    const choice=prompt(`雲端同步｜共同代號 ${shortId(c)}\n\n1 = 複製/顯示同步碼\n2 = 立即雙向同步\n3 = 將本機資料立即上傳\n4 = 連結到另一組同步碼\n5 = 關閉這台裝置的雲端同步\n\n請輸入 1–5：`,'2');
    if(choice==='1'){
      const code=codeFrom(c);try{await navigator.clipboard.writeText(code);alert(`同步碼已複製。\n\n共同代號：${shortId(c)}\n\n請像密碼一樣保管，不要公開分享。`);}catch(_){prompt('請複製這組同步碼：',code);}
    }else if(choice==='2'){
      const changed=await pull({silent:false});
      if(!changed&&localStorage.getItem(DIRTY_STORE)==='1')await pushNow({silent:false,force:true});
    }else if(choice==='3')await pushNow({silent:false,force:true});
    else if(choice==='4')await importCode();
    else if(choice==='5'&&confirm('只會取消這台裝置的連結；本機收藏不會刪除。確定嗎？')){setCredentials(null);localStorage.removeItem(DIRTY_STORE);paint();}
  }

  function injectStyle(){
    if(document.getElementById(STYLE_ID))return;
    const s=document.createElement('style');s.id=STYLE_ID;s.textContent=`.cloud-sync-control{display:inline-flex;align-items:center;gap:6px;padding:8px 11px;border:1px solid #2c3a50;border-radius:999px;background:#111a29;color:#9eabcb;cursor:pointer;font:inherit;font-size:.72rem;font-weight:760}.cloud-sync-control:hover{border-color:#5f58a8;color:#e5e9f2}.cloud-sync-control.is-on{color:#80e0b2;border-color:#2d6a4d}.cloud-sync-control.is-warn{color:#ffd866;border-color:#7f6b2d}.cloud-sync-control.is-off{color:#9eabcb}@media(max-width:760px){.cloud-sync-control .cloud-sync-text{display:none}}`;document.head.append(s);
  }
  function injectNav(){
    document.querySelectorAll('.global-category-nav-inner').forEach(inner=>{
      inner.querySelectorAll('.cloud-sync-control').forEach(node=>node.remove());
      const b=document.createElement('button');b.type='button';b.className='cloud-sync-control';b.dataset.cloudSync='1';b.innerHTML='<span aria-hidden="true">☁</span><span class="cloud-sync-text">未連結</span>';b.addEventListener('click',menu);inner.append(b);
    });
    paint();
  }
  function paint(temp=''){
    const c=credentials();const dirty=localStorage.getItem(DIRTY_STORE)==='1';
    document.querySelectorAll('.cloud-sync-control').forEach(b=>{
      b.classList.toggle('is-on',!!c&&!dirty);b.classList.toggle('is-warn',!!c&&dirty);b.classList.toggle('is-off',!c);
      const text=b.querySelector('.cloud-sync-text');const next=temp||(c?(dirty?'待同步':`同步 ${shortId(c)}`):'未連結');if(text&&text.textContent!==next)text.textContent=next;
      b.title=c?`雲端同步設定｜共同代號 ${shortId(c)}`:'尚未連結其他裝置';
    });
  }

  function schedulePolling(){
    clearInterval(pollTimer);
    pollTimer=setInterval(()=>{if(credentials()&&navigator.onLine!==false&&document.visibilityState==='visible')pull({silent:true});},POLL_MS);
  }
  function init(){
    injectStyle();injectNav();schedulePolling();
    window.addEventListener('ai3d:preference-change',queuePush);
    window.addEventListener('ai3d:bookmark-change',queuePush);
    window.addEventListener('online',()=>{if(credentials())pull({silent:true});});
    document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible'&&credentials())pull({silent:true});});
    if(credentials())setTimeout(()=>pull({silent:true}),400);
  }

  window.ai3dCloudSyncCode=()=>codeFrom(credentials());
  window.ai3dCloudSyncStatus=()=>({linked:!!credentials(),sync_id:credentials()?.sync_id||null,short_id:shortId(),dirty:localStorage.getItem(DIRTY_STORE)==='1',remote_updated_at:lastRemoteUpdatedAt||null});
  window.ai3dCloudSyncNow=()=>pull({silent:false});
  window.ai3dCloudSyncImport=importCode;
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
