import {SETTINGS,validateSettings} from './policy.mjs';
export const PENDING='config/collection-pending.json';
export const decode=f=>JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(f.content.replace(/\s/g,'')),c=>c.charCodeAt(0))));
export function encode(value){let s='';for(const b of new TextEncoder().encode(JSON.stringify(value,null,2)+'\n'))s+=String.fromCharCode(b);return btoa(s);}
export async function snapshot(github){
 const head=(await github('/git/ref/heads/main')).object.sha;
 const active=await github(`/contents/${SETTINGS}?ref=${head}`);
 let pending=null;try{pending=await github(`/contents/${PENDING}?ref=${head}`);}catch(e){if(e.message!=='repository_404')throw e;}
 return {head,active,pending};
}
export function pendingState(s){
 if(!s.pending)return {state:'ACTIVE'};
 const p=decode(s.pending);validateSettings(p.settings);
 if(p.schema_version!==1||!/^[a-f0-9]{40}$/.test(p.base_sha||''))throw new Error('invalid_pending_settings');
 if(JSON.stringify(decode(s.active))===JSON.stringify(p.settings))return {state:'ACTIVE'};
 if(p.base_sha!==s.active.sha)return {state:'STALE',message:'生效設定已改變，請重新載入並送出驗證。'};
 return {state:'SAVED',draft:p.settings};
}
export async function validationState(s,publicRuns){
 const state=pendingState(s);if(state.state!=='SAVED')return state;
 try{
  const data=await publicRuns(s.head);
  if(!Array.isArray(data.workflow_runs)||data.total_count>100)throw new Error('incomplete_checks');
  const required=['.github/workflows/daily-contract.yml','.github/workflows/collection-settings-check.yml'];
  const runs=required.map(path=>data.workflow_runs.filter(r=>r.head_sha===s.head&&r.head_branch==='main'&&r.path===path&&['push','workflow_dispatch'].includes(r.event)).sort((a,b)=>Number(b.id)-Number(a.id)||Number(b.run_attempt)-Number(a.run_attempt))[0]);
  const failed=runs.find(r=>r?.status==='completed'&&r.conclusion!=='success');
  const waiting=runs.find(r=>r&&r.status!=='completed');
  const missing=runs.some(r=>!r);
  const run=failed||waiting||runs[1]||runs[0];
  return {...state,state:failed?'FAILED':waiting?'VALIDATING':missing?'SAVED':'PASSED',run_url:run?.html_url};
 }catch{return {...state,state:'UNKNOWN',message:'無法確認驗證結果；現行設定繼續使用。'};}
}
export async function savePending(github,body){
 const s=await snapshot(github);
 if(body.sha!==s.active.sha||(body.pending_sha||null)!==(s.pending?.sha||null))throw new Error('version_conflict');
 const settings=validateSettings(body.settings);
 const result=await github(`/contents/${PENDING}`,'PUT',{branch:'main',...(s.pending?{sha:s.pending.sha}:{}),content:encode({schema_version:1,base_sha:s.active.sha,settings}),message:'Validate proposed collection settings [collection-settings-check]'});
 return {sha:s.active.sha,pending_sha:result.content.sha,commit_url:result.commit.html_url,message:'待驗證版本已儲存；驗證通過並套用前，現行設定保持不變。'};
}
export async function activate(github,publicRuns,commit,body){
 const s=await snapshot(github);
 if(body.head!==s.head||body.pending_sha!==s.pending?.sha||body.sha!==s.active.sha)throw new Error('version_conflict');
 if((await validationState(s,publicRuns)).state!=='PASSED')throw new Error('validation_required');
 const settings=validateSettings(decode(s.pending).settings);
 // The only mutation is this fixed path, with an atomic main-head comparison.
 const result=await commit(s.head,encode(settings));
 return {commit_url:result.url,message:'驗證通過，設定已生效；下一次既有 Collector 使用此版本。'};
}
