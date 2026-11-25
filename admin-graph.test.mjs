import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {connectTopic,connectionState,stageData} from './admin-graph-model.mjs';
const fixture=()=>{const s=JSON.parse(readFileSync(new URL('./scripts/fixtures/collection-admin.json',import.meta.url)));s.topics.push({...s.topics[0],id:'photography',name:'攝影',include_terms:['photo'],enabled:false});return s;};
test('graph changes only source topic membership and does not mutate the active version',()=>{
 const s=fixture(),id=s.sources[0].id,before=structuredClone(s),next=connectTopic(s,id,'photography');
 assert.deepEqual(s,before);assert.deepEqual(next.sources[0].topic_ids,['ai-3d','photography']);assert.deepEqual(next.topics,s.topics);
 assert.deepEqual(connectTopic(next,id,'photography'),next);
 assert.deepEqual(connectTopic(next,id,'photography',false),s);
 assert.equal(connectionState(s,id,'photography'),'draft');assert.equal(connectionState(s,id,'ai-3d'),'active');
});
test('connections cannot target stages, orphan a source, or remove the final AI/3D supply',()=>{
 const s=fixture(),id=s.sources[0].id;
 assert.throws(()=>connectTopic(s,id,'publish'));
 assert.throws(()=>connectTopic(s,'publish','ai-3d'));
 assert.throws(()=>connectTopic(s,id,'ai-3d',false),/至少/);
 let next=connectTopic(s,id,'photography');next.sources.forEach(x=>x.enabled=x.id===id);
 assert.throws(()=>connectTopic(next,id,'ai-3d',false),/AI／3D/);
});
test('stage badges preserve unknowns and never equate approval with publication',()=>{
 const empty=stageData(null,null);assert.match(empty.find(x=>x.id==='evidence').value,/—/);assert.equal(empty.find(x=>x.id==='publish').value,'狀態未知');
 const waiting=stageData({date:'2026-11-25',state:'AWAITING_HANDOFF',counts:{review_approved:20,published:0},queue:[],reserve_count:0},null);
 assert.equal(waiting.find(x=>x.id==='publish').value,'AWAITING_HANDOFF');
 const done=stageData({date:'2026-11-25',state:'DONE',counts:{published:12},reserve_count:0},null);
 assert.equal(done.find(x=>x.id==='publish').value,'已發布 12 篇');
});
