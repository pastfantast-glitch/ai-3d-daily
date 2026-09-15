import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.116.0?bundle';

if (!window.__ai3dCloudSyncV4) {
  window.__ai3dCloudSyncV4 = true;

  const SUPABASE_URL='https://epumcdxfkcujulqrcjrw.supabase.co';
  const SUPABASE_KEY='sb_publishable_KPadXg3RKth3SGsAuXzebA_OylGgtpf';
  const OWNER_REGISTER=`${SUPABASE_URL}/functions/v1/ai3d-owner-register`;
  const PROFILE_STORE='ai3d-preferences-v2';
  const BOOKMARK_STORE='ai3d-bookmarks-v1';
  const LEGACY_CRED_STORE='ai3d-cloud-sync-v1';
  const STYLE_ID='ai3d-cloud-sync-style-v4';
  const DIALOG_ID='ai3d-cloud-sync-dialog-v4';
  const SYNC_INTERVAL_MS=60000;
  const supabase=createClient(SUPABASE_URL,SUPABASE_KEY,{
    auth:{persistSession:true,autoRefreshToken:true,detectSessionInUrl:false},
  });

  let session=null;
  let busy=false;
  let pending=false;
  let applying=false;
  let pushTimer=0;
  let lastSyncAt=0;
  let statusText='未登入';

  function readJson(key,fallback=null){try{return JSON.parse(localStorage.getItem(key)||'null')??fallback;}catch(_){return fallback;}}
  function clone(value){return JSON.parse(JSON.stringify(value));}
  function object(value){return value&&typeof value==='object'&&!Array.isArray(value)?value:{};}
  function isoMax(a,b){return (Date.parse(String(a||''))||0)>=(Date.parse(String(b||''))||0)?a:b;}
  function timeOf(value){return Date.parse(String(value||''))||0;}
  function emptyProfile(){return{schemaVersion:2,votes:{},tombstones:{},weights:{category:{},tool:{},topic:{},tag:{}},updatedAt:null};}
  function emptyBookmarks(){return{schemaVersion:1,items:{},tombstones:{},updatedAt:null};}
  function normalizeProfile(value){const src=object(value);return Object.assign(emptyProfile(),src,{votes:object(src.votes),tombstones:object(src.tombstones)});}
  function normalizeBookmarks(value){const src=object(value);return Object.assign(emptyBookmarks(),src,{items:object(src.items),tombstones:object(src.tombstones)});}
  function localState(){return{profile:normalizeProfile(readJson(PROFILE_STORE)),bookmarks:normalizeBookmarks(readJson(BOOKMARK_STORE))};}
  function same(a,b){try{return JSON.stringify(a)===JSON.stringify(b);}catch(_){return false;}}

  function mergeTimedMap(localItems,remoteItems,localTombs,remoteTombs,itemTime){
    const items={};const tombstones={};
    const ids=new Set([...Object.keys(localItems),...Object.keys(remoteItems),...Object.keys(localTombs),...Object.keys(remoteTombs)]);
    ids.forEach(id=>{
      const li=localItems[id],ri=remoteItems[id];
      const lt=String(localTombs[id]||''),rt=String(remoteTombs[id]||'');
      const tomb= timeOf(lt)>=timeOf(rt)?lt:rt;
      if(tomb)tombstones[id]=tomb;
      const chosen=!li?ri:!ri?li:(itemTime(li)>=itemTime(ri)?li:ri);
      if(chosen && itemTime(chosen)>timeOf(tomb)) items[id]=chosen;
    });
    return{items,tombstones};
  }

  function mergeStates(local,remote){
    const lp=normalizeProfile(local?.profile),rp=normalizeProfile(remote?.profile);
    const pv=mergeTimedMap(lp.votes,rp.votes,lp.tombstones,rp.tombstones,x=>timeOf(x?.updatedAt));
    const profile=Object.assign(emptyProfile(),lp,rp,{
      votes:pv.items,tombstones:pv.tombstones,
      weights:object(lp.weights),updatedAt:isoMax(lp.updatedAt,rp.updatedAt),
    });
    const lb=normalizeBookmarks(local?.bookmarks),rb=normalizeBookmarks(remote?.bookmarks);
    const bi=mergeTimedMap(lb.items,rb.items,lb.tombstones,rb.tombstones,x=>timeOf(x?.updatedAt||x?.savedAt));
    const bookmarks=Object.assign(emptyBookmarks(),lb,rb,{
      items:bi.items,tombstones:bi.tombstones,updatedAt:isoMax(lb.updatedAt,rb.updatedAt),
    });
    return{profile,bookmarks};
  }

  function applyLocal(next){
    applying=true;
    try{
      localStorage.setItem(PROFILE_STORE,JSON.stringify(normalizeProfile(next.profile)));
      localStorage.setItem(BOOKMARK_STORE,JSON.stringify(normalizeBookmarks(next.bookmarks)));
      if(typeof window.ai3dPreferenceReloadFromStorage==='function')window.ai3dPreferenceReloadFromStorage({remote:true,source:'cloud-owner'});
      else window.dispatchEvent(new CustomEvent('ai3d:cloud-state-applied',{detail:{state:clone(next)}}));
    }finally{applying=false;}
  }

  function legacyCredentials(){const c=readJson(LEGACY_CRED_STORE);return c?.sync_id&&c?.secret?c:null;}
  function setStatus(text){statusText=text;paint();}
  function sessionLabel(){return session?.user?'已同步':'未登入';}

  async function syncNow({force=false}={}){
    if(!session?.user)return false;
    if(!force&&Date.now()-lastSyncAt<2500)return false;
    if(busy){pending=true;return false;}
    busy=true;setStatus('同步中…');
    try{
      const uid=session.user.id;
      const {data,error}=await supabase.from('user_sync_state').select('state,updated_at').eq('user_id',uid).maybeSingle();
      if(error)throw error;
      const local=localState();
      const remote=data?.state&&typeof data.state==='object'?data.state:null;
      const merged=remote?mergeStates(local,remote):local;
      if(!same(local,merged))applyLocal(merged);
      if(!remote||!same(remote,merged)){
        const {error:upsertError}=await supabase.from('user_sync_state').upsert({user_id:uid,state:merged,updated_at:new Date().toISOString()},{onConflict:'user_id'});
        if(upsertError)throw upsertError;
      }
      lastSyncAt=Date.now();setStatus('已同步');return true;
    }catch(err){console.warn('AI3D owner sync failed',err);setStatus(navigator.onLine?'同步失敗':'離線');return false;}
    finally{
      busy=false;
      if(pending){pending=false;setTimeout(()=>syncNow({force:true}),120);}
    }
  }

  function queueSync(){
    if(applying||!session?.user)return;
    clearTimeout(pushTimer);
    pushTimer=setTimeout(()=>syncNow({force:true}),180);
    setStatus('待同步');
  }

  function injectStyle(){
    if(document.getElementById(STYLE_ID))return;
    const style=document.createElement('style');style.id=STYLE_ID;style.textContent=`
      .cloud-sync-control{display:inline-flex;align-items:center;gap:6px;padding:8px 11px;border:1px solid #2c3a50;border-radius:999px;background:#111a29;color:#9eabcb;cursor:pointer;font:inherit;font-size:.72rem;font-weight:760}.cloud-sync-control:hover{border-color:#5f58a8;color:#e5e9f2}.cloud-sync-control.is-on{color:#80e0b2;border-color:#2d6a4d}.cloud-sync-control.is-warn{color:#ffd866;border-color:#7f6b2d}.ai3d-auth-dialog{max-width:430px;width:calc(100% - 32px);border:1px solid #33425d;border-radius:16px;background:#0f1726;color:#dfe5f1;padding:0;box-shadow:0 24px 80px rgba(0,0,0,.5)}.ai3d-auth-dialog::backdrop{background:rgba(4,8,15,.7)}.ai3d-auth-box{padding:22px}.ai3d-auth-box h2{margin:0 0 8px;font-size:1.15rem}.ai3d-auth-box p{margin:0 0 16px;color:#91a0b9;font-size:.82rem;line-height:1.55}.ai3d-auth-fields{display:grid;gap:10px}.ai3d-auth-fields label{display:grid;gap:5px;color:#aab5c8;font-size:.76rem;font-weight:700}.ai3d-auth-fields input{width:100%;box-sizing:border-box;border:1px solid #33425d;border-radius:10px;background:#0a111d;color:#eef2f8;padding:10px 11px;font:inherit}.ai3d-auth-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:15px}.ai3d-auth-actions button{border:1px solid #3a4b67;border-radius:9px;background:#172238;color:#dfe5f1;padding:9px 12px;cursor:pointer;font:inherit;font-size:.78rem;font-weight:760}.ai3d-auth-actions button.primary{background:#26395c;border-color:#5870a0}.ai3d-auth-actions button.danger{color:#ffabb5;border-color:#6b333b;background:#301b20}.ai3d-auth-note{margin-top:12px!important;font-size:.72rem!important;color:#748198!important}@media(max-width:760px){.cloud-sync-control .cloud-sync-text{display:none}.ai3d-auth-dialog{width:calc(100% - 20px)}}`;
    document.head.append(style);
  }

  function injectNav(){
    document.querySelectorAll('.global-category-nav-inner').forEach(inner=>{
      if(inner.querySelector('.cloud-sync-control'))return;
      const b=document.createElement('button');b.type='button';b.className='cloud-sync-control';b.dataset.cloudSync='1';b.innerHTML='<span aria-hidden="true">☁</span><span class="cloud-sync-text">未登入</span>';b.addEventListener('click',openAccountDialog);inner.append(b);
    });
    paint();
  }

  function paint(){
    document.querySelectorAll('.cloud-sync-control').forEach(b=>{
      const on=!!session?.user;
      b.classList.toggle('is-on',on&&statusText==='已同步');
      b.classList.toggle('is-warn',on&&statusText!=='已同步');
      const text=b.querySelector('.cloud-sync-text');const next=on?statusText:'登入';
      if(text&&text.textContent!==next)text.textContent=next;
      b.title=on?'雲端帳號與同步設定':'登入主人帳號以跨裝置同步';
    });
  }

  function ensureDialog(){
    let dialog=document.getElementById(DIALOG_ID);if(dialog)return dialog;
    dialog=document.createElement('dialog');dialog.id=DIALOG_ID;dialog.className='ai3d-auth-dialog';document.body.append(dialog);return dialog;
  }

  function dialogShell(title,description,body,actions,note=''){
    const dialog=ensureDialog();
    dialog.innerHTML=`<div class="ai3d-auth-box"><h2>${title}</h2><p>${description}</p><div class="ai3d-auth-fields">${body}</div><div class="ai3d-auth-actions">${actions}</div>${note?`<p class="ai3d-auth-note">${note}</p>`:''}</div>`;
    if(!dialog.open)dialog.showModal();
    return dialog;
  }

  function closeDialog(){const d=document.getElementById(DIALOG_ID);if(d?.open)d.close();}
  function value(dialog,name){return String(dialog.querySelector(`[name="${name}"]`)?.value||'').trim();}

  async function login(email,password){
    setStatus('登入中…');
    const {data,error}=await supabase.auth.signInWithPassword({email,password});
    if(error)throw error;
    session=data.session;paint();await syncNow({force:true});
  }

  async function bootstrapOwner(email,password){
    const legacy=legacyCredentials();if(!legacy)throw new Error('這台裝置沒有舊同步憑證，請先在原本有收藏的裝置建立主人帳號。');
    const res=await fetch(OWNER_REGISTER,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,password,...legacy,local_state:localState()})});
    const body=await res.json().catch(()=>({}));
    if(!res.ok)throw new Error(body?.error==='owner_exists'?'主人帳號已經建立，請直接登入。':body?.error||'建立主人帳號失敗');
    await login(email,password);
  }

  function openSignedOutDialog(){
    const canBootstrap=!!legacyCredentials();
    const actions=`<button type="button" class="primary" data-auth-login>登入</button>${canBootstrap?'<button type="button" data-auth-bootstrap>第一次建立主人帳號</button>':''}<button type="button" data-auth-close>取消</button>`;
    const dialog=dialogShell('雲端主人帳號','所有裝置只要登入同一帳號，就會共用同一份收藏與 👍/👎；登入狀態會保存在這台裝置。','<label>Email<input name="email" type="email" autocomplete="username" required></label><label>密碼<input name="password" type="password" autocomplete="current-password" minlength="10" required></label>',actions,canBootstrap?'第一次建立會把目前分散的舊收藏合併到同一份雲端資料。密碼至少 10 個字元。':'主人帳號建立後，新裝置只需要登入，不需要同步碼。');
    dialog.querySelector('[data-auth-close]')?.addEventListener('click',closeDialog);
    dialog.querySelector('[data-auth-login]')?.addEventListener('click',async()=>{
      const email=value(dialog,'email'),password=value(dialog,'password');
      if(!email||!password)return alert('請輸入 Email 與密碼。');
      try{await login(email,password);closeDialog();}catch(err){console.warn(err);alert('登入失敗，請確認 Email / 密碼。若尚未建立主人帳號，請在原本的主要裝置先建立一次。');setStatus('未登入');}
    });
    dialog.querySelector('[data-auth-bootstrap]')?.addEventListener('click',async()=>{
      const email=value(dialog,'email'),password=value(dialog,'password');
      if(!email||password.length<10)return alert('請輸入有效 Email，密碼至少 10 個字元。');
      if(!confirm('建立後這組 Email / 密碼就是所有裝置共用的主人登入。確定建立嗎？'))return;
      try{setStatus('建立帳號…');await bootstrapOwner(email,password);closeDialog();alert('主人帳號已建立，舊收藏已合併。之後其他裝置只要登入同一帳號即可自動同步。');}catch(err){console.warn(err);alert(err?.message||'建立主人帳號失敗');setStatus('未登入');}
    });
  }

  function openSignedInDialog(){
    const email=session?.user?.email||'已登入';
    const dialog=dialogShell('雲端同步','這台裝置已連到主人帳號。開啟網站、回到分頁、恢復網路與收藏/評價操作都會自動同步。',`<label>目前帳號<input value="${String(email).replaceAll('&','&amp;').replaceAll('"','&quot;')}" disabled></label>`,`<button type="button" class="primary" data-auth-sync>立即同步</button><button type="button" class="danger" data-auth-logout>登出這台裝置</button><button type="button" data-auth-close>關閉</button>`,'⭐ 收藏仍然只做知識管理，不會增加偏好權重。');
    dialog.querySelector('[data-auth-close]')?.addEventListener('click',closeDialog);
    dialog.querySelector('[data-auth-sync]')?.addEventListener('click',async()=>{await syncNow({force:true});alert(statusText==='已同步'?'同步完成。':'目前同步失敗，本機資料仍保留。');});
    dialog.querySelector('[data-auth-logout]')?.addEventListener('click',async()=>{if(!confirm('只登出這台裝置；雲端收藏不會刪除。確定嗎？'))return;await supabase.auth.signOut();session=null;setStatus('未登入');closeDialog();});
  }

  function openAccountDialog(){session?.user?openSignedInDialog():openSignedOutDialog();}

  async function refreshSession(){
    try{
      const {data,error}=await supabase.auth.getSession();if(error)throw error;
      session=data.session||null;setStatus(session?.user?'已同步':'未登入');
      if(session?.user)await syncNow({force:true});
    }catch(err){console.warn('AI3D auth session unavailable',err);session=null;setStatus('未登入');}
  }

  function activeSync(){if(session?.user&&navigator.onLine)syncNow();}
  function init(){
    injectStyle();injectNav();refreshSession();
    window.addEventListener('ai3d:preference-change',event=>{if(!event.detail?.remote)queueSync();});
    window.addEventListener('ai3d:bookmark-change',event=>{if(!event.detail?.remote)queueSync();});
    window.addEventListener('online',()=>syncNow({force:true}));
    window.addEventListener('focus',activeSync);
    document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')activeSync();});
    setInterval(activeSync,SYNC_INTERVAL_MS);
    supabase.auth.onAuthStateChange((event,nextSession)=>{
      session=nextSession||null;setStatus(session?.user?'已同步':'未登入');
      if(event==='SIGNED_IN'&&session?.user)setTimeout(()=>syncNow({force:true}),0);
    });
  }

  window.ai3dCloudSyncNow=()=>syncNow({force:true});
  window.ai3dCloudAccount=()=>openAccountDialog();
  window.ai3dCloudSession=()=>session?{user:{id:session.user.id,email:session.user.email}}:null;

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
}
