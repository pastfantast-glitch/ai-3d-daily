import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {batchSources,mergeSettings,settingsImpact,sourceHealth,reserveBreakdown,heldSelection} from './admin-studio-model.mjs';
import {validateSettings} from './supabase/functions/collection-admin/policy.mjs';
const fixture=()=>JSON.parse(fs.readFileSync(new URL('./scripts/fixtures/collection-admin.json',import.meta.url)));
test('batch source changes are immutable drafts and cannot bypass primary supply guard',()=>{
 const s=fixture(),ids=s.sources.map(x=>x.id),next=batchSources(s,ids,{enabled:false});assert.ok(s.sources.some(x=>x.enabled));assert.ok(next.sources.every(x=>!x.enabled));assert.throws(()=>validateSettings(next));
 const disconnected=batchSources(s,[ids[0]],{topic:'ai-3d',connected:false});assert.equal(disconnected.sources[0].enabled,false);assert.throws(()=>batchSources(disconnected,[ids[0]],{enabled:true}));assert.throws(()=>batchSources(s,['missing'],{enabled:true}));
 assert.ok(settingsImpact(s,next).warnings.length);assert.ok(settingsImpact(s,next).changes.length);
});
test('three-way conflict handling preserves disjoint remote changes and refuses overlapping edits',()=>{
 const b=fixture(),l=structuredClone(b),r=structuredClone(b);l.sources[0].name='Local';r.sources[1].name='Remote';
 const merged=mergeSettings(b,l,r);assert.deepEqual(merged.conflicts,[]);assert.equal(merged.settings.sources[0].name,'Local');assert.equal(merged.settings.sources[1].name,'Remote');assert.notEqual(r.sources[0].name,'Local');
 r.sources[0].name='Conflicting';const failed=mergeSettings(b,l,r);assert.equal(failed.settings,null);assert.match(failed.conflicts[0],/name/);
 const removed=structuredClone(b);removed.sources.shift();assert.equal(mergeSettings(b,removed,r).settings,null);
});
test('health uses bounded actual observations, skips unscheduled batches and leaves unknowns unknown',()=>{
 assert.equal(sourceHealth(null,'x').failures,null);
 const monitor={date:'2026-11-26',source_run_id:'3',sources:{x:{status:'unavailable'}},yield_history:[
 {date:'2026-11-24',source_run_id:'1',sources:{x:{status:'checked',evidence_extracted:8,candidates_found:10,review_approved:4}}},
 {date:'2026-11-25',source_run_id:'2',sources:{x:{status:'blocked'}}},
 {date:'2026-11-26',source_run_id:'3',sources:{x:{status:'unavailable'}}}]};
 const h=sourceHealth(monitor,'x');assert.equal(h.observations,3);assert.equal(h.failures,2);assert.equal(h.lastSuccess,'2026-11-24');assert.equal(h.bodyRate,80);assert.equal(h.reviewRate,50);
 assert.equal(sourceHealth({sources:{x:{status:'not-scheduled'}},date:'2026-11-26'},'x').bodyRate,null);
});
test('reserve total, eligible stock and targets never equate to approved publication',()=>{
 assert.equal(reserveBreakdown({reserve_complete:false,reserve:[]}),null);
 const b=reserveBreakdown({reserve_complete:true,reserve:[{state:'held'},{state:'date_ineligible'},{state:'recheck_required'}],reserve_count:1,reserve_target:60});
 assert.equal(b.total,3);assert.equal(b.ready,1);assert.equal(b.gap,59);assert.equal(b.states.held,1);
});
test('batch holds only change the requested existing URLs and preserve others',()=>{
 const c={schema_version:1,held_urls:['https://example.com/old']},rows=[{source_url:'https://example.com/new'}];
 const next=heldSelection(c,rows,['https://example.com/new'],true);assert.equal(next.held_urls.length,2);assert.equal(c.held_urls.length,1);
 assert.throws(()=>heldSelection(c,rows,['https://example.com/unknown'],true));
 assert.deepEqual(heldSelection(next,rows,['https://example.com/new'],false),c);
});
