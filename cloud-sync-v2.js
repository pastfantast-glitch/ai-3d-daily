(()=>{
  if(window.__ai3dCloudSyncV2)return;
  window.__ai3dCloudSyncV2=true;

  const ENDPOINT='https://epumcdxfkcujulqrcjrw.supabase.co/functions/v1/ai3d-sync';
  const PROFILE_STORE='ai3d-preferences-v2';
  const BOOKMARK_STORE='ai3d-bookmarks-v1';
  const CRED_STORE='ai3d-cloud-sync-v1';
  const DIRTY_STORE='ai3d-cloud-sync-dirty-v1';
  const STYLE_ID='ai3d-cloud-sync-style-v2';
  let busy=false;
  let pushTimer=0;

  function readJson(key,fallback=null){try{return JSON.parse(localStorage.getItem(key)||'null')??fallback;}catch(_){return fallback;}}
  function state(){return{profile:readJson(PROFILE_STORE),bookmarks:readJson(BOOKMARK_STORE)};}
  function credentials(){return readJson(CRED_STORE);}
  function setCredentials(value){if(value)localStorage.setItem(CRED_STORE,JSON.stringify(value));else localStorage.removeItem(CRED_STORE);paint();}
  function makeSecret(){const bytes=new Uint8Array(32);crypto.getRandomValues(bytes);let s='';for(const b of bytes)s+=String.fromCharCode(b);return btoa(s).replaceAll('+','-').replaceAll('/','_').replace(/=+$/,'');}
  function codeFrom(c){return c?`${c.sync_id}.${c.secret}`:'';}
  function parseCode(value){const m=String(value||'').trim().match(/^([0-9a-f-]{36})\.([A-Za-z0-9_-]{32,})$/i);return m?{sync_id:m[1],secret:m[2]}:null;}
  async function call(payload){
    const controller=new AbortController();
    const timer=setTimeout(()=>controller.abort(),8000);
    try{
      const res=await fetch(ENDPOINT,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:controller.signal});
      const body=await res.json().catch(()=>({}));
      if(!res.ok)throw new Error(body?.error||`HTTP ${res.status}`);
      return body;
    }finally{clearTimeout(timer);}
  }
  function same(a,b){try{return JSON.stringify(a)===JSON.stringify(b);}catch(_){return false;}}
  function applyRemote(remote){
    if(!remote||typeof remote!=='object')return false;
    const local=state();
    if(same(local,remote))return false;
    if(remote.profile)localStorage.setItem(PROFILE_STORE,JSON.stringify(remote.profile));
    if(remote.bookmarks)localStorage.setItem(BOOKMARK_STORE,JSON.stringify(remote.bookmarks));
    localStorage.removeItem(DIRTY_STORE);
    return true;
  }
  async function register(){
    if(busy)return;busy=true;paint('建立同步…');
    try{
      const secret=makeSecret();
      const out=await call({action:'register',secret,state:state()});
      setCredentials({sync_id:out.sync_id,secret});
      localStorage.removeItem(DIRTY_STORE);
      paint('已同步');
      alert('雲端同步已建立。請點 ☁ 按鈕查看/複製同步碼，換裝置時輸入同一組碼即可。');
    }catch(err){console.warn('AI3D cloud sync register failed',err);paint('同步失敗');alert('目前無法建立雲端同步，本機收藏仍可正常使用。');}
    finally{busy=false;paint();}
  }
  async function pull({reload=false}={}){
    const c=credentials();if(!c||busy)return;busy=true;paint('同步中…');
    try{
      const out=await call({action:'pull',...c});
      const changed=applyRemote(out.state);
      paint('已同步');
      if(changed&&reload)location.reload();
      return changed;
    }catch(err){console.warn('AI3D cloud sync pull failed',err);paint('離線');throw err;}
    finally{busy=false;paint();}
  }
  async function pushNow(){
    const c=credentials();if(!c||busy)return;
    busy=true;paint('同步中…');
    try{
      await call({action:'push',...c,state:state()});
      localStorage.removeItem(DIRTY_STORE);paint('已同步');
    }catch(err){localStorage.setItem(DIRTY_STORE,'1');console.warn('AI3D cloud sync push failed',err);paint('待同步');}
    finally{busy=false;paint();}
  }
  function queuePush(){
    if(!credentials())return;
    localStorage.setItem(DIRTY_STORE,'1');
    clearTimeout(pushTimer);pushTimer=setTimeout(()=>pushNow(),900);
    paint('待同步');
  }
  async function importCode(){
    const value=prompt('貼上另一台裝置的 AI 3D Daily 同步碼：');
    if(value===null)return;
    const c=parseCode(value);
    if(!c){alert('同步碼格式不正確。');return;}
    if(busy)return;busy=true;paint('驗證同步碼…');
    try{
      const out=await call({action:'pull',...c});
      setCredentials(c);localStorage.removeItem(DIRTY_STORE);
      const changed=applyRemote(out.state);
      alert('同步完成，這台裝置已連到同一份收藏與偏好資料。');
      if(changed)location.reload();
    }catch(err){console.warn(err);alert('同步碼無效或目前無法連線。');}
    finally{busy=false;paint();}
  }
  async function menu(){
    const c=credentials();
    if(!c){
      const choice=confirm('尚未啟用雲端同步。\n\n按「確定」建立新的同步碼；按「取消」則輸入既有同步碼。');
      return choice?register():importCode();
    }
    const choice=prompt('雲端同步設定\n\n1 = 複製/顯示同步碼\n2 = 從雲端抓取最新資料\n3 = 將本機資料立即上傳\n4 = 換成其他同步碼\n5 = 關閉這台裝置的雲端同步\n\n請輸入 1–5：','2');
    if(choice==='1'){
      const code=codeFrom(c);try{await navigator.clipboard.writeText(code);alert(`同步碼已複製：\n\n${code}\n\n請像密碼一樣保管，不要公開分享。`);}catch(_){prompt('請複製這組同步碼：',code);}
    }else if(choice==='2'){
      try{const changed=await pull();if(changed){alert('已取得另一裝置的最新資料，重新整理後套用。');location.reload();}else alert('目前已是最新資料。');}catch(_){alert('目前無法連線，本機資料不受影響。');}
    }else if(choice==='3'){await pushNow();}
    else if(choice==='4'){await importCode();}
    else if(choice==='5'&&confirm('只會關閉這台裝置的雲端同步；本機收藏不會刪除。確定嗎？')){setCredentials(null);localStorage.removeItem(DIRTY_STORE);paint();}
  }
  function injectStyle(){
    if(document.getElementById(STYLE_ID))return;
    const s=document.createElement('style');s.id=STYLE_ID;s.textContent=`.cloud-sync-control{display:inline-flex;align-items:center;gap:6px;padding:8px 11px;border:1px solid #2c3a50;border-radius:999px;background:#111a29;color:#9eabcb;cursor:pointer;font:inherit;font-size:.72rem;font-weight:760}.cloud-sync-control:hover{border-color:#5f58a8;color:#e5e9f2}.cloud-sync-control.is-on{color:#80e0b2;border-color:#2d6a4d}.cloud-sync-control.is-warn{color:#ffd866;border-color:#7f6b2d}@media(max-width:760px){.cloud-sync-control .cloud-sync-text{display:none}}`;document.head.append(s);
  }
  function injectNav(){
    document.querySelectorAll('.global-category-nav-inner').forEach(inner=>{
      if(inner.querySelector('.cloud-sync-control'))return;
      const b=document.createElement('button');b.type='button';b.className='cloud-sync-control';b.dataset.cloudSync='1';b.innerHTML='<span aria-hidden="true">☁</span><span class="cloud-sync-text">同步</span>';b.addEventListener('click',menu);inner.append(b);
    });
    paint();
  }
  function paint(temp=''){
    const c=credentials();const dirty=localStorage.getItem(DIRTY_STORE)==='1';
    document.querySelectorAll('.cloud-sync-control').forEach(b=>{
      b.classList.toggle('is-on',!!c&&!dirty);b.classList.toggle('is-warn',!!c&&dirty);
      const text=b.querySelector('.cloud-sync-text');const next=temp||(c?(dirty?'待同步':'同步'):'本機');if(text&&text.textContent!==next)text.textContent=next;
      b.title=c?'雲端同步設定':'啟用雲端同步';
    });
  }
  function init(){
    injectStyle();injectNav();
    window.addEventListener('ai3d:preference-change',queuePush);
    window.addEventListener('ai3d:bookmark-change',queuePush);
  }
  window.ai3dCloudSyncCode=()=>codeFrom(credentials());
  window.ai3dCloudSyncNow=()=>pull();
  window.ai3dCloudSyncImport=importCode;
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();
