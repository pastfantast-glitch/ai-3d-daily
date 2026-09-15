import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.116.0?bundle';

if (!window.__ai3dOwnerSync) {
  window.__ai3dOwnerSync = true;

  const SUPABASE_URL='https://epumcdxfkcujulqrcjrw.supabase.co';
  const SUPABASE_KEY='sb_publishable_KPadXg3RKth3SGsAuXzebA_OylGgtpf';
  const OWNER_REGISTER=`${SUPABASE_URL}/functions/v1/ai3d-owner-register`;
  const PROFILE_STORE='ai3d-preferences-v2';
  const BOOKMARK_STORE='ai3d-bookmarks-v1';
  const LEGACY_CRED_STORE='ai3d-cloud-sync-v1';
  const DIRTY_STORE='ai3d-owner-sync-dirty-v1';
  const STYLE_ID='ai3d-owner-sync-style-v1';
  const DIALOG_ID='ai3d-owner-sync-dialog-v1';
  const POLL_MS=60000;

  const supabase=createClient(SUPABASE_URL,SUPABASE_KEY,{
    auth:{persistSession:true,autoRefreshToken:true,detectSessionInUrl:false},
  });

  let session=null;
  let busy=false;
  let pendingAction=null;
  let pushTimer=0;
  let lastPullAt=0;
  let status='未登入';
  let applying=false;

  function readJson(key,fallback=null){try{return JSON.parse(localStorage.getItem(key)||'null')??fallback;}catch(_){return fallback;}}
  function localState(){return{profile:readJson(PROFILE_STORE),bookmarks:readJson(BOOKMARK_STORE)};}
  function legacyCredentials(){const c=readJson(LEGACY_CRED_STORE);return c?.sync_id&&c?.secret?c:null;}
  function markDirty(value=true){if(value)localStorage.setItem(DIRTY_STORE,'1');else localStorage.removeItem(DIRTY_STORE);paint();}
  function isDirty(){return localStorage.getItem(DIRTY_STORE)==='1';}
  function setStatus(next){status=next;paint();}
  function escapeHtml(value){return String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));}

  function applyCloudState(state){
    if(!state||typeof state!=='object')return;
    applying=true;
    try{
      if(state.profile!==undefined&&state.profile!==null)localStorage.setItem(PROFILE_STORE,JSON.stringify(state.profile));
      if(state.bookmarks!==undefined&&state.bookmarks!==null)localStorage.setItem(BOOKMARK_STORE,JSON.stringify(state.bookmarks));
      if(typeof window.ai3dPreferenceReloadFromStorage==='function')window.ai3dPreferenceReloadFromStorage({remote:true,source:'owner-cloud'});
      else window.dispatchEvent(new CustomEvent('ai3d:cloud-state-applied',{detail:{remote:true,source:'owner-cloud'}}));
    }finally{applying=false;}
  }

  async function pushLocal({silent=false}={}){
    if(!session?.user)return false;
    if(busy){pendingAction='push';return false;}
    busy=true;if(!silent)setStatus('同步中…');
    try{
      const {error}=await supabase.from('user_sync_state').upsert({
        user_id:session.user.id,
        state:localState(),
        updated_at:new Date().toISOString(),
      },{onConflict:'user_id'});
      if(error)throw error;
      markDirty(false);setStatus('已同步');return true;
    }catch(err){console.warn('AI3D owner push failed',err);markDirty(true);setStatus(navigator.onLine?'待同步':'離線');return false;}
    finally{
      busy=false;
      const next=pendingAction;pendingAction=null;
      if(next)setTimeout(()=>next==='push'?pushLocal({silent:true}):pullCloud({silent:true,force:true}),120);
    }
  }

  async function pullCloud({silent=false,force=false}={}){
    if(!session?.user)return false;
    if(isDirty())return pushLocal({silent});
    if(!force&&Date.now()-lastPullAt<2500)return true;
    if(busy){pendingAction='pull';return false;}
    busy=true;if(!silent)setStatus('同步中…');
    try{
      const {data,error}=await supabase.from('user_sync_state').select('state,updated_at').eq('user_id',session.user.id).maybeSingle();
      if(error)throw error;
      if(data?.state)applyCloudState(data.state);
      else{
        const {error:seedError}=await supabase.from('user_sync_state').upsert({user_id:session.user.id,state:localState(),updated_at:new Date().toISOString()},{onConflict:'user_id'});
        if(seedError)throw seedError;
      }
      lastPullAt=Date.now();markDirty(false);setStatus('已同步');return true;
    }catch(err){console.warn('AI3D owner pull failed',err);setStatus(navigator.onLine?'同步失敗':'離線');return false;}
    finally{
      busy=false;
      const next=pendingAction;pendingAction=null;
      if(next)setTimeout(()=>next==='push'?pushLocal({silent:true}):pullCloud({silent:true,force:true}),120);
    }
  }

  function queuePush(event){
    if(applying||event?.detail?.remote||!session?.user)return;
    markDirty(true);setStatus('待同步');
    clearTimeout(pushTimer);pushTimer=setTimeout(()=>pushLocal({silent:true}),180);
  }

  function injectStyle(){
    if(document.getElementById(STYLE_ID))return;
    const s=document.createElement('style');s.id=STYLE_ID;s.textContent=`
      .cloud-sync-control{display:inline-flex;align-items:center;gap:6px;padding:8px 11px;border:1px solid #2c3a50;border-radius:999px;background:#111a29;color:#9eabcb;cursor:pointer;font:inherit;font-size:.72rem;font-weight:760}.cloud-sync-control:hover{border-color:#5f58a8;color:#e5e9f2}.cloud-sync-control.is-on{color:#80e0b2;border-color:#2d6a4d}.cloud-sync-control.is-warn{color:#ffd866;border-color:#7f6b2d}.owner-sync-dialog{max-width:430px;width:calc(100% - 32px);border:1px solid #33425d;border-radius:16px;background:#0f1726;color:#dfe5f1;padding:0;box-shadow:0 24px 80px rgba(0,0,0,.5)}.owner-sync-dialog::backdrop{background:rgba(4,8,15,.72)}.owner-sync-box{padding:22px}.owner-sync-box h2{margin:0 0 8px;font-size:1.15rem}.owner-sync-box p{margin:0 0 16px;color:#91a0b9;font-size:.82rem;line-height:1.55}.owner-sync-fields{display:grid;gap:10px}.owner-sync-fields label{display:grid;gap:5px;color:#aab5c8;font-size:.76rem;font-weight:700}.owner-sync-fields input{width:100%;box-sizing:border-box;border:1px solid #33425d;border-radius:10px;background:#0a111d;color:#eef2f8;padding:10px 11px;font:inherit}.owner-sync-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:15px}.owner-sync-actions button{border:1px solid #3a4b67;border-radius:9px;background:#172238;color:#dfe5f1;padding:9px 12px;cursor:pointer;font:inherit;font-size:.78rem;font-weight:760}.owner-sync-actions button.primary{background:#26395c;border-color:#5870a0}.owner-sync-actions button.danger{color:#ffabb5;border-color:#6b333b;background:#301b20}.owner-sync-note{margin-top:12px!important;font-size:.72rem!important;color:#748198!important}@media(max-width:760px){.cloud-sync-control .cloud-sync-text{display:none}.owner-sync-dialog{width:calc(100% - 20px)}}`;
    document.head.append(s);
  }

  function injectNav(){
    document.querySelectorAll('.global-category-nav-inner').forEach(inner=>{
      inner.querySelectorAll('.cloud-sync-control').forEach(n=>n.remove());
      const b=document.createElement('button');b.type='button';b.className='cloud-sync-control';b.dataset.cloudSync='owner';b.innerHTML='<span aria-hidden="true">☁</span><span class="cloud-sync-text">登入</span>';b.addEventListener('click',openAccount);inner.append(b);
    });paint();
  }

  function paint(){
    document.querySelectorAll('.cloud-sync-control').forEach(b=>{
      const logged=!!session?.user;const warn=logged&&(status!=='已同步');
      b.classList.toggle('is-on',logged&&!warn);b.classList.toggle('is-warn',warn);
      const text=b.querySelector('.cloud-sync-text');const next=logged?status:'登入';if(text&&text.textContent!==next)text.textContent=next;
      b.title=logged?'主人帳號同步設定':'登入主人帳號以跨裝置同步';
    });
  }

  function ensureDialog(){let d=document.getElementById(DIALOG_ID);if(d)return d;d=document.createElement('dialog');d.id=DIALOG_ID;d.className='owner-sync-dialog';document.body.append(d);return d;}
  function closeDialog(){const d=document.getElementById(DIALOG_ID);if(d?.open)d.close();}
  function showDialog(title,desc,fields,actions,note=''){
    const d=ensureDialog();d.innerHTML=`<div class="owner-sync-box"><h2>${title}</h2><p>${desc}</p><div class="owner-sync-fields">${fields}</div><div class="owner-sync-actions">${actions}</div>${note?`<p class="owner-sync-note">${note}</p>`:''}</div>`;if(!d.open)d.showModal();return d;
  }
  function field(d,name){return String(d.querySelector(`[name="${name}"]`)?.value||'').trim();}

  async function signIn(email,password){
    setStatus('登入中…');
    const {data,error}=await supabase.auth.signInWithPassword({email,password});if(error)throw error;
    session=data.session;setStatus('已同步');await pullCloud({force:true});
  }

  async function bootstrap(email,password){
    const legacy=legacyCredentials();if(!legacy)throw new Error('這台裝置沒有舊同步憑證，請在原本有收藏的裝置先建立主人帳號。');
    const res=await fetch(OWNER_REGISTER,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,password,...legacy,local_state:localState()})});
    const body=await res.json().catch(()=>({}));
    if(!res.ok){if(body?.error==='owner_exists')throw new Error('主人帳號已經建立，請直接登入。');throw new Error(body?.error||'建立主人帳號失敗');}
    await signIn(email,password);
  }

  function signedOutDialog(){
    const canBootstrap=!!legacyCredentials();
    const d=showDialog('主人帳號登入','所有裝置登入同一帳號後，共用同一份收藏與 👍/👎。登入狀態會保留在這台裝置。','<label>Email<input name="email" type="email" autocomplete="username"></label><label>密碼<input name="password" type="password" autocomplete="current-password" minlength="10"></label>',`<button class="primary" type="button" data-login>登入</button>${canBootstrap?'<button type="button" data-bootstrap>第一次建立主人帳號</button>':''}<button type="button" data-close>取消</button>`,canBootstrap?'第一次建立會把目前 9 份舊同步資料與這台本機收藏合併成唯一雲端資料。密碼至少 10 個字元。':'主人帳號建立後，新裝置只需要登入，不需要同步碼。');
    d.querySelector('[data-close]')?.addEventListener('click',closeDialog);
    d.querySelector('[data-login]')?.addEventListener('click',async()=>{const email=field(d,'email'),password=field(d,'password');if(!email||!password)return alert('請輸入 Email 與密碼。');try{await signIn(email,password);closeDialog();}catch(err){console.warn(err);session=null;setStatus('未登入');alert('登入失敗，請確認 Email / 密碼。');}});
    d.querySelector('[data-bootstrap]')?.addEventListener('click',async()=>{const email=field(d,'email'),password=field(d,'password');if(!/^\S+@\S+\.\S+$/.test(email)||password.length<10)return alert('請輸入有效 Email，密碼至少 10 個字元。');if(!confirm('這組 Email / 密碼會成為所有裝置共用的主人登入。確定建立嗎？'))return;try{setStatus('建立帳號…');await bootstrap(email,password);closeDialog();alert('主人帳號已建立，舊收藏已合併。之後其他裝置只要登入同一帳號即可。');}catch(err){console.warn(err);setStatus('未登入');alert(err?.message||'建立主人帳號失敗');}});
  }

  function signedInDialog(){
    const email=escapeHtml(session?.user?.email||'已登入');
    const d=showDialog('主人帳號同步','開啟網站、切回分頁、恢復網路，以及每次收藏或 👍/👎 都會自動同步。',`<label>目前帳號<input value="${email}" disabled></label>`,`<button class="primary" type="button" data-sync>立即同步</button><button class="danger" type="button" data-logout>登出這台裝置</button><button type="button" data-close>關閉</button>`,'⭐ 收藏仍為純收藏，偏好權重維持 0。');
    d.querySelector('[data-close]')?.addEventListener('click',closeDialog);
    d.querySelector('[data-sync]')?.addEventListener('click',async()=>{const ok=isDirty()?await pushLocal():await pullCloud({force:true});alert(ok?'同步完成。':'目前同步失敗，本機資料仍保留。');});
    d.querySelector('[data-logout]')?.addEventListener('click',async()=>{if(!confirm('只登出這台裝置，雲端收藏不會刪除。確定嗎？'))return;await supabase.auth.signOut();session=null;setStatus('未登入');closeDialog();});
  }

  function openAccount(){session?.user?signedInDialog():signedOutDialog();}

  async function refreshSession(){
    try{const {data,error}=await supabase.auth.getSession();if(error)throw error;session=data.session||null;setStatus(session?.user?'已同步':'未登入');if(session?.user)await (isDirty()?pushLocal({silent:true}):pullCloud({silent:true,force:true}));}
    catch(err){console.warn('AI3D session restore failed',err);session=null;setStatus('未登入');}
  }

  function resumeSync(){if(!session?.user||navigator.onLine===false)return;if(isDirty())pushLocal({silent:true});else pullCloud({silent:true});}

  function init(){
    injectStyle();injectNav();refreshSession();
    window.addEventListener('ai3d:preference-change',queuePush);
    window.addEventListener('ai3d:bookmark-change',queuePush);
    window.addEventListener('online',resumeSync);
    window.addEventListener('focus',resumeSync);
    document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')resumeSync();});
    setInterval(()=>{if(document.visibilityState==='visible')resumeSync();},POLL_MS);
    supabase.auth.onAuthStateChange((event,next)=>{session=next||null;setStatus(session?.user?'已同步':'未登入');if(event==='SIGNED_IN'&&session?.user)setTimeout(resumeSync,0);});
  }

  window.ai3dCloudSyncNow=()=>isDirty()?pushLocal():pullCloud({force:true});
  window.ai3dCloudAccount=openAccount;
  window.ai3dCloudSession=()=>session?{user:{id:session.user.id,email:session.user.email}}:null;

  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
}
