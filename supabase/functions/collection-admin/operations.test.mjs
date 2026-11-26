import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';
import {receiptIssues,operations,validateControls,recentSource,taipeiDate} from './operations.mjs';
import {reserveInventory,recoveryAdvice,urlKey} from './supply.mjs';
test('inventory includes merged reserve, removes published duplicates and never counts unavailable or unreviewed copy',()=>{
 const settings={topics:[{id:'ai-3d',enabled:true}],sources:[{id:'example',base_url:'https://example.com/',enabled:true,topic_ids:['ai-3d']}]};
 const a={source_url:'https://www.example.com/new',source_published_at:'2026-11-18',title:'Approved',review:{approved:true}};
 const opts={published:new Set(['https://example.com/used']),held:new Set(),date:'2026-11-19',recentSource,settings};
 const reviews=[{date:'2026-11-18',source_run_id:123,items:{a,b:{...a,source_url:'https://example.com/used?utm_source=x'}}}];
 const rows=reserveInventory({items:[{...a,refresh_status:'temporarily-unavailable'},{...a,source_url:'https://example.com/unreviewed'}]},reviews,opts);
 assert.equal(rows.length,2);assert.equal(rows.find(x=>x.title==='Approved'&&x.approved).state,'source_unavailable');assert.equal(rows.find(x=>x.source_url.endsWith('unreviewed')).state,'awaiting_review');
 const ready=reserveInventory(null,reviews,opts);assert.equal(ready.length,1);assert.equal(ready[0].state,'recheck_required');assert.equal(ready[0].source_run_id,123);
 assert.equal(reserveInventory(null,reviews,{...opts,held:new Set([a.source_url])})[0].state,'held');
 assert.equal(urlKey('https://example.com/a?utm_source=x'),'https://example.com/a');
});
test('recovery distinguishes failed Publisher from bounded handoff and never reopens DONE',()=>{
 assert.equal(recoveryAdvice('DONE',[],null).action,'none');assert.equal(recoveryAdvice('PUBLISHING',[],null).action,'wait');
 assert.match(recoveryAdvice('PUBLISH_FAILED',[],null).next_step,/原 Publisher/);assert.equal(recoveryAdvice('HANDOFF_FAILED',[],{attempts:3}).action,'limit_reached');
});
const root=new URL('../../../',import.meta.url),read=p=>JSON.parse(fs.readFileSync(new URL(p,root)));
const date='2026-11-19',done=read(`data/publish/${date}.done.json`),canonical=read(`data/daily/${date}.json`),latest={date,publish_commit_sha:done.publish_commit_sha,site_url:done.site_url,receipt:`data/publish/${date}.done.json`,health:{date,publish_commit_sha:done.publish_commit_sha,state:'HEALTHY',checks:{pages:'pass'}}};
test('strict DONE matches real receipt and refuses date, URL, commit data and latest drift',()=>{assert.deepEqual(receiptIssues(date,done,canonical,latest,canonical),[]);for(const patch of [{daily_url:'https://wrong.invalid/'},{date:'2026-11-18'},{canonical:{ids:[],item_count:0}},{qa:{pages:'fail'}}])assert.ok(receiptIssues(date,{...done,...patch},canonical,latest,canonical).length);assert.ok(receiptIssues(date,done,canonical,{...latest,date:'2026-11-18'},canonical).length);assert.ok(receiptIssues(date,done,canonical,latest,{...canonical,items:[]}).length);});
test('controls cannot approve or write arbitrary data; twelve calendar months enforced',()=>{assert.throws(()=>validateControls({schema_version:1,held_urls:[],approved:true}));assert.throws(()=>validateControls({schema_version:1,held_urls:['https://a.test','https://a.test']}));assert.throws(()=>validateControls({schema_version:1,held_urls:['http://a.test']}));assert.equal(recentSource('2025-11-19',date),true);assert.equal(recentSource('2025-11-18',date),false);assert.equal(recentSource('2026-02-30',date),false);assert.equal(recentSource('2026-11-20',date),false);assert.equal(taipeiDate(new Date('2026-11-18T23:50:00Z')),date);});
function repo(files){return async p=>{if(p==='/git/ref/heads/main')return{object:{sha:'a'.repeat(40)}};const key=p.split('?')[0].replace('/contents/','');if(!(key in files))throw new Error('repository_404');return{sha:'b'.repeat(40),content:Buffer.from(JSON.stringify(files[key])).toString('base64')};};}
test('failed review inventory is unknown, not zero available reserve',async()=>{
 const base=repo({}),github=async p=>{if(p.startsWith('/contents/data/editorial-reviews?'))throw Error('repository_403');return base(p);};
 const r=await operations(github,async()=>[],new Date('2026-11-19T00:00:00Z'));
 assert.equal(r.reserve_complete,false);assert.equal(r.reserve_count,null);assert.equal(r.reserve_days,null);assert.match(r.issues.join(''),/索引讀取不完整/);
});
test('missing Actions is unknown; skipped is not genuine; active publisher wins',async()=>{const github=repo({});const now=new Date('2026-11-19T00:00:00Z');assert.equal((await operations(github,async()=>{throw Error('rate limit');},now)).state,'UNKNOWN');assert.equal((await operations(github,async()=>[{name:'Autonomous daily Collector',status:'completed',conclusion:'skipped'}],now)).state,'NOT_STARTED');assert.equal((await operations(github,async()=>[{name:'Canonical intelligence publish',status:'in_progress'}],now)).state,'PUBLISHING');});
test('published rows are hidden and holds remain manageable without a current queue',async()=>{const files={'config/editorial-selection.json':{schema_version:1,held_urls:['https://example.com/hold']},'data/candidates/rolling-backlog.json':{items:[{id:'used',source_url:'https://example.com/used'},{id:'old',source_url:'https://example.com/old',source_published_at:'2024-01-01'}]},'data/candidates/published-registry-snapshot.json':{published_sources:[{id:'used',source_url:'https://example.com/used'}]}};const r=await operations(repo(files),async()=>[],new Date('2026-11-19T00:00:00Z'));assert.equal(r.queue[0].state,'held');assert.equal(r.reserve.length,1);assert.equal(r.reserve[0].state,'date_ineligible');assert.equal(r.reserve_count,0);});
