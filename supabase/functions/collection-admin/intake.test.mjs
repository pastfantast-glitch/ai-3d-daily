import test from 'node:test';
import assert from 'node:assert/strict';
import {classifyURL,saveRecommendation,INTAKE_PATH} from './intake.mjs';
import {encode} from './settings-flow.mjs';
const settings={sources:[{id:'80-level',base_url:'https://80.lv',name:'80 Level',enabled:true,topic_ids:['ai-3d']}]};
test('lookup distinguishes pending, reserve, published and missing without fetching the source',()=>{
 const url='https://80.lv/articles/example';
 assert.equal(classifyURL(url,{queue:[{source_url:url,state:'awaiting_review'}]},settings).state,'awaiting_review');
 assert.equal(classifyURL(url,{registry:[{source_url:url}]},settings).state,'published');
 assert.equal(classifyURL(url,{reserve:[{source_url:url,state:'recheck_required'}]},settings).can_recommend,false);
 assert.equal(classifyURL(url,{},settings).can_recommend,true);
 assert.equal(classifyURL('https://unknown.example/article',{},settings).can_recommend,false);
 assert.throws(()=>classifyURL('https://127.0.0.1/private',{},settings));
});
test('recommendation has one fixed-path SHA guarded write, duplicate and conflict never retry',async()=>{
 const head='a'.repeat(40),sha='b'.repeat(40),url='https://80.lv/articles/example',writes=[];
 let items=[];
 const github=async(path,method,body)=>{
  if(path==='/git/ref/heads/main')return {object:{sha:head}};
  if(method==='PUT'){writes.push({path,body});return {content:{sha:'c'.repeat(40)},commit:{html_url:'https://github.com/test'}};}
  return {sha,content:encode({schema_version:1,items})};
 };
 await assert.rejects(saveRecommendation(github,{url,head,sha:'d'.repeat(40)},settings));assert.equal(writes.length,0);
 await assert.rejects(saveRecommendation(github,{url:'https://evil.example/a',head,sha},settings));
 await saveRecommendation(github,{url,head,sha},settings);assert.equal(writes.length,1);assert.equal(writes[0].path,'/contents/'+INTAKE_PATH);assert.equal(writes[0].body.sha,sha);
 items=[{source_url:url}];assert.equal((await saveRecommendation(github,{url,head,sha},settings)).unchanged,true);assert.equal(writes.length,1);
});
