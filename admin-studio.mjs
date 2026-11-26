import {settingsImpact,mergeSettings,batchSources,sourceHealth,reserveBreakdown} from './admin-studio-model.mjs';
const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
const titles={overview:'發布概況',queue:'待審稿與退件',reserve:'備稿管理',sources:'來源管理',topics:'收集主題',history:'修改紀錄',validation:'設定驗證與影響',account:'帳號設定'};
const statusNames={ACTIVE:'已生效',SAVED:'已儲存待驗證',VALIDATING:'驗證中',PASSED:'驗證通過，待套用',FAILED:'驗證失敗',UNKNOWN:'驗證狀態未知',STALE:'遠端版本已改變'};
const stateNames={recheck_required:'已審待複核',held:'暫緩',date_ineligible:'超期／日期不符',source_unavailable:'來源失效',source_disabled:'來源／主題停用',awaiting_review:'待審稿',rejected:'待修正'};
export function mountStudio({getState,onDraft,onRemote,onCloseEditor,api,notify}){
 const $=s=>document.querySelector(s),selectedSources=new Set(),scrolls=new Map();let view=null,remote=null,checking=false,editorDirty=false,lastFocus=null;
 const bar=el('section',undefined,'studio-status');bar.setAttribute('aria-label','工作區設定狀態');$('#graph-view').prepend(bar);
 const panel=el('aside',undefined,'studio-panel');panel.id='studio-panel';panel.hidden=true;panel.setAttribute('aria-label','工作區詳情');
 const head=el('header'),title=el('h2'),expand=button('放大工作面板',()=>{panel.classList.toggle('wide');expand.textContent=panel.classList.contains('wide')?'收合工作面板':'放大工作面板';}),close=button('返回畫布',()=>hide());
 head.append(title,expand,close);const content=el('div',undefined,'studio-content');panel.append(head,content);document.body.append(panel);
 const sections={};for(const name of Object.keys(titles)){let section=name==='validation'?$('#settings-validation'):$('#'+name+'-view');if(!section){section=el('section');section.id=name+'-view';}sections[name]=section;section.hidden=true;content.append(section);}
 const article=el('section');article.hidden=true;content.append(article);
 const impact=el('section',undefined,'studio-impact');sections.validation.prepend(impact);
 const conflict=el('section',undefined,'studio-conflict');conflict.hidden=true;panel.insertBefore(conflict,content);
 const account=sections.account;account.append(el('h3','網站站主帳號'),el('p','帳號登入與密碼管理獨立於供稿流程。'),link('忘記密碼／寄送重設連結','../reset-password/'));
 const accountButton=button('帳號設定',()=>open('account'));$('.aside-bottom').prepend(accountButton);
 function button(label,fn){const b=el('button',label);b.type='button';b.onclick=async()=>{try{await fn();}catch(e){notify(e.message,true);}};return b;}
 function link(label,url){const a=el('a',label);a.href=url;if(url.startsWith('https://')){a.target='_blank';a.rel='noopener noreferrer';}return a;}
 function markNavigation(name){document.querySelectorAll('[data-view]').forEach(b=>{if(b.dataset.view===name)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});}
 function hide(){if(!canLeaveEditor())return;if(article.hidden)scrolls.set(view,content.scrollTop);panel.hidden=true;article.hidden=true;if(view)sections[view].hidden=true;view=null;markNavigation('graph');lastFocus?.isConnected&&lastFocus.focus({preventScroll:true});}
 function canLeaveEditor(){if(!editorDirty)return true;if(!confirm('編輯表單尚未加入草稿，確定離開？'))return false;editorDirty=false;return true;}
 function open(name){if(!sections[name]||!canLeaveEditor())return;onCloseEditor?.();if(view){if(article.hidden)scrolls.set(view,content.scrollTop);}else lastFocus=document.activeElement;view=name;markNavigation(name);for(const [k,s]of Object.entries(sections))s.hidden=k!==name;article.hidden=true;title.textContent=titles[name];panel.hidden=false;content.scrollTop=scrolls.get(name)||0;if(name==='history')history();if(name==='validation')renderImpact();close.focus({preventScroll:true});}
 function renderImpact(){const s=getState();if(!s.settings)return;const report=settingsImpact(s.activeSettings,s.settings);impact.replaceChildren(el('h3','套用影響預覽'),el('p',report.timing));const ul=el('ul');for(const text of report.changes)ul.append(el('li',text));if(!report.changes.length)ul.append(el('li','來源與主題沒有變更。'));impact.append(ul);
  for(const t of report.topics)impact.append(el('p',`${t.name}：啟用來源 ${t.before} → ${t.after}${t.enabled?'':'（主題停用）'}`));for(const w of report.warnings)impact.append(el('p',w,'error'));
  // renderValidation replaces its section, so reinsert this separate impact node.
  if(!impact.isConnected)sections.validation.prepend(impact);
 }
 async function history(){const box=$('#history-list');box.replaceChildren(el('p','載入修改紀錄…'));try{const data=await api('history');box.replaceChildren();for(const row of data.history){const c=el('article',undefined,'history-row');c.append(el('h3',row.message),el('p',`${new Date(row.date).toLocaleString('zh-TW',{timeZone:'Asia/Taipei'})} · 提交帳號：${row.actor||'尚未取得'}（服務提交帳號不等同實際操作者）`),link('查看完整變更',row.url),button('預覽並建立還原草稿',async()=>{if(!canLeaveEditor())return;const old=await api('version',{commit:row.sha});onDraft(old.settings);open('validation');notify('已建立還原草稿；需儲存、驗證與套用後才生效。');}));box.append(c);}}catch(e){box.replaceChildren(el('p',e.message,'error'));}}
 function showArticle(row){scrolls.set(view,content.scrollTop);sections[view].hidden=true;article.hidden=false;article.replaceChildren(button('返回原清單',()=>{article.hidden=true;sections[view].hidden=false;content.scrollTop=scrolls.get(view)||0;}),el('h3',row.title||row.id),el('p',stateNames[row.state]||row.state),el('p','來源日期：'+(row.source_date||'未知')));
  if(/^https:\/\//.test(row.source_url||''))article.append(link('開啟原始來源',row.source_url));
  if(row.summary)article.append(el('p',row.summary));for(const b of row.full_analysis||[])article.append(el('h4',b.label),el('p',b.text));for(const error of row.errors||[])article.append(el('p',error,'error'));
  if(row.evidence_refs?.length)article.append(el('p','來源段落引用：'+row.evidence_refs.join('、')));
  const ops=getState().operations;const url=row.source_run_id?'https://github.com/pastfantast-glitch/ai-3d-daily/actions/runs/'+row.source_run_id:ops?.source_run_url;if(url)article.append(link('開啟來源證據與執行紀錄',url));
  article.append(el('p','未提供的正文證據不會在此補寫；核准仍須由既有審稿流程逐篇核對。','help'));content.scrollTop=0;
 }
 const batch=el('div',undefined,'studio-batch');sections.sources.querySelector('.toolbar').after(batch);
 function sourceBatch(){const s=getState();if(!s.settings)return;for(const id of selectedSources)if(!s.settings.sources.some(x=>x.id===id))selectedSources.delete(id);
  batch.replaceChildren(el('span',`已選 ${selectedSources.size} 個來源`),button('選取目前篩選來源',()=>{$('#source-list').querySelectorAll('[data-source-select]').forEach(x=>selectedSources.add(x.dataset.sourceSelect));render();}),button('清除選取',()=>{selectedSources.clear();render();}));
  const apply=options=>{if(!selectedSources.size)throw Error('請先選取來源。');onDraft(batchSources(s.settings,[...selectedSources],options));notify('批次修改已加入草稿，可復原；儲存驗證後再套用。');};
  batch.append(button('批次啟用',()=>apply({enabled:true})),button('批次暫停',()=>apply({enabled:false})));
  const topics=el('select');topics.setAttribute('aria-label','批次來源主題');for(const t of s.settings.topics){const o=el('option',t.name);o.value=t.id;topics.append(o);}batch.append(topics,button('加入主題',()=>apply({topic:topics.value,connected:true})),button('移除主題',()=>apply({topic:topics.value,connected:false})));
  for(const card of $('#source-list').children){const id=card.querySelector('[data-live-inventory]')?.dataset.liveInventory;if(!id)continue;card.querySelector('.studio-source-check')?.remove();const label=el('label','選取來源','studio-source-check'),check=el('input');check.type='checkbox';check.dataset.sourceSelect=id;check.setAttribute('aria-label','選取來源 '+s.settings.sources.find(x=>x.id===id).name);check.checked=selectedSources.has(id);check.onchange=()=>{check.checked?selectedSources.add(id):selectedSources.delete(id);sourceBatch();};label.prepend(check);card.prepend(label);
   card.querySelector('.source-health')?.remove();const h=sourceHealth(s.monitor,id),health=el('div',undefined,'source-health');health.append(el('p',`最後取得正文：${h.lastSuccess||'未知'} · 近期連續失敗：${h.failures??'未知'} 次`),el('p',`正文取得率 ${h.bodyRate===null?'—':h.bodyRate+'%'} · 批次記錄核准率 ${h.reviewRate===null?'—':h.reviewRate+'%'}（${h.observations} 次觀測；批次可能重疊，非唯一文章數）`));card.append(health);
  }
 }
 function render(){const s=getState();if(!s.settings)return;bar.replaceChildren(el('strong',remote?'設定版本衝突':s.dirty?'未儲存草稿':statusNames[s.validation?.state]||'狀態未知'),el('span','變更須儲存 → 驗證 → 套用'),button('設定影響與驗證',()=>open('validation')),button('修改紀錄',()=>open('history')),button('更新遠端狀態',()=>checkRemote()));
  if(s.validation?.state==='FAILED')bar.append(el('span',s.validation.message||'請查看驗證紀錄中的失敗原因','error'));
  renderImpact();sourceBatch();const summary=reserveBreakdown(s.operations);let reserve=sections.reserve.querySelector('.reserve-breakdown');if(!reserve){reserve=el('div',undefined,'reserve-breakdown');$('#reserve-note').after(reserve);}reserve.replaceChildren();if(!summary)reserve.append(el('p','備稿資料尚未完整取得，數量未知。'));else{reserve.append(el('p',`入庫 ${summary.total} · 下次待複核 ${summary.ready??'未知'} · 每日目標 ${summary.daily} · 備稿目標 ${summary.target} · 尚缺 ${summary.gap??'未知'}`));for(const [key,n]of Object.entries(summary.states))reserve.append(button(`${stateNames[key]||key} ${n}`,()=>{$('#reserve-filter').value=key;$('#reserve-filter').dispatchEvent(new Event('change'));}));}
 }
 async function checkRemote(){if(checking||!getState().settings)return;checking=true;try{const next=await api('load'),s=getState();if(next.sha!==s.sha||next.pending_sha!==s.pendingSha){remote=next;conflict.hidden=false;conflict.replaceChildren(el('h3','遠端設定已有修改；本機草稿已保留'),el('p',settingsImpact(s.savedSettings,next.validation?.draft||next.settings).changes.join('；')||'設定版本已變更。'),button('比較並重套本機差異',()=>{const merged=mergeSettings(s.savedSettings,s.settings,next.validation?.draft||next.settings);if(merged.conflicts.length){notify('同欄位衝突，請先手動比對：'+merged.conflicts.join('、'),true);return;}onRemote(next,merged.settings);remote=null;conflict.hidden=true;render();}),button('捨棄本機並載入遠端',()=>{if(!confirm('捨棄本機草稿並載入遠端設定？'))return;onRemote(next);remote=null;conflict.hidden=true;render();}));open('validation');render();}else if(!s.dirty){onRemote(next);render();}}catch(e){notify('遠端版本未確認：'+e.message,true);}finally{checking=false;}}
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!panel.hidden){e.preventDefault();hide();}});
 const channel=typeof BroadcastChannel==='function'?new BroadcastChannel('ai3d-settings-version'):null;
 if(channel)channel.onmessage=()=>checkRemote();window.addEventListener('focus',()=>checkRemote());
 $('#editor-form').addEventListener('input',()=>editorDirty=true);
 window.addEventListener('beforeunload',e=>{if(editorDirty){e.preventDefault();e.returnValue='';}});
 return {open,hide,render,showArticle,canLeaveEditor,checkRemote,hasConflict:()=>!!remote,announce:()=>channel?.postMessage('changed'),resetEditor:()=>editorDirty=false};
}
