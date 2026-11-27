import {urlKey,reserveInventory,recoveryAdvice,sourceMatch} from './supply.mjs';
export const CONTROL_PATH='config/editorial-selection.json';
const site='https://pastfantast-glitch.github.io/ai-3d-daily/';
export const taipeiDate=(now=new Date())=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Taipei',year:'numeric',month:'2-digit',day:'2-digit'}).format(now);
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const stable=x=>Array.isArray(x)?x.map(stable):x&&typeof x==='object'?Object.fromEntries(Object.keys(x).sort().map(k=>[k,stable(x[k])])):x;
export function validateControls(data){
 if(!data||Object.keys(data).sort().join()!=='held_urls,schema_version'||data.schema_version!==1||!Array.isArray(data.held_urls)||data.held_urls.length>500)throw new Error('invalid_editorial_controls');
 for(const u of data.held_urls){let p;try{p=new URL(u);}catch{throw new Error('invalid_editorial_controls');}if(typeof u!=='string'||u.length>1500||p.protocol!=='https:'||p.username||p.password||p.hash)throw new Error('invalid_editorial_controls');}
 if(new Set(data.held_urls).size!==data.held_urls.length)throw new Error('invalid_editorial_controls');return data;
}
export function receiptIssues(date,receipt,canonical,latest,committed){
 const ids=(canonical?.items||[]).map(x=>x.id),issues=[];
 if(receipt?.date!==date||receipt?.state!=='DONE'||canonical?.date!==date)issues.push('收據或資料日期不一致');
 if(!ids.length||ids.some(x=>typeof x!=='string'||!x)||new Set(ids).size!==ids.length||!same(receipt?.canonical?.ids,ids)||receipt?.canonical?.item_count!==ids.length)issues.push('文章 IDs 或數量不一致');
 if(receipt?.qa?.pages!=='pass'||receipt?.site_url!==site||receipt?.daily_url!==site+date+'/')issues.push('Pages 驗證或發布網址不一致');
 if(!same(stable(committed),stable(canonical)))issues.push('發布 commit 與目前資料不一致');
 const h=latest?.health;
 if(latest?.date!==date||latest?.publish_commit_sha!==receipt?.publish_commit_sha||latest?.site_url!==site||latest?.receipt!==`data/publish/${date}.done.json`||h?.date!==date||h?.publish_commit_sha!==receipt?.publish_commit_sha||h?.state!=='HEALTHY'||h?.checks?.pages!=='pass')issues.push('latest-success 尚未對應本期發布');
 const extras=canonical?.topic_items||[];
 if(extras.length&&(!same(receipt?.topics?.ids,extras.map(x=>x.id))||receipt?.topics?.item_count!==extras.length))issues.push('主題文章 IDs 或數量不一致');return issues;
}
export function recentSource(date,today){
 if(!/^\d{4}-\d{2}-\d{2}$/.test(date||''))return false;
 const parsed=new Date(date+'T00:00:00Z');if(!Number.isFinite(parsed.getTime())||parsed.toISOString().slice(0,10)!==date)return false;
 const d=new Date(today+'T00:00:00Z'),month=d.getUTCMonth();d.setUTCFullYear(d.getUTCFullYear()-1);if(d.getUTCMonth()!==month)d.setUTCDate(0);
 return date>=d.toISOString().slice(0,10)&&date<=today;
}
export async function operations(github,publicRuns,now=new Date()){
 const date=taipeiDate(now),head=(await github('/git/ref/heads/main')).object.sha;
 const file=async(path,ref=head)=>{try{const r=await github(`/contents/${path}?ref=${ref}`);return{sha:r.sha,data:JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(r.content.replace(/\s/g,'')),c=>c.charCodeAt(0))))};}catch(e){if(e.message==='repository_404')return{sha:null,data:null};throw e;}};
 const paths=['data/publish/latest-success.json',`data/publish/${date}.done.json`,`data/daily/${date}.json`,'data/ops/collection-monitor.json','data/candidates/rolling-backlog.json',CONTROL_PATH,'data/candidates/published-registry-snapshot.json',`data/candidates/decision-ledger/${date}.json`,`data/candidates/collection-session/${date}.json`];
 const files=await Promise.all(paths.map(p=>file(p)));const [latest,receipt,canonical,monitor,backlog,controls,registry,ledger,session]=files.map(f=>f.data);
 const held=new Set(validateControls(controls||{schema_version:1,held_urls:[]}).held_urls);
 let state='UNKNOWN',issues=[],runs=[];
 if(receipt){const sha=receipt.publish_commit_sha;const committed=/^[a-f0-9]{40}$/.test(sha||'')?(await file(`data/daily/${date}.json`,sha)).data:null;issues=receiptIssues(date,receipt,canonical,latest,committed);state=issues.length?'INVALID_RECEIPT':'DONE';}
 else{try{runs=await publicRuns(date);const active=runs.filter(r=>['queued','in_progress','waiting','pending','requested'].includes(r.status));const collectors=runs.filter(r=>r.name==='Autonomous daily Collector'&&r.conclusion!=='skipped');const failed=runs.find(r=>['Canonical intelligence publish','Collector handoff gate'].includes(r.name)&&r.conclusion==='failure');
 if(active.some(r=>r.name==='Canonical intelligence publish'))state='PUBLISHING';else if(active.some(r=>r.name==='Autonomous daily Collector'))state='COLLECTING';else if(failed){state=failed.name==='Collector handoff gate'?'HANDOFF_FAILED':'PUBLISH_FAILED';issues.push('既有流程失敗，請開啟執行紀錄查看第一個失敗步驟。');}else if(session&&canonical?.items?.length)state='AWAITING_HANDOFF';else if(collectors.length){state=collectors[0].conclusion==='failure'?'COLLECTOR_FAILED':'NOT_PUBLISHED';if(state==='COLLECTOR_FAILED')issues.push('Collector 未完成；下列候選與品質資訊以最近實際紀錄為準。');}else state='NOT_STARTED';
 }catch{issues.push('無法讀取 GitHub Actions，即時執行狀態未知。');}}
 const published=new Set((registry?.published_sources||[]).flatMap(x=>[x.id,x.source_url,urlKey(x.source_url)]));
 if(state==='DONE')for(const i of [...(canonical.items||[]),...(canonical.topic_items||[])]){published.add(i.id);published.add(i.source_url);published.add(urlKey(i.source_url));}
 const settings=(await file('config/collection-admin.json')).data||{topics:[],sources:[]};
 let reviewComplete=true,reviewFiles=[];
 try{
  const directory=await github(`/contents/data/editorial-reviews?ref=${head}`);
  const cutoff=new Date(date+'T00:00:00Z');cutoff.setUTCDate(cutoff.getUTCDate()-180);
  const paths=directory.filter(x=>x.type==='file'&&/^20\d{2}-\d{2}-\d{2}(?:-[1-9]\d*)?\.json$/.test(x.name)&&x.name.slice(0,10)<=date&&x.name.slice(0,10)>=cutoff.toISOString().slice(0,10)).map(x=>'data/editorial-reviews/'+x.name);
  if(paths.length>500)throw Error('review_inventory_limit');
  for(let i=0;i<paths.length;i+=6)reviewFiles.push(...(await Promise.all(paths.slice(i,i+6).map(p=>file(p)))).map(x=>x.data).filter(Boolean));
 }catch(e){if(e.message!=='repository_404'){reviewComplete=false;issues.push('審稿備稿索引讀取不完整；庫存數量暫不可確認。');}}
 const usableMonitor=monitor?.date===date?monitor:null;
 const raw=monitor?.pending_queue||monitor?.articles||(ledger?.items||[]).map(x=>({id:x.candidate_id,title:x.candidate_id,source_url:x.source_url,source_date:'',errors:x.editorial_errors||[x.reason_code||x.decision],review_status:x.decision}));
 const queue=raw.filter(x=>!published.has(x.id)&&!published.has(urlKey(x.source_url))&&x.errors?.length).map(x=>({id:x.id||x.source_url,title:x.title||x.source_url,source_url:x.source_url,source_date:x.source_date||'',errors:x.errors,held:held.has(x.source_url),state:held.has(x.source_url)?'held':x.errors.some(e=>e.includes('awaiting-editorial-review'))?'awaiting_review':'rejected'}));
 const reserve=reserveInventory(backlog,reviewFiles,{published,held,date,recentSource,settings});
 for(const row of queue){const original=raw.find(x=>urlKey(x.source_url)===urlKey(row.source_url));Object.assign(row,{first_seen:original?.first_seen||monitor?.date,last_attempt_on:original?.last_attempt_on||monitor?.date,evidence_date:original?.evidence_date||monitor?.date,source_run_id:original?.source_run_id||monitor?.source_run_id,source_head_sha:original?.source_head_sha||monitor?.source_head_sha});if(!row.held&&original?.state)row.state=original.state;if(!row.held&&row.source_date&&!recentSource(row.source_date,date))row.state='date_ineligible';}
 const intakeFile=await file('config/collection-intake.json');
 const intake=intakeFile.data?.items||[];
 for(const item of intake)if(!published.has(urlKey(item.source_url))&&!queue.some(x=>urlKey(x.source_url)===urlKey(item.source_url))&&!reserve.some(x=>urlKey(x.source_url)===urlKey(item.source_url)))queue.push({...item,id:item.source_url,title:item.source_url,source_date:'',errors:['owner-recommended'],state:'recommended',held:false,first_seen:item.requested_on});
 for(const row of queue){const s=sourceMatch(row.source_url,settings.sources);row.source_id=s?.id;row.topic_ids=s?.topic_ids||[];}
 // Merged approval is not still awaiting review. Keep held rows manageable.
 for(let i=queue.length-1;i>=0;i--)if(!queue[i].held&&reserve.some(x=>x.approved&&urlKey(x.source_url)===urlKey(queue[i].source_url)))queue.splice(i,1);
 for(const url of held)if(!queue.some(x=>x.source_url===url)&&!reserve.some(x=>x.source_url===url))queue.push({id:url,title:url,source_url:url,source_date:'',errors:['owner-held-for-later'],held:true,state:'held'});
 const eligible=reviewComplete?reserve.filter(x=>x.state==='recheck_required').length:null;
 const target=settings.topics.find(x=>x.id==='ai-3d')?.target_items||30;
 const reviewed=reviewFiles.filter(x=>x.date===date);
 const review_progress={date,source_run_id:usableMonitor?.source_run_id||reviewed[0]?.source_run_id||null,merged_approved:new Set(reviewed.flatMap(x=>Object.values(x.items||{}).filter(r=>r.review?.approved===true).map(r=>urlKey(r.source_url)))).size,awaiting:queue.filter(x=>x.state==='awaiting_review').length,local_progress:'unknown',note:'只列已合併核准與 Collector 紀錄；本機草稿及未合併 PR 進度未取得。'};
 const diagnostic=(await file(`data/ops/handoff/${date}.json`)).data;
 const recovery=recoveryAdvice(state,runs,diagnostic);
 if(state==='HANDOFF_FAILED'&&diagnostic?.reason)issues.unshift(diagnostic.reason);
 const published_items=state==='DONE'?[...(canonical.items||[]),...(canonical.topic_items||[])].map(x=>({id:x.id,title:x.title,summary:x.summary,full_analysis:x.full_analysis,source_url:x.source_url,source_id:x.source_id,topic_ids:x.topic_ids,source_date:x.source_published_at||x.source_date||'',state:'published'})):[];
 const source_supply=settings.sources.map(s=>({source_id:s.id,name:s.name,...(usableMonitor?.sources?.[s.id]||{}),published:state==='DONE'?published_items.filter(x=>sourceMatch(x.source_url,settings.sources)?.id===s.id).length:null,reserve:reviewComplete?reserve.filter(x=>x.source_id===s.id&&x.state==='recheck_required').length:null}));
 const supply=usableMonitor?.counts||canonical?.metadata?.content_supply||null;
 return{date,checked_at:now.toISOString(),head_sha:head,state,issues,latest_date:latest?.date||null,daily_url:state==='DONE'?receipt.daily_url:null,publish_commit:state==='DONE'?receipt.publish_commit_sha:null,counts:supply?{...supply,published:state==='DONE'?canonical.items.length:null}:null,
 queue,reserve,published_items,review_progress,recovery,source_supply,coverage:settings.sources.map(s=>({...s,...(monitor?.source_coverage?.[s.id]||monitor?.sources?.[s.id]||{status:'unknown'}),checked_on:monitor?.source_coverage?.[s.id]?.checked_on||((monitor?.sources?.[s.id]?.status&&monitor.sources[s.id].status!=='not-scheduled')?monitor.date:null)})),intake,intake_sha:intakeFile.sha,queue_overflow:monitor?.queue_overflow||0,reserve_complete:reviewComplete,reserve_target:target*2,daily_target:target,reserve_count:eligible,reserve_days:eligible===null?null:Math.round(eligible/target*10)/10,queue_date:monitor?.date||ledger?.date||null,queue_complete:!!monitor&&monitor.queue_complete!==false,monitor_date:monitor?.date||null,sources:monitor?.sources||{},runs:runs.map(r=>({id:r.id,name:r.name,status:r.status,conclusion:r.conclusion,url:r.html_url})),
 source_run_url:usableMonitor?`https://github.com/pastfantast-glitch/ai-3d-daily/actions/runs/${usableMonitor.source_run_id}`:null,controls_sha:files[5].sha,controls:controls||{schema_version:1,held_urls:[]},credential_expires_on:'2026-12-18'};
}
