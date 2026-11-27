import {mountLayoutStorage} from './admin-graph-storage.mjs?v=20261127-layout1';
import {mountStudio} from './admin-studio.mjs?v=20261127-layout1';
import {mountGraph} from './admin-graph.js?v=20261127-layout1';
import {validateGraphDraft} from './admin-graph-model.mjs?v=20261127-layout1';
import {mountOperations} from './admin-operations.js?v=20261127-layout1';
import {createClient} from 'https://esm.sh/@supabase/supabase-js@2.116.0?bundle';
import {validateGraphSettings as validateSettings} from './admin-graph-model.mjs?v=20261127-layout1';
import {projectSettings,unprojectSettings,categoryItems,BUILTINS} from './category-model.mjs?v=20261127-layout1';
import {sourceInventory} from './admin-source-state.mjs';
const base='https://epumcdxfkcujulqrcjrw.supabase.co',key='sb_publishable_KPadXg3RKth3SGsAuXzebA_OylGgtpf';
const auth=createClient(base,key,{auth:{persistSession:true,autoRefreshToken:true,detectSessionInUrl:false}});
const $=s=>document.querySelector(s),el=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
let settings=null,activeSettings=null,sha='',head='',pendingSha=null,validation=null,metrics=null,monitor=null,session=null,editing=null,busy=false;
const messages={validation_required:'設定尚未通過驗證，現行版本保持不變。',owner_required:'這個帳號沒有站主權限。',admin_not_configured:'管理服務尚未完成部署設定。',version_conflict:'設定已被其他操作更新。請重新整理後再修改；本次沒有覆蓋新設定。',origin_not_allowed:'請從正式網站開啟後臺。',unsafe_source_url:'請使用公開網站的 HTTPS 網址。',unsafe_source_address:'這個網址不是可收集的公開網路位址。'};
function notify(text,error=false){$('#notice').textContent=text;$('#notice').classList.toggle('error',error);}
async function api(op,body={}){
  // Same two publisher-declared feed aliases as the Collector. The server
  // still validates HTTPS/public DNS; this preview never approves an article.
  if(op==='probe')body={...body,url:({'https://www.cgchannel.com/feed/':'https://feeds2.feedburner.com/cgchannel/nHpU','https://www.blendernation.com/feed/':'https://feeds.feedburner.com/Blendernation'})[body.url]||body.url};
  if(body.settings)body={...body,settings:unprojectSettings(body.settings)};
  const current=await auth.auth.getSession();session=current.data.session;if(!session)throw new Error('請先登入站主帳號。');
  let response;try{response=await fetch(`${base}/functions/v1/collection-admin`,{method:'POST',headers:{apikey:key,Authorization:`Bearer ${session.access_token}`,'Content-Type':'application/json'},body:JSON.stringify({op,...body}),signal:AbortSignal.timeout(op==='probe'?90000:45000)});}catch{throw new Error('無法連線管理服務，請稍後重試；尚未確認儲存成功。');}
  const data=await response.json();if(!response.ok){if(data.error==='version_conflict')studio?.checkRemote();throw new Error(messages[data.error]||data.message||`操作未完成（${data.error||response.status}）`);}if(data.settings)data.settings=projectSettings(data.settings);if(data.validation?.draft)data.validation.draft=projectSettings(data.validation.draft);return data;
}
let graphDirty=false,savedSettings=null,currentView='graph',operationsData=null,studio=null,layoutView=null,leaving=false;
const operationsView=mountOperations(api,notify,data=>{operationsData=data;if(settings)render();else updateGraph();},row=>studio.showArticle(row));
const graphView=mountGraph({
  onChange:next=>{if(busy){notify('正在儲存，請稍候再修改。');return;}try{validateGraphDraft(next);settings=next;graphDirty=JSON.stringify(settings)!==JSON.stringify(savedSettings);render();}catch(e){notify(e.message,true);updateGraph();}},
  onEdit:(kind,id)=>openEditor(kind,id),onAdd:kind=>openEditor(kind),
  onSave:async()=>{if(busy||!graphDirty)return;busy=true;updateGraph();try{await save(settings);}catch(e){notify(e.message,true);}finally{busy=false;updateGraph();}},
  onDiscard:()=>{if(!confirm('捨棄尚未儲存的畫布變更？已儲存的待驗證版本不受影響。'))return;settings=structuredClone(savedSettings);graphDirty=false;closeEditor();render();notify('已捨棄本機變更。');},
  onValidation:()=>studio.open('validation'),
  onLayoutChange:()=>layoutView?.changed(),onView:view=>studio.open(view),notify
});
layoutView=mountLayoutStorage({auth,graph:graphView,notify});
function setDraft(next){if(busy)throw Error('正在儲存，請稍後再修改。');validateGraphDraft(next);settings=structuredClone(next);graphDirty=JSON.stringify(settings)!==JSON.stringify(savedSettings);render();}
studio=mountStudio({api,notify,onCloseEditor:closeEditor,getState:()=>({settings,activeSettings,savedSettings,sha,pendingSha,validation,monitor,operations:operationsData,dirty:graphDirty}),onDraft:setDraft,onRemote:(data,merged)=>{activeSettings=data.settings;validation=data.validation;savedSettings=structuredClone(validation?.draft||activeSettings);settings=structuredClone(merged||savedSettings);sha=data.sha;head=data.head;pendingSha=data.pending_sha;monitor=data.monitor;metrics=data.metrics;graphDirty=JSON.stringify(settings)!==JSON.stringify(savedSettings);render();}});
function updateGraph(){if(settings)graphView.update({settings,activeSettings,validation,metrics,monitor,operations:operationsData,dirty:graphDirty,busy,version:sha+":"+pendingSha,storageKey:"ai3d.graph.v1:"+(session?.user?.id||"owner")});}
window.addEventListener('beforeunload',e=>{if(!leaving&&(graphDirty||layoutView?.dirty)){e.preventDefault();e.returnValue='';}});
function closeEditor(){if($('#graph-inline-editor').contains($('#editor-form')))$('#editor').append($('#editor-form'));$('#editor').close();studio?.resetEditor();graphView.refreshInspector();}

async function load({preserveDirty=false}={}){
  if(graphDirty&&!preserveDirty&&!confirm('重新載入將捨棄尚未儲存的畫布變更，是否繼續？'))return;
  const data=await api('load');activeSettings=data.settings;validation=data.validation;settings=structuredClone(validation?.draft||activeSettings);savedSettings=structuredClone(settings);graphDirty=false;sha=data.sha;head=data.head;pendingSha=data.pending_sha;metrics=data.metrics;monitor=data.monitor;
  $('#workspace').hidden=false;$('#login-panel').hidden=true;$('#logout').hidden=false;$('#account-state').textContent='站主管理';$('#graph-view').hidden=false;$('#overview-view').hidden=true;render();await Promise.all([layoutView.start(),operationsView.refresh()]);
}
function button(text,action){const b=el('button',text);b.type='button';b.onclick=()=>action().catch(e=>notify(e.message,true));return b;}
async function save(next){if(studio.hasConflict())throw Error('請先比較並處理遠端版本衝突。');validateSettings(next);const result=await api('save',{sha,pending_sha:pendingSha,settings:next});await load({preserveDirty:true});studio.announce();notify(result.message);return result;}
function renderValidation(){
  const box=$('#settings-validation');box.replaceChildren();
  const labels={ACTIVE:'現行設定已生效',SAVED:'待驗證版本已儲存，等待檢查',VALIDATING:'正在驗證，現行設定保持不變',PASSED:'驗證通過，可以套用',FAILED:'驗證失敗，現行設定保持不變',UNKNOWN:'驗證狀態未知，現行設定保持不變',STALE:'現行設定已更新，請重新送出驗證'};
  box.append(el('h3',labels[validation?.state]||'設定狀態未知'));
  if(graphDirty)box.append(el('p','畫布尚有未儲存變更。請先儲存並驗證，或捨棄變更後再套用已驗證版本。'));
  if(validation?.draft)box.append(el('p','下方為待驗證版本；上方啟用數量仍以現行設定計算。'));
  if(validation?.message)box.append(el('p',validation.message));
  if(validation?.run_url){const a=el('a','查看驗證結果與失敗原因');a.href=validation.run_url;a.target='_blank';a.rel='noopener';box.append(a);}
  box.append(button('更新驗證狀態',async()=>studio.checkRemote()));
  if(validation?.state==='PASSED'&&!graphDirty)box.append(button('套用已驗證設定',async()=>{if(busy)return;busy=true;try{if(studio.hasConflict())throw Error('請先處理設定版本衝突。');if(!confirm('已確認影響預覽？套用後，下一次 Collector 使用此設定；已發布文章不變。'))return;const r=await api('activate',{sha,head,pending_sha:pendingSha});await load();studio.announce();notify(r.message);}finally{busy=false;}}));
}
function render(){
  updateGraph();renderValidation();
  $('#active-sources').textContent=activeSettings.sources.filter(s=>s.enabled).length;$('#active-topics').textContent=activeSettings.topics.filter(t=>t.enabled).length;
  $('#metrics-date').textContent=(monitor?`最近收集：${monitor.date}（${monitor.collector_conclusion==='success'?'成功':'未完成'}），含失敗批次。下方另列已發布日報的 30 日累計；缺項以 — 表示。 `:'尚無最近收集快照。 ')+(metrics?`供稿成效：${metrics.from} 至 ${metrics.date}；僅統計已發布日報的收集紀錄，失敗批次未納入。`:'尚無來源成效統計；下一次正式發布後更新。');
  const q=$('#source-search').value.toLowerCase(),status=$('#source-status').value;$('#source-list').replaceChildren();
  const list=settings.sources.filter(s=>(s.name+' '+s.base_url).toLowerCase().includes(q)&&(status==='all'||s.enabled===(status==='enabled')));
  $('#source-empty').hidden=!!list.length;
  for(const s of list){const card=el('article',undefined,'source-card'),main=el('div'),actions=el('div',undefined,'source-actions');main.append(el('h3',s.name),el('div',s.base_url,'address'));
    const tags=el('div',undefined,'tags');tags.append(el('span',s.enabled?'啟用中':'已暫停',`pill${s.enabled?'':' off'}`));for(const id of s.topic_ids)tags.append(el('span',settings.topics.find(t=>t.id===id)?.name||id,'tag'));main.append(tags);
    const latest=monitor?.sources?.[s.id];const recent=el('div',undefined,'source-stats');for(const [label,k] of [['收集時候選','candidates_found'],['收集時正文成功','evidence_extracted'],['收集時核准','review_approved'],['收集時待審','awaiting_review']]){const x=el('span',label);x.append(el('strong',latest?.[k]??'—'));recent.append(x);}main.append(recent);
    const states={checked:'已檢查',blocked:'網站拒絕連線',unavailable:'暫時無法讀取','not-scheduled':'本批未排入'};main.append(el('p',latest?`${monitor.mode==='source-trial'?'試收 · ':''}${states[latest.status]||latest.status} ${latest.reason||''}`:'尚無此來源的收集紀錄；不代表沒有文章。','help'));
    const live=sourceInventory(operationsData,s.id),liveStats=el('div',undefined,'source-stats');liveStats.dataset.liveInventory=s.id;
    for(const [label,k] of [['目前庫存稿件','total'],['可供下次複核','pending'],['來源暫時無法讀取','unavailable']]){const x=el('span',label);x.append(el('strong',live?.[k]??'—'));liveStats.append(x);}main.append(liveStats,el('p',live?`即時庫存查核：${new Date(live.checkedAt).toLocaleString('zh-TW',{timeZone:'Asia/Taipei'})}；與備稿管理使用同一份資料，使用前仍須重新核對。`:'尚未取得此來源的完整即時庫存；— 不代表零篇。','help'));
    const yieldRow=monitor?.yield_inventory?.[s.id];
    if(yieldRow){const stats=el('div',undefined,'source-stats');for(const [label,k] of [['收集時 30 日唯一核准','approved_30d'],['收集時核准稿已發布','published_from_approvals_30d'],['收集時備稿快照','reserve_pending_recheck']]){const x=el('span',label);x.append(el('strong',yieldRow[k]??'—'));stats.append(x);}main.append(stats,el('p',`歷史快照：${monitor.date}，保留該次收集完成時的數量；後續審稿合併反映在上方即時庫存。`,'help'));}
    const observations=(monitor?.yield_history||[]).filter(x=>x.sources?.[s.id]&&x.sources[s.id].status!=='not-scheduled').slice(-7);
    if(observations.length){const trend=el('details');trend.append(el('summary',`最近 ${observations.length} 次供稿觀測（批次可能重疊，不相加）`));for(const x of observations){const r=x.sources[s.id];trend.append(el('p',`${x.date} · ${x.mode==='source-trial'?'試收':'日常'} · 正文 ${r.evidence_extracted??'—'}／待審 ${r.awaiting_review??'—'}／核准 ${r.review_approved??'—'}／入選 ${r.selected??'—'}／剩餘合格 ${r.approved_reserve??'—'}`));}main.append(trend);}
    const row=metrics?.sources?.[s.id],stats=el('div',undefined,'source-stats');for(const [label,k] of [['累計候選','candidates'],['累計退件','rejected'],['累計入備稿','reserve'],['累計發布','published']]){const x=el('span',label);x.append(el('strong',row?.[k]??'—'));stats.append(x);}main.append(stats);
    actions.append(button('編輯',async()=>openEditor('source',s.id)),button(s.enabled?'暫停':'恢復',async()=>{const next=structuredClone(settings);next.sources.find(x=>x.id===s.id).enabled=!s.enabled;setDraft(next);notify('變更已加入工作區草稿。');}));card.append(main,actions);$('#source-list').append(card);
  }
  $('#topic-list').replaceChildren();for(const t of settings.topics){const c=el('article',undefined,'topic-card');c.append(el('span',t.enabled?'啟用中':'尚未啟用',`pill${t.enabled?'':' off'}`),el('h3',t.name),el('p',t.description));c.append(el('p',`${settings.sources.filter(s=>s.enabled&&s.topic_ids.includes(t.id)).length} 個啟用來源 · 排序 ${t.order??0} · ${t.visible?"導覽顯示":"導覽隱藏"}`));const f=el('footer');const a=el('a','查看分類頁 ↗');a.href=`../?view=${encodeURIComponent(t.id)}`;f.append(a,button('編輯分類',async()=>openEditor('topic',t.id)));c.append(f);$('#topic-list').append(c);}
  studio?.render();
}
function input(name,label,value,{type='text',help='',disabled=false}={}){const l=el('label',label);const i=el(type==='textarea'?'textarea':'input');i.name=name;if(type!=='textarea')i.type=type;i.value=value??'';i.disabled=disabled;if(['id','name','base_url'].includes(name))i.required=true;l.append(i);if(help)l.append(el('small',help,'help'));return l;}
function openEditor(kind,id=null){
  if(studio&&!studio.canLeaveEditor())return;studio?.hide();
  if(busy){notify('正在儲存，請稍候再編輯。');return;}
  closeEditor();editing={kind,id};$('#editor-form button[type=submit]').textContent=currentView==='graph'?'加入畫布草稿':'儲存並驗證';const fields=$('#editor-fields');fields.replaceChildren();$('#editor-error').textContent='';$('#probe-result').hidden=true;$('#probe-source').hidden=kind!=='source';$('#editor-kicker').textContent=kind==='source'?'SOURCE':'CATEGORY';$('#editor-title').textContent=(id?'編輯':'新增')+(kind==='source'?'來源':'分類與分頁');
  const item=(kind==='source'?settings.sources:settings.topics).find(x=>x.id===id)||{};
  fields.append(input('name','名稱',item.name),input('id',kind==='source'?'來源代號':'網址代號',item.id,{disabled:!!id,help:'使用小寫英數與連字號，例如 cloth-workflow；儲存後固定。'}));
  if(kind==='source'){
    fields.append(input('base_url','網站首頁',item.base_url,{type:'url'}),input('endpoints','文章列表或 RSS 網址',item.endpoints?.join('\n'),{type:'textarea',help:'每行一個，最多 5 個；與網站首頁相同網域。'}));
    const box=el('fieldset',undefined,'checkboxes');box.append(el('legend','收集到哪些分類'));for(const t of settings.topics){const l=el('label'),i=el('input');i.type='checkbox';i.name='topic_ids';i.value=t.id;i.checked=item.topic_ids?.includes(t.id)||(!id&&BUILTINS.includes(t.id));l.append(i,document.createTextNode(' '+t.name));box.append(l);}fields.append(box);
  }else{
    fields.append(input('description','分類說明',item.description,{type:'textarea'}),input('include_terms','收錄關鍵字',item.include_terms?.join('\n'),{type:'textarea',help:'每行一組；符合其中一組即可。既有分類留白時沿用原分類；後續收集仍檢查製作相關性。'}),input('exclude_terms','排除關鍵字',item.exclude_terms?.join('\n'),{type:'textarea'}));
    fields.append(input('order','按鈕排序（數字小的在前）',item.order??settings.topics.length,{type:'number'}));
    for(const [key,label,defaultValue] of [['visible','在導覽列顯示',true],['hide_empty','本期沒有文章時隱藏按鈕',true]]){const l=el('label'),i=el('input');i.name=key;i.type='checkbox';i.checked=item[key]??defaultValue;l.append(i,document.createTextNode(' '+label));fields.append(l);}
    fields.append(input('manual_urls','人工指定加入：原文網址',item.manual_urls?.join('\n'),{type:'textarea',help:'每行一個。只調整已發布文章的分類；不會收集或核准文章。同一文章可出現在多個分類。'}),input('excluded_urls','人工指定排除：原文網址',item.excluded_urls?.join('\n'),{type:'textarea'}));
    const preview=button('預覽分類結果',async()=>previewCategory(item.id));fields.append(preview,el('div',undefined,'category-preview'));
  }
  const l=el('label'),check=el('input');check.name='enabled';check.type='checkbox';check.checked=!!item.enabled;check.disabled=id==='ai-3d';l.append(check,document.createTextNode(' 啟用'+(kind==='source'?'來源':'分類')));fields.append(l,el('p','先儲存待驗證版本；完整檢查通過並套用後，下一次收集才會使用。導覽名稱、排序與顯示在網站更新後生效；供稿規則套用至後續收集，已發布文章保留。','help'));if(currentView==='graph'){$('#graph-inline-editor').append($('#editor-form'));$('#graph-inline-editor input[name=name]').focus();}else $('#editor').showModal();
}
$('#editor-form').onsubmit=async e=>{e.preventDefault();if(busy)return;busy=true;const submit=e.submitter;submit.disabled=true;try{
  const f=new FormData(e.target),lines=k=>String(f.get(k)||'').split(/\r?\n/).map(x=>x.trim()).filter(Boolean),item={id:editing.id||String(f.get('id')).trim(),name:String(f.get('name')).trim(),enabled:editing.id==='ai-3d'||f.has('enabled')};
  if(editing.kind==='source')Object.assign(item,{base_url:String(f.get('base_url')).trim(),endpoints:lines('endpoints'),topic_ids:f.getAll('topic_ids')});
  else Object.assign(item,{description:String(f.get('description')||'').trim(),include_terms:lines('include_terms'),exclude_terms:lines('exclude_terms'),target_items:30,max_age_months:12,visible:f.has('visible'),hide_empty:f.has('hide_empty'),order:Number(f.get('order')),manual_urls:lines('manual_urls'),excluded_urls:lines('excluded_urls'),source_ids:settings.sources.filter(s=>s.topic_ids.includes(editing.id)).map(s=>s.id)});
  const next=structuredClone(settings),list=editing.kind==='source'?next.sources:next.topics,index=list.findIndex(x=>x.id===editing.id);if(index<0)list.push(item);else list[index]=item;
  if(currentView==='graph'){validateGraphDraft(next);settings=next;graphDirty=JSON.stringify(settings)!==JSON.stringify(savedSettings);closeEditor();render();notify('節點設定已加入草稿；請按「儲存畫布並驗證」。');}else{await save(next);closeEditor();}
}catch(error){$('#editor-error').textContent=error.message;}finally{busy=false;submit.disabled=false;updateGraph();}};
$('#probe-source').onclick=async()=>{const b=$('#probe-source');b.disabled=true;$('#editor-error').textContent='';try{const url=$('#editor-form [name=endpoints]').value.split(/\r?\n/).find(x=>x.trim())||$('#editor-form [name=base_url]').value;const r=await api('probe',{url:url.trim()});const p=$('#probe-result');p.replaceChildren(el('h3',r.title||'來源預覽'),el('p',`來源日期：${r.source_date||'列表中未確認'} · 正文長度：${r.body_characters} 字元`),el('p',r.body_preview),el('p',r.note));for(const href of r.article_links){const a=el('a',href);a.href=href;a.target='_blank';a.rel='noopener noreferrer';p.append(a);}for(const sample of r.samples||[]){const card=el('div');card.append(el('strong',sample.title||sample.url),el('p',sample.error?`試讀失敗：${sample.error}`:`日期：${sample.source_date||'未確認'} · ${sample.body_characters} 字元 · ${sample.date_eligible?'期限內':'日期待確認或超期'}`));if(sample.body_preview)card.append(el('p',sample.body_preview));p.append(card);}p.hidden=false;}catch(e){$('#editor-error').textContent=e.message;}finally{b.disabled=false;}};
for(const id of ['close-editor','cancel-editor'])$('#'+id).onclick=()=>{if(studio.canLeaveEditor())closeEditor();};
$('#add-source').onclick=()=>openEditor('source');$('#add-topic').onclick=()=>openEditor('topic');
$('#source-search').oninput=render;$('#source-status').onchange=render;
$('#reload').onclick=()=>{if(!studio.canLeaveEditor())return;closeEditor();load().catch(e=>notify(e.message,true));};
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{if(!studio.canLeaveEditor())return;closeEditor();document.querySelectorAll('[data-view]').forEach(x=>x.removeAttribute('aria-current'));b.setAttribute('aria-current','page');$('#view-title').textContent='圖形工作區';$('#graph-view').hidden=false;if(b.dataset.view==='graph')studio.hide();else studio.open(b.dataset.view);});
$('#login-form').onsubmit=async e=>{e.preventDefault();const f=new FormData(e.target),button=e.submitter;button.disabled=true;try{const r=await auth.auth.signInWithPassword({email:String(f.get('email')),password:String(f.get('password'))});e.target.password.value='';if(r.error)throw new Error('登入失敗，請確認帳號與密碼。');await load();notify('已登入站主後臺。');}catch(e){notify(e.message,true);}finally{button.disabled=false;}};
$('#logout').onclick=async()=>{if(!studio.canLeaveEditor())return;if((graphDirty||layoutView.dirty)&&!confirm('還有未儲存的設定或版面，確定登出？'))return;leaving=true;graphDirty=false;closeEditor();await auth.auth.signOut();location.reload();};
try{const r=await auth.auth.getSession();if(r.data.session)await load();}catch(e){notify(e.message,true);}

async function previewCategory(id){
 const target=$('#editor-fields .category-preview');target.replaceChildren(el('p','正在讀取最新已發布內容…'));
 const f=new FormData($('#editor-form')),lines=k=>String(f.get(k)||'').split(/\r?\n/).map(x=>x.trim()).filter(Boolean);
 const c={id:id||String(f.get('id')).trim(),enabled:f.has('enabled'),include_terms:lines('include_terms'),exclude_terms:lines('exclude_terms'),manual_urls:lines('manual_urls'),excluded_urls:lines('excluded_urls'),source_ids:settings.sources.filter(s=>s.topic_ids.includes(id)).map(s=>s.id)};
 try{const read=async url=>{const r=await fetch(url,{cache:'no-cache',signal:AbortSignal.timeout(15000)});if(!r.ok)throw Error('無法取得已發布資料');return r.json();};const latest=await read('../data/publish/latest-success.json'),daily=await read(`../data/daily/${latest.date}.json`);if(daily.date!==latest.date)throw Error('發布資料日期不一致');const matched=categoryItems([...(daily.items||[]),...(daily.topic_items||[])],c,unprojectSettings(settings));target.replaceChildren(el('h4',`${latest.date}：符合 ${matched.length} 篇`),el('p','這是目前表單規則的預覽；尚未儲存或生效。新分類請先建立節點，再連接來源。','help'));for(const i of matched){const a=el('a',i.title);a.href=i.source_url;a.target='_blank';a.rel='noopener';const row=el('p');row.append(a);target.append(row);}}catch(e){target.replaceChildren(el('p',e.message,'error'));}
}
