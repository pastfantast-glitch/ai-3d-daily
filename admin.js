import {mountOperations} from './admin-operations.js';
import {createClient} from 'https://esm.sh/@supabase/supabase-js@2.116.0?bundle';
import {validateSettings} from './supabase/functions/collection-admin/policy.mjs';
const base='https://epumcdxfkcujulqrcjrw.supabase.co',key='sb_publishable_KPadXg3RKth3SGsAuXzebA_OylGgtpf';
const auth=createClient(base,key,{auth:{persistSession:true,autoRefreshToken:true,detectSessionInUrl:false}});
const $=s=>document.querySelector(s),el=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
let settings=null,sha='',metrics=null,session=null,editing=null,busy=false;
const messages={owner_required:'這個帳號沒有站主權限。',admin_not_configured:'管理服務尚未完成部署設定。',version_conflict:'設定已被其他操作更新。請重新整理後再修改；本次沒有覆蓋新設定。',origin_not_allowed:'請從正式網站開啟後臺。',unsafe_source_url:'請使用公開網站的 HTTPS 網址。',unsafe_source_address:'這個網址不是可收集的公開網路位址。'};
function notify(text,error=false){$('#notice').textContent=text;$('#notice').classList.toggle('error',error);}
async function api(op,body={}){
  const current=await auth.auth.getSession();session=current.data.session;if(!session)throw new Error('請先登入站主帳號。');
  let response;try{response=await fetch(`${base}/functions/v1/collection-admin`,{method:'POST',headers:{apikey:key,Authorization:`Bearer ${session.access_token}`,'Content-Type':'application/json'},body:JSON.stringify({op,...body}),signal:AbortSignal.timeout(op==='probe'?45000:25000)});}catch{throw new Error('無法連線管理服務，請稍後重試；尚未確認儲存成功。');}
  const data=await response.json();if(!response.ok)throw new Error(messages[data.error]||data.message||`操作未完成（${data.error||response.status}）`);return data;
}
const operationsView=mountOperations(api,notify);
async function load(){
  const data=await api('load');settings=data.settings;sha=data.sha;metrics=data.metrics;
  $('#workspace').hidden=false;$('#login-panel').hidden=true;$('#logout').hidden=false;$('#account-state').textContent='站主管理';render();await operationsView.refresh();
}
function button(text,action){const b=el('button',text);b.type='button';b.onclick=()=>action().catch(e=>notify(e.message,true));return b;}
async function save(next){validateSettings(next);const result=await api('save',{sha,settings:next});settings=next;sha=result.sha;render();notify(result.message);return result;}
function render(){
  $('#active-sources').textContent=settings.sources.filter(s=>s.enabled).length;$('#active-topics').textContent=settings.topics.filter(t=>t.enabled).length;
  $('#metrics-date').textContent=metrics?`供稿成效：${metrics.from} 至 ${metrics.date}；僅統計已發布日報的收集紀錄，失敗批次未納入。`:'尚無來源成效統計；下一次正式發布後更新。';
  const q=$('#source-search').value.toLowerCase(),status=$('#source-status').value;$('#source-list').replaceChildren();
  const list=settings.sources.filter(s=>(s.name+' '+s.base_url).toLowerCase().includes(q)&&(status==='all'||s.enabled===(status==='enabled')));
  $('#source-empty').hidden=!!list.length;
  for(const s of list){const card=el('article',undefined,'source-card'),main=el('div'),actions=el('div',undefined,'source-actions');main.append(el('h3',s.name),el('div',s.base_url,'address'));
    const tags=el('div',undefined,'tags');tags.append(el('span',s.enabled?'啟用中':'已暫停',`pill${s.enabled?'':' off'}`));for(const id of s.topic_ids)tags.append(el('span',settings.topics.find(t=>t.id===id)?.name||id,'tag'));main.append(tags);
    const row=metrics?.sources?.[s.id],stats=el('div',undefined,'source-stats');for(const [label,k] of [['找到','candidates'],['退件','rejected'],['入備稿','reserve'],['實際發布','published']]){const x=el('span',label);x.append(el('strong',row?.[k]??'—'));stats.append(x);}main.append(stats);
    actions.append(button('編輯',async()=>openEditor('source',s.id)),button(s.enabled?'暫停':'恢復',async()=>{const next=structuredClone(settings);next.sources.find(x=>x.id===s.id).enabled=!s.enabled;await save(next);}));card.append(main,actions);$('#source-list').append(card);
  }
  $('#topic-list').replaceChildren();for(const t of settings.topics){const c=el('article',undefined,'topic-card');c.append(el('span',t.enabled?'啟用中':'尚未啟用',`pill${t.enabled?'':' off'}`),el('h3',t.name),el('p',t.description));c.append(el('p',`${settings.sources.filter(s=>s.enabled&&s.topic_ids.includes(t.id)).length} 個啟用來源 · 近 ${t.max_age_months} 個月 · 每期目標 ${t.target_items} 篇`));const f=el('footer');const a=el('a','查看主題頁 ↗');a.href=t.id==='ai-3d'?'../':`../topics/?topic=${encodeURIComponent(t.id)}`;f.append(a,button('編輯主題',async()=>openEditor('topic',t.id)));c.append(f);$('#topic-list').append(c);}
}
function input(name,label,value,{type='text',help='',disabled=false}={}){const l=el('label',label);const i=el(type==='textarea'?'textarea':'input');i.name=name;if(type!=='textarea')i.type=type;i.value=value??'';i.disabled=disabled;if(['id','name','base_url'].includes(name))i.required=true;l.append(i);if(help)l.append(el('small',help,'help'));return l;}
function openEditor(kind,id=null){
  editing={kind,id};const fields=$('#editor-fields');fields.replaceChildren();$('#editor-error').textContent='';$('#probe-result').hidden=true;$('#probe-source').hidden=kind!=='source';$('#editor-kicker').textContent=kind==='source'?'SOURCE':'TOPIC';$('#editor-title').textContent=(id?'編輯':'新增')+(kind==='source'?'來源':'收集主題');
  const item=(kind==='source'?settings.sources:settings.topics).find(x=>x.id===id)||{};
  fields.append(input('name','名稱',item.name),input('id',kind==='source'?'來源代號':'網址代號',item.id,{disabled:!!id,help:'使用小寫英數與連字號，例如 photography；儲存後固定。'}));
  if(kind==='source'){
    fields.append(input('base_url','網站首頁',item.base_url,{type:'url'}),input('endpoints','文章列表或 RSS 網址',item.endpoints?.join('\n'),{type:'textarea',help:'每行一個，最多 5 個；與網站首頁相同網域。'}));
    const box=el('fieldset',undefined,'checkboxes');box.append(el('legend','收集到哪些主題'));for(const t of settings.topics){const l=el('label'),i=el('input');i.type='checkbox';i.name='topic_ids';i.value=t.id;i.checked=item.topic_ids?.includes(t.id)||(!id&&t.id==='ai-3d');l.append(i,document.createTextNode(' '+t.name));box.append(l);}fields.append(box);
  }else{
    fields.append(input('description','主題說明',item.description,{type:'textarea'}),input('include_terms','收錄關鍵字',item.include_terms?.join('\n'),{type:'textarea',help:'每行一組；符合其中一組即可。AI／3D 另沿用現有製作相關性檢查。'}),input('exclude_terms','排除關鍵字',item.exclude_terms?.join('\n'),{type:'textarea'}));
    const pair=el('div',undefined,'field-pair');pair.append(input('target_items','每期目標篇數',item.target_items??10,{type:'number',disabled:id==='ai-3d'}),input('max_age_months','來源期限（月）',item.max_age_months??12,{type:'number'}));fields.append(pair);
  }
  const l=el('label'),check=el('input');check.name='enabled';check.type='checkbox';check.checked=!!item.enabled;check.disabled=id==='ai-3d';l.append(check,document.createTextNode(' 啟用'+(kind==='source'?'來源':'主題')));fields.append(l,el('p','設定從下一次收集生效；不會刪除已發布內容。','help'));$('#editor').showModal();
}
$('#editor-form').onsubmit=async e=>{e.preventDefault();if(busy)return;busy=true;const submit=e.submitter;submit.disabled=true;try{
  const f=new FormData(e.target),lines=k=>String(f.get(k)||'').split(/\r?\n/).map(x=>x.trim()).filter(Boolean),item={id:editing.id||String(f.get('id')).trim(),name:String(f.get('name')).trim(),enabled:editing.id==='ai-3d'||f.has('enabled')};
  if(editing.kind==='source')Object.assign(item,{base_url:String(f.get('base_url')).trim(),endpoints:lines('endpoints'),topic_ids:f.getAll('topic_ids')});
  else Object.assign(item,{description:String(f.get('description')||'').trim(),include_terms:lines('include_terms'),exclude_terms:lines('exclude_terms'),target_items:editing.id==='ai-3d'?30:Number(f.get('target_items')),max_age_months:Number(f.get('max_age_months'))});
  const next=structuredClone(settings),list=editing.kind==='source'?next.sources:next.topics,index=list.findIndex(x=>x.id===editing.id);if(index<0)list.push(item);else list[index]=item;
  await save(next);$('#editor').close();
}catch(error){$('#editor-error').textContent=error.message;}finally{busy=false;submit.disabled=false;}};
$('#probe-source').onclick=async()=>{const b=$('#probe-source');b.disabled=true;$('#editor-error').textContent='';try{const url=$('#editor-form [name=endpoints]').value.split(/\r?\n/).find(x=>x.trim())||$('#editor-form [name=base_url]').value;const r=await api('probe',{url:url.trim()});const p=$('#probe-result');p.replaceChildren(el('h3',r.title||'來源預覽'),el('p',`來源日期：${r.source_date||'列表中未確認'} · 正文長度：${r.body_characters} 字元`),el('p',r.body_preview),el('p',r.note));for(const href of r.article_links){const a=el('a',href);a.href=href;a.target='_blank';a.rel='noopener noreferrer';p.append(a);}p.hidden=false;}catch(e){$('#editor-error').textContent=e.message;}finally{b.disabled=false;}};
for(const id of ['close-editor','cancel-editor'])$('#'+id).onclick=()=>$('#editor').close();
$('#add-source').onclick=()=>openEditor('source');$('#add-topic').onclick=()=>openEditor('topic');
$('#source-search').oninput=render;$('#source-status').onchange=render;
$('#reload').onclick=()=>load().then(()=>notify('已載入最新設定。')).catch(e=>notify(e.message,true));
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=async()=>{document.querySelectorAll('[data-view]').forEach(x=>x.removeAttribute('aria-current'));b.setAttribute('aria-current','page');const view=b.dataset.view;$('#view-title').textContent={overview:'發布概況',queue:'待審稿',reserve:'備稿管理',sources:'來源管理',topics:'收集主題',history:'修改紀錄'}[view];for(const name of ['overview','queue','reserve','sources','topics','history'])$('#'+name+'-view').hidden=name!==view;
  if(view==='history'&&settings)try{const r=await api('history');$('#history-list').replaceChildren();for(const entry of r.history){const row=el('article',undefined,'history-row'),left=el('div',entry.message);left.append(el('small',new Date(entry.date).toLocaleString('zh-TW',{timeZone:'Asia/Taipei'})));const restore=button('還原此設定',async()=>{if(!confirm('將來源與主題設定還原至此版本？已發布文章不會變動。'))return;const old=await api('version',{commit:entry.sha});await save(old.settings);});row.append(left,restore);$('#history-list').append(row);}}catch(e){notify(e.message,true);}
});
$('#login-form').onsubmit=async e=>{e.preventDefault();const f=new FormData(e.target),button=e.submitter;button.disabled=true;try{const r=await auth.auth.signInWithPassword({email:String(f.get('email')),password:String(f.get('password'))});e.target.password.value='';if(r.error)throw new Error('登入失敗，請確認帳號與密碼。');await load();notify('已登入站主後臺。');}catch(e){notify(e.message,true);}finally{button.disabled=false;}};
$('#logout').onclick=async()=>{await auth.auth.signOut();location.reload();};
try{const r=await auth.auth.getSession();if(r.data.session)await load();}catch(e){notify(e.message,true);}
