import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {connectTopic,moveConnection,connectionState,stageData} from './admin-graph-model.mjs';
import {zoomAt,fitNodes,workspaceState,editHistory,changeSummary} from './admin-graph-workspace.mjs';
import {scopedArticles} from './admin-graph-details.mjs';
import {validateSettings} from './supabase/functions/collection-admin/policy.mjs';
const fixture=()=>{const s=JSON.parse(readFileSync(new URL('./scripts/fixtures/collection-admin.json',import.meta.url)));s.topics.push({...s.topics[0],id:'photography',name:'攝影',include_terms:['photo'],enabled:false});return s;};
test('wheel zoom anchors the pointer and fit covers selected bounds',()=>{
 const c={zoom:1,x:500,y:400},p={x:120,y:80},n=zoomAt(c,1.4,p);
 assert.ok(Math.abs((c.x+p.x)/c.zoom-(n.x+p.x)/n.zoom)<1e-9);assert.ok(Math.abs((c.y+p.y)/c.zoom-(n.y+p.y)/n.zoom)<1e-9);
 assert.equal(zoomAt(c,100,p).zoom,2);assert.equal(zoomAt(c,.01,p).zoom,.02);
 const f=fitNodes([{x:500,y:400,width:255,height:140}],800,600);assert.ok(f.zoom>0);assert.equal(fitNodes([],800,600),null);
 const many=fitNodes([{x:30,y:35,width:255,height:2600}],800,600);assert.ok(2600*many.zoom<=600-80);
});
test('persisted workspace tolerates corruption and stores only presentation fields',()=>{
 const s=workspaceState({schema:1,positions:[null,42,['source:example',{x:20,y:30}],['bad',{x:3,y:4}]],camera:{zoom:NaN},mode:'operations',token:'SECRET',settings:{}});
 assert.deepEqual(s.positions,[['source:example',{x:20,y:30}]]);assert.equal(s.mode,'operations');assert.equal(s.camera.zoom,1);assert.ok(!JSON.stringify(s).includes('SECRET'));
});
test('undo redo restores settings plus layout and a new edit clears the redo branch',()=>{
 const h=editHistory(),s=fixture();h.reset({settings:s,positions:[]});const next=connectTopic(s,s.sources[0].id,'photography');h.push({settings:next,positions:[['source:a',{x:90,y:90}]]});
 assert.deepEqual(h.undo().settings,s);assert.deepEqual(h.redo().settings,next);h.undo();h.push({settings:s,positions:[['source:a',{x:50,y:50}]]});assert.equal(h.canRedo,false);
 assert.ok(changeSummary(s,next).some(x=>x.includes('新增連線')));
});
test('node details stay scoped by source/topic and include published cards',()=>{
 const settings=fixture(),source=settings.sources[0],row={id:'a',source_id:source.id,source_url:source.base_url,state:'published'};
 const data={settings,operations:{queue:[],reserve:[],published_items:[row]}};
 assert.deepEqual(scopedArticles('source:'+source.id,data),[row]);assert.deepEqual(scopedArticles('topic:photography',data),[]);assert.deepEqual(scopedArticles('stage:reserve',data),[]);
 data.operations.queue=[{...row,id:'q',state:'awaiting_review'}];data.operations.reserve=[{...row,id:'r',state:'date_ineligible'}];
 assert.deepEqual(scopedArticles('stage:publish',data),[row]);assert.deepEqual(scopedArticles('stage:review',data),data.operations.queue);assert.deepEqual(scopedArticles('stage:reserve',data),data.operations.reserve);
});
test('graph changes only source topic membership and does not mutate the active version',()=>{
 const s=fixture(),id=s.sources[0].id,before=structuredClone(s),next=connectTopic(s,id,'photography');
 assert.deepEqual(s,before);assert.deepEqual(next.sources[0].topic_ids,['ai-3d','photography']);assert.deepEqual(next.topics,s.topics);
 assert.deepEqual(connectTopic(next,id,'photography'),next);
 assert.deepEqual(connectTopic(next,id,'photography',false),s);
 assert.equal(connectionState(s,id,'photography'),'draft');assert.equal(connectionState(s,id,'ai-3d'),'active');
});
test('disconnected drafts pause sources, preserve records, and cannot save without primary supply',()=>{
 const s=fixture(),id=s.sources[0].id;
 assert.throws(()=>connectTopic(s,id,'publish'));
 assert.throws(()=>connectTopic(s,'publish','ai-3d'));
 const disconnected=connectTopic(s,id,'ai-3d',false);
 assert.deepEqual(disconnected.sources[0].topic_ids,[]);assert.equal(disconnected.sources[0].enabled,false);assert.equal(disconnected.sources.length,s.sources.length);
 validateSettings(disconnected);
 const reconnected=connectTopic(disconnected,id,'ai-3d');assert.equal(reconnected.sources[0].enabled,false);assert.deepEqual(reconnected.sources[0].topic_ids,['ai-3d']);
 const broken=structuredClone(disconnected);broken.sources[0].enabled=true;assert.throws(()=>validateSettings(broken),/停用/);
 let next=connectTopic(s,id,'photography');next.sources.forEach(x=>x.enabled=x.id===id);
 next=connectTopic(next,id,'ai-3d',false);assert.throws(()=>validateSettings(next),/AI／3D/);
 const h=editHistory();h.reset({settings:s});h.push({settings:disconnected});assert.deepEqual(h.undo().settings,s);assert.deepEqual(h.redo().settings,disconnected);
});

test('camera and nodes cross former boundaries and fit/zoom preserve negative coordinates',()=>{
 const c={zoom:.7,x:-900000,y:800000},point={x:230,y:125},n=zoomAt(c,1.1,point);
 assert.ok(Math.abs((n.x+point.x)/n.zoom-(c.x+point.x)/c.zoom)<1e-8);
 const saved=workspaceState({schema:2,camera:c,positions:[['source:test',{x:-45000,y:99000}],['topic:bad',{x:Infinity,y:0}]]});
 assert.deepEqual(saved.camera,c);assert.deepEqual(saved.positions,[['source:test',{x:-45000,y:99000}]]);
 const f=fitNodes([{x:-10000,y:-9000,width:255,height:140}],800,600);
 assert.equal((-10000+255/2)*f.zoom-f.x,400);assert.equal((-9000+140/2)*f.zoom-f.y,300);
});

test('endpoint rewiring is atomic, preserves enabled state and rejects fixed routes',()=>{
 const s=fixture(),id=s.sources[0].id,rewired=moveConnection(s,id,'ai-3d','photography');
 assert.deepEqual(rewired.sources[0].topic_ids,['photography']);assert.equal(rewired.sources[0].enabled,s.sources[0].enabled);
 assert.deepEqual(moveConnection(s,id,'ai-3d','ai-3d'),s);
 assert.equal(moveConnection(s,id,'ai-3d').sources[0].enabled,false);
 assert.throws(()=>moveConnection(s,id,'ai-3d','publish'));
 assert.throws(()=>moveConnection(s,id,'photography','ai-3d'));
 assert.deepEqual(s.sources[0].topic_ids,['ai-3d']);
});
test('stage badges preserve unknowns and never equate approval with publication',()=>{
 const empty=stageData(null,null);assert.match(empty.find(x=>x.id==='evidence').value,/—/);assert.equal(empty.find(x=>x.id==='publish').value,'狀態未知');
 const waiting=stageData({date:'2026-11-25',state:'AWAITING_HANDOFF',counts:{review_approved:20,published:0},queue:[],reserve_count:0},null);
 assert.equal(waiting.find(x=>x.id==='publish').value,'AWAITING_HANDOFF');
 const done=stageData({date:'2026-11-25',state:'DONE',counts:{published:12},reserve_count:0},null);
 assert.equal(done.find(x=>x.id==='publish').value,'已發布 12 篇');
});
