const $=s=>document.querySelector(s),el=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
const states={DONE:'今日已發布',UNKNOWN:'狀態未知',INVALID_RECEIPT:'發布證據不完整',NOT_STARTED:'今日尚未開始',COLLECTING:'收集中',PUBLISHING:'發布中',HANDOFF_FAILED:'交接失敗',PUBLISH_FAILED:'發布失敗',COLLECTOR_FAILED:'收集未完成',AWAITING_HANDOFF:'等待交接',NOT_PUBLISHED:'尚未確認發布'};
const rowStates={held:'已暫緩',awaiting_review:'待審稿',rejected:'待修正',recheck_required:'等待再次核對',date_ineligible:'日期不符'};
function link(label,url){const a=el('a',label);try{const u=new URL(url);if(u.protocol!=='https:')return el('span',label);a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';}catch{return el('span',label);}return a;}
export function mountOperations(api,notify){
 let data=null,busy=false,limit={queue:10,reserve:10};
 function renderList(kind){const box=$('#'+kind+'-list');box.replaceChildren();if(!data){box.append(el('p','尚未取得資料。'));return;}
  const q=$('#'+kind+'-search').value.toLowerCase(),filter=$('#'+kind+'-filter').value;
  const rows=data[kind].filter(x=>(filter==='all'||x.state===filter)&&[x.title,x.source_url,...(x.errors||[])].join(' ').toLowerCase().includes(q));
  if(!rows.length)box.append(el('div',q||filter!=='all'?'沒有符合條件的稿件。':kind==='queue'?'目前紀錄中沒有待處理稿件。':'目前沒有已入庫備稿；新增來源並完成審稿後，合格的剩餘內容會由 Collector 保留。','empty-state'));
  for(const row of rows.slice(0,limit[kind])){const card=el('article',undefined,'editorial-card'),body=el('div');body.append(el('span',rowStates[row.state]||row.state,'pill'),el('h3',row.title||row.id),el('p','來源日期：'+(row.source_date||'未確認'),'muted'),link('查看來源 ↗',row.source_url));if(row.errors?.length){const details=el('details'),summary=el('summary','查看退件原因');details.append(summary,el('p',row.errors.join(' · ')));body.append(details);}
   const action=el('button',row.held?'恢復收錄':'暫緩收錄');action.disabled=busy||!data.controls_sha;action.onclick=async()=>{if(busy)return;busy=true;renderLists();try{const held=new Set(data.controls.held_urls);row.held?held.delete(row.source_url):held.add(row.source_url);await api('selection',{sha:data.controls_sha,controls:{schema_version:1,held_urls:[...held].sort()}});notify(row.held?'已恢復；下一次收集仍須重新驗證。':'已暫緩；稿件保留，下一次收集將略過。');await refresh();}catch(e){notify(e.message,true);}finally{busy=false;renderLists();}};card.append(body,action);box.append(card);}
  $('#'+kind+'-more').hidden=rows.length<=limit[kind];
 }
 function renderLists(){renderList('queue');renderList('reserve');}
 function render(){const status=$('#operations-status');status.replaceChildren(el('span',data.date+' · 台北時間','eyebrow'),el('h2',states[data.state]||data.state),el('p','最新已發布：'+(data.latest_date||'尚未確認')));if(data.daily_url)status.append(link('開啟本期日報 ↗',data.daily_url));for(const issue of data.issues)status.append(el('p',issue,'error'));status.append(el('small','查核時間：'+new Date(data.checked_at).toLocaleString('zh-TW',{timeZone:'Asia/Taipei'})));
  const grid=$('#supply-metrics');grid.replaceChildren();for(const [label,key] of [['正文可讀','body_readable'],['記錄核准','review_approved'],['品質與去重通過','quality_pass_unpublished'],['實際發布','published']]){const c=el('div',undefined,'panel');c.append(el('span',label),el('strong',data.counts?.[key]??'—'));grid.append(c);}const r=el('div',undefined,'panel');r.append(el('span','備稿待複核'),el('strong',data.reserve_count),el('small',`約 ${data.reserve_days} 天（每日目標 30 篇）`));grid.append(r);
  const detail=$('#operations-detail');detail.replaceChildren(el('h3','流程紀錄'),el('p','未取得的數量顯示「—」。備稿估算不代表已完成當日來源核對。','muted'));
  if(data.source_run_url)detail.append(link('查看來源 Collector ↗',data.source_run_url));for(const run of data.runs){const p=el('p');p.append(link(`${run.name} · ${run.conclusion||run.status} ↗`,run.url));detail.append(p);}detail.append(link('開啟 GitHub Actions ↗','https://github.com/pastfantast-glitch/ai-3d-daily/actions'));
  if(data.monitor_date){detail.append(el('h3','來源連通性 · '+data.monitor_date));for(const [name,row]of Object.entries(data.sources)){detail.append(el('p',`${name}：${row.status||'未知'} · 找到 ${row.candidates_found??'—'} 篇${row.reason?' · '+row.reason:''}`));}}
  detail.append(el('p',`後臺寫入金鑰到期日：${data.credential_expires_on}。到期前需更新伺服器設定。`,'muted'));
  $('#queue-note').textContent=`紀錄日期：${data.queue_date||'尚未取得'} · ${data.queue.length} 篇。`+(data.queue_complete?'':'目前使用決策紀錄，可能沒有完整標題或正文退件細節；下次 Collector 完成後更新。');$('#reserve-note').textContent=`已入庫 ${data.reserve.length} 篇；其中 ${data.reserve_count} 篇日期符合，可等待再次核對。`;renderLists();
 }
 async function refresh(){const b=$('#refresh-operations');b.disabled=true;try{data=await api('operations');render();}catch(e){data=null;$('#operations-status').replaceChildren(el('h2','狀態未知'),el('p',e.message));$('#supply-metrics').replaceChildren();$('#operations-detail').replaceChildren();for(const k of ['queue','reserve']){$('#'+k+'-note').textContent='資料取得失敗，無法確認庫存。';$('#'+k+'-more').hidden=true;}renderLists();notify(e.message,true);}finally{b.disabled=false;}}
 $('#refresh-operations').onclick=refresh;
 for(const k of ['queue','reserve']){for(const suffix of ['search','filter'])$('#'+k+'-'+suffix).addEventListener(suffix==='search'?'input':'change',()=>{limit[k]=10;renderList(k);});$('#'+k+'-more').onclick=()=>{limit[k]+=10;renderList(k);};}return{refresh};
}
