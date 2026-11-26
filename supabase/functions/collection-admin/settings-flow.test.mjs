import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {encode,validationState,activate,savePending} from './settings-flow.mjs';
const active=JSON.parse(fs.readFileSync(new URL('../../../config/collection-admin.json',import.meta.url)));
const draft=structuredClone(active);draft.sources[0].name+=' draft';
const a='a'.repeat(40),b='b'.repeat(40),h='c'.repeat(40);
const snapshot={head:h,active:{sha:a,content:encode(active)},pending:{sha:b,content:encode({schema_version:1,base_sha:a,settings:draft})}};
const run={id:1,head_sha:h,head_branch:'main',path:'.github/workflows/daily-contract.yml',event:'push',status:'completed',conclusion:'success'};
test('only exact main contract run can approve a pending version',async()=>{
 for(const [patch,expected] of [[{},'PASSED'],[{status:'in_progress'},'VALIDATING'],[{conclusion:'failure'},'FAILED'],[{head_sha:a},'SAVED'],[{event:'pull_request'},'SAVED'],[{path:'other.yml'},'SAVED']]){
  assert.equal((await validationState(snapshot,async()=>({total_count:1,workflow_runs:[{...run,...patch},{...run,path:'.github/workflows/collection-settings-check.yml'}]}))).state,expected);
 }
 assert.equal((await validationState(snapshot,async()=>{throw Error('rate limit')})).state,'UNKNOWN');
 assert.equal((await validationState({...snapshot,active:{...snapshot.active,sha:b}},async()=>{})).state,'STALE');
});
test('save never changes active settings; activation is guarded and conflict is never retried',async()=>{
 let writes=[],commits=[];
 const github=async(path,method,body)=>{
  if(method==='PUT'){writes.push({path,body});return {content:{sha:b},commit:{html_url:'https://example.com'}};}
  if(path==='/git/ref/heads/main')return {object:{sha:h}};
  if(path.includes('collection-pending'))return snapshot.pending;
  if(path.includes('collection-admin'))return snapshot.active;
  throw Error(path);
 };
 await savePending(github,{sha:a,pending_sha:b,settings:draft});
 assert.deepEqual(writes.map(x=>x.path),['/contents/config/collection-pending.json']);
 await assert.rejects(savePending(github,{sha:a,pending_sha:a,settings:draft}),/version_conflict/);
 const body={sha:a,pending_sha:b,head:h};
 const commit=async(head,content)=>{commits.push({head,content});return {url:'https://example.com'}};
 await assert.rejects(activate(github,async()=>({total_count:1,workflow_runs:[{...run,conclusion:'failure'}]}),commit,body),/validation_required/);
 await assert.rejects(activate(github,async()=>({total_count:1,workflow_runs:[run,{...run,path:'.github/workflows/collection-settings-check.yml'}]}),commit,{...body,head:a}),/version_conflict/);
 assert.equal(commits.length,0);
 await activate(github,async()=>({total_count:1,workflow_runs:[run,{...run,path:'.github/workflows/collection-settings-check.yml'}]}),commit,body);
 assert.equal(commits.length,1);assert.equal(commits[0].head,h);assert.deepEqual(JSON.parse(Buffer.from(commits[0].content,'base64')),draft);
 let calls=0;await assert.rejects(activate(github,async()=>({total_count:1,workflow_runs:[run,{...run,path:'.github/workflows/collection-settings-check.yml'}]}),async()=>{calls++;throw Error('version_conflict')},body));assert.equal(calls,1);
});

test('save permits a paused unconnected source but never accepts draft validation bypass',async()=>{
 const paused=structuredClone(active);paused.sources[0].enabled=false;paused.sources[0].topic_ids=[];
 let writes=0;
 const github=async(path,method)=>{if(method==='PUT'){writes++;return {content:{sha:b},commit:{html_url:'https://example.com'}};}if(path==='/git/ref/heads/main')return {object:{sha:h}};if(path.includes('collection-pending'))return snapshot.pending;if(path.includes('collection-admin'))return snapshot.active;throw Error(path);};
 await savePending(github,{sha:a,pending_sha:b,settings:paused});assert.equal(writes,1);
 paused.sources.forEach(s=>s.enabled=false);
 await assert.rejects(savePending(github,{sha:a,pending_sha:b,settings:paused,draft:true}),/AI／3D/);assert.equal(writes,1);
});
