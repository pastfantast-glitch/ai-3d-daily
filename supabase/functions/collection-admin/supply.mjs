// Read-only inventory. Approval is never inferred from a readable body or a date.
export function urlKey(value){try{const u=new URL(value);u.hash='';for(const k of [...u.searchParams.keys()])if(k.startsWith('utm_')||['fbclid','gclid'].includes(k))u.searchParams.delete(k);u.searchParams.sort();return u.href.replace(/\/$/,'');}catch{return value;}}
export const sourceMatch=(url,sources)=>{try{const host=new URL(url).hostname.replace(/^www\./,'');return sources.find(s=>{const base=new URL(s.base_url).hostname.replace(/^www\./,'');return base===host||host.endsWith('.'+base);});}catch{return undefined;}};
export function reserveInventory(backlog,reviews,{published,held,date,recentSource,settings}){
 const rows=new Map(),used=url=>published.has(url)||published.has(urlKey(url));
 const add=(x,review)=>{
  const url=x.source_url,id=x.id||x.candidate_id||url;if(!url||used(url)||published.has(id))return;
  const source=sourceMatch(url,settings?.sources||[]),sourceDate=x.source_published_at||x.source_date||'';
  const approval=review||x.review_provenance||x.reader_copy?.review_provenance;
  const approved=!!review||['verified','temporarily-unavailable','owner-held'].includes(x.refresh_status);
  const unavailable=x.refresh_status==='temporarily-unavailable';
  const activeTopic=source?.topic_ids?.some(id=>settings.topics.some(t=>t.id===id&&t.enabled))&&(!settings.navigation||settings.navigation.some(c=>c.enabled&&c.source_ids.includes(source?.id)));
  const state=held.has(url)||held.has(urlKey(url))?'held':!recentSource(sourceDate,date)?'date_ineligible':unavailable?'source_unavailable':!approved?'awaiting_review':!source?.enabled||!activeTopic?'source_disabled':'recheck_required';
  const row={id,title:x.title||x.reader_copy?.title||url,source_url:url,source_date:sourceDate,source_id:source?.id,topic_ids:source?.topic_ids||[],held:state==='held',state,approved,reviewed_on:approval?.date||null,source_run_id:approval?.source_run_id||null,summary:x.summary||x.reader_copy?.summary,full_analysis:x.full_analysis||x.reader_copy?.full_analysis,evidence_refs:x.evidence_refs||[]};
  // An inaccessible source remains unavailable even when its copy is approved.
  const prior=rows.get(urlKey(url));if(prior?.state==='source_unavailable'&&state==='recheck_required')row.state='source_unavailable';
  if(!prior||review)rows.set(urlKey(url),row);
 };
 for(const x of backlog?.items||[])add(x);
 for(const review of reviews)for(const [id,x]of Object.entries(review.items||{}))if(x.review?.approved===true)add({...x,id},review);
 return [...rows.values()];
}
export function recoveryAdvice(state,runs,diagnostic){
 if(state==='DONE')return {next_step:'本期收據核對通過；不重跑收集或發布。',action:'none'};
 if(['COLLECTING','PUBLISHING'].includes(state))return {next_step:'追蹤現有執行，不建立第二個 Collector 或發布者。',action:'wait'};
 const failed=runs.find(r=>r.conclusion==='failure'&&r.name===(state==='PUBLISH_FAILED'?'Canonical intelligence publish':'Collector handoff gate'));
 if(state==='PUBLISH_FAILED')return {action:'correct_then_resume_existing',run_url:failed?.html_url,next_step:'先修正原執行的第一個失敗步驟並通過 CI，再確認無 active writer、無有效 DONE，才接續原 Publisher 的失敗工作；不重新收集。'};
 if(state==='HANDOFF_FAILED')return {action:diagnostic?.attempts>=3?'limit_reached':'correct_then_handoff',run_url:diagnostic?.run_url||failed?.html_url,next_step:diagnostic?.attempts>=3?'已達初次加兩次修正上限，停止自動重試，檢查退件原因。':'修正退件原因與輸入後，交給既有 handoff；內容未改不得重試，最多兩次修正交接。',reason:diagnostic?.reason||null};
 if(state==='COLLECTOR_FAILED')return {action:'inspect_evidence',next_step:'檢查原 Collector 日誌與證據包；只有文案退件才由既有審稿任務續審，不盲目重跑。'};
 if(state==='NOT_STARTED')return {action:'watchdog',next_step:'交由既有 Watchdog 查核啟動條件；後臺不建立額外收集流程。'};
 return {action:'inspect',next_step:'查核既有 run 與持久化 session，資訊不足時保持未知，不視為已發布。'};
}
