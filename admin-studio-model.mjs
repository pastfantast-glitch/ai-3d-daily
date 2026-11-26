import {validateGraphDraft} from './admin-graph-model.mjs';
import {changeSummary} from './admin-graph-workspace.mjs';
const equal=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
export function settingsImpact(before,after){
 const topics=after.topics.map(t=>({id:t.id,name:t.name,enabled:t.enabled,
  before:before.sources.filter(s=>s.enabled&&s.topic_ids.includes(t.id)).length,
  after:after.sources.filter(s=>s.enabled&&s.topic_ids.includes(t.id)).length}));
 return {changes:changeSummary(before,after),topics,warnings:topics.filter(t=>t.enabled&&!t.after).map(t=>`${t.name} 沒有啟用來源，無法供稿。`),
  timing:'驗證通過並套用後，下一次既有 Collector 才使用新設定；進行中的批次與已發布文章保留原設定。'};
}
export function batchSources(settings,ids,{enabled,topic,connected}={}){
 const next=structuredClone(settings),chosen=new Set(ids);
 if(!chosen.size||[...chosen].some(id=>!next.sources.some(s=>s.id===id)))throw Error('請選取現有來源。');
 if(topic&&!next.topics.some(t=>t.id===topic))throw Error('請選取有效主題。');
 for(const s of next.sources.filter(s=>chosen.has(s.id))){
  if(topic)s.topic_ids=connected?[...new Set([...s.topic_ids,topic])]:s.topic_ids.filter(id=>id!==topic);
  if(enabled!==undefined)s.enabled=enabled;
  if(!s.topic_ids.length){if(enabled===true)throw Error(`${s.name} 尚未連接主題，不能啟用。`);s.enabled=false;}
 }
 return validateGraphDraft(next);
}
// Three-way merge only disjoint fields; never silently overwrite a remote edit.
export function mergeSettings(base,local,remote){
 const next=structuredClone(remote),conflicts=[];
 for(const group of ['sources','topics']){
  const keys=new Set([...base[group],...local[group],...remote[group]].map(x=>x.id));
  for(const id of keys){const b=base[group].find(x=>x.id===id),l=local[group].find(x=>x.id===id),r=remote[group].find(x=>x.id===id);
   if(equal(l,b))continue;
   if(!b||!l||!r){if(!equal(r,b)&&!equal(r,l)){conflicts.push(`${group}/${id}`);continue;}next[group]=next[group].filter(x=>x.id!==id);if(l)next[group].push(structuredClone(l));continue;}
   const target=next[group].find(x=>x.id===id);
   for(const key of Object.keys(l)){if(equal(l[key],b[key]))continue;if(!equal(r[key],b[key])&&!equal(r[key],l[key]))conflicts.push(`${group}/${id}/${key}`);else target[key]=structuredClone(l[key]);}
  }
 }
 if(conflicts.length)return {conflicts,settings:null};
 return {conflicts,settings:validateGraphDraft(next)};
}
export function sourceHealth(monitor,id){
 const seen=new Set(),rows=[];
 for(const h of [...(monitor?.yield_history||[]),...(monitor?[monitor]:[])]){
  const s=h.sources?.[id],key=h.source_run_id||`${h.date}:${h.mode}`;
  if(!s||s.status==='not-scheduled'||seen.has(key))continue;seen.add(key);rows.push({...s,date:h.date,observed_at:h.observed_at});
 }
 rows.sort((a,b)=>(a.observed_at||a.date||'').localeCompare(b.observed_at||b.date||''));
 const success=[...rows].reverse().find(x=>x.status==='checked'&&x.evidence_extracted>0);
 let failures=0;for(const row of [...rows].reverse()){if(['blocked','unavailable'].includes(row.status))failures++;else break;}
 const rate=(num,den)=>{const valid=rows.filter(x=>Number.isFinite(x[num])&&Number.isFinite(x[den])&&x[den]>0);if(!valid.length)return null;const a=valid.reduce((v,x)=>v+x[num],0),b=valid.reduce((v,x)=>v+x[den],0);return a<=b?Math.round(a/b*100):null;};
 return {observations:rows.length,lastSuccess:success?.observed_at||success?.date||null,failures:rows.length?failures:null,bodyRate:rate('evidence_extracted','candidates_found'),reviewRate:rate('review_approved','evidence_extracted'),latest:rows.at(-1)};
}
export function reserveBreakdown(ops){
 if(!ops||ops.reserve_complete!==true)return null;
 const states={};for(const row of ops.reserve||[])states[row.state]=(states[row.state]||0)+1;
 const ready=Number.isInteger(ops.reserve_count)?ops.reserve_count:null,target=ops.reserve_target||60;
 return {total:ops.reserve.length,ready,states,target,daily:ops.daily_target||30,gap:ready===null?null:Math.max(0,target-ready)};
}
export function heldSelection(controls,rows,urls,held){
 const allowed=new Set(rows.map(r=>r.source_url)),next=new Set(controls.held_urls);
 for(const url of new Set(urls)){if(!allowed.has(url))throw Error('稿件清單已變更，請重新選取。');held?next.add(url):next.delete(url);}
 return {schema_version:1,held_urls:[...next].sort()};
}
