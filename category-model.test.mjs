import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {categories,projectSettings,unprojectSettings,categoryItems,visibleCategories,validateCategories} from './category-model.mjs';
import {validateSettings} from './supabase/functions/collection-admin/policy.mjs';
import {connectTopic,moveConnection,validateGraphDraft} from './admin-graph-model.mjs';
import {mergeSettings} from './admin-studio-model.mjs';
const raw=JSON.parse(readFileSync(new URL('./config/collection-admin.json',import.meta.url)));
const daily=JSON.parse(readFileSync(new URL('./data/daily/2026-11-27.json',import.meta.url)));
test('legacy six categories become editable nodes without changing canonical topic bindings',()=>{
 const view=projectSettings(raw),back=unprojectSettings(view);validateSettings(back);
 assert.equal(view.topics.length,6);assert.deepEqual(back.sources,raw.sources);assert.deepEqual(back.topics,raw.topics);
 for(const c of categories(raw))assert.deepEqual(categoryItems(daily.items,c,raw).map(i=>i.id),daily.items.filter(i=>i.category===c.id).map(i=>i.id));
 assert.equal(view.topics.some(t=>t.id==='top5'),false);
});
test('connection edits, undo values and remote merge preserve independent collection data',()=>{
 const view=projectSettings(raw),s=view.sources[0],id=view.topics[0].id;
 const changed=connectTopic(view,s.id,id,false),back=unprojectSettings(changed);
 assert(!back.navigation[0].source_ids.includes(s.id));assert(view.sources[0].topic_ids.includes(id));
 assert.deepEqual(back.sources[0].topic_ids,raw.sources[0].topic_ids);
 const remote=structuredClone(view);remote.topics[1].name='Changed name';
 const merged=mergeSettings(view,changed,remote);assert.equal(merged.conflicts.length,0);assert.equal(merged.settings.topics[1].name,'Changed name');validateGraphDraft(merged.settings);
 let disconnected=view;for(const t of view.topics)disconnected=connectTopic(disconnected,s.id,t.id,false);
 assert.equal(disconnected.sources[0].enabled,false);assert.equal(unprojectSettings(disconnected).sources[0].enabled,false);
 assert.throws(()=>moveConnection(view,s.id,id,'top5'));
});
test('multi-category rules deduplicate IDs, honor exclusions and manual corrections, and hide empty tabs',()=>{
 const settings=unprojectSettings(projectSettings(raw));const item=daily.items[0],c=structuredClone(settings.navigation[0]);
 c.id='custom-tab';c.include_terms=['unmatched fixture'];c.manual_urls=[item.source_url];c.hide_empty=true;
 settings.navigation.push(c);validateSettings(settings);
 assert.equal(categoryItems([item,item],c,settings).length,1);assert(visibleCategories(settings,[item]).some(x=>x.id===c.id));
 c.excluded_urls=[item.source_url];assert.equal(categoryItems([item],c,settings).length,0);assert.throws(()=>validateCategories(settings.navigation,settings.sources));
 c.manual_urls=[];assert(!visibleCategories(settings,[item]).some(x=>x.id===c.id));
 c.excluded_urls=[];c.include_terms=[item.title];c.source_ids=[];assert.equal(categoryItems([item],c,settings).length,0);
});
test('published memberships survive paused sources; malformed and empty live supply cannot activate',()=>{
 const s=unprojectSettings(projectSettings(raw)),c=s.navigation.find(c=>c.id===daily.items[0].category);c.source_ids=[];
 assert.equal(categoryItems([daily.items[0]],c,s).length,1);
 for(const c of s.navigation)c.enabled=false;assert.throws(()=>validateSettings(s));validateSettings(s,{draft:true});
 assert.throws(()=>validateCategories([{...categories(raw)[0],id:'top5'}],raw.sources));
});
test('source-language classification survives translation and manual exclusion can correct it',()=>{
 const settings=unprojectSettings(projectSettings(raw));const c={...settings.navigation[0],id:'cloth-workflow',include_terms:['cloth'],source_ids:[]};
 const item={id:'translated',title:'布料製作',source_url:'https://example.com/article',navigation_category_ids:['cloth-workflow']};
 assert.equal(categoryItems([item],c,settings).length,1);
 c.excluded_urls=[item.source_url];assert.equal(categoryItems([item],c,settings).length,0);
});
