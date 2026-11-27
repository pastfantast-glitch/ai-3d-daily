import test from 'node:test';
import assert from 'node:assert/strict';
import {layoutDocument,layoutStore,movedNodes,alignedNodes,arrangedNodes} from './admin-graph-layout.mjs';
const node=(key,x,y,width=100)=>({key,x,y,width,height:100});
const doc=()=>({schema:3,positions:[['source:a',{x:-300,y:400}]],camera:{x:-100,y:10,zoom:.8},mode:'configuration',navigation:{locks:['source:a'],views:[],groups:[{name:'群組',ids:['source:a']}]}});
test('layout payload strips settings and credentials and rejects corrupt positions',()=>{
  const d=doc();d.settings={sources:[]};d.token='secret';d.navigation.token='secret';assert.equal(JSON.stringify(layoutDocument(d)).includes('secret'),false);
  d.positions.push(['source:a',{x:0,y:0}]);assert.throws(()=>layoutDocument(d));d.positions.pop();d.camera.x=Infinity;assert.throws(()=>layoutDocument(d));
});
test('selected movement preserves offsets and excludes fixed and unselected nodes',()=>{
  const nodes=[node('source:a',-100,20),node('source:b',200,90),node('topic:c',400,900)],ids=new Set(nodes.map(n=>n.key));
  const moved=movedNodes(nodes,ids,k=>k==='topic:c',50,-150);
  assert.deepEqual(moved,[['source:a',{x:-50,y:-130}],['source:b',{x:250,y:-60}]]);assert.equal(nodes[0].x,-100);
});
test('align uses fixed anchor, spacing handles variable widths and fixed spans',()=>{
  const nodes=[node('source:a',0,10,100),node('source:b',180,50,50),node('source:c',500,90,100),node('source:d',900,120,200)],ids=new Set(nodes.map(n=>n.key));
  assert.deepEqual(alignedNodes(nodes,ids,k=>k==='source:c','left').map(x=>x[1].x),[500,500,500]);
  const spaced=alignedNodes(nodes,ids,()=>false,'horizontal');assert.equal(spaced[0][1].x,100+(900-250)/3);assert.equal(spaced[1][1].x,spaced[0][1].x+50+(900-250)/3);
  assert.deepEqual(alignedNodes(nodes,ids,k=>k==='source:c','horizontal'),[['source:b',{x:275,y:50}]]);
});
test('auto layout preserves pinned/unselected nodes and leaves nonoverlapping columns',()=>{
  const nodes=[node('source:a',50,30),node('source:b',55,30),node('topic:c',440,30),node('topic:d',440,60),node('stage:top5',700,30)],links=[['source:a','topic:d'],['source:b','topic:c']];
  const moved=arrangedNodes(nodes,links,null,k=>k==='topic:c');assert.ok(!moved.some(([k])=>k==='topic:c'));
  const result=nodes.map(n=>({...n,...new Map(moved).get(n.key)}));
  for(const a of result)for(const b of result)if(a!==b)assert.ok(a.x+a.width<=b.x||b.x+b.width<=a.x||a.y+a.height<=b.y||b.y+b.height<=a.y);
  assert.equal(arrangedNodes(nodes,links,new Set(['source:a']),()=>false).length,1);
  assert.deepEqual(arrangedNodes(nodes,links,null,k=>k==='topic:c'),moved);
});
test('account save restores across new sessions and conflicts cannot silently overwrite',async()=>{
  let remote={layout:null,revision:0,updated_at:null};const calls=[];
  const rpc=async(name,p)=>{calls.push(name);if(name==='get_admin_graph_layout')return structuredClone(remote);if(p.p_expected_revision!==remote.revision)throw Error('layout_version_conflict');remote={layout:structuredClone(p.p_layout),revision:remote.revision+1,updated_at:'2026-11-27T10:00:00Z'};return structuredClone(remote);};
  const a=layoutStore(rpc),b=layoutStore(rpc);await assert.rejects(()=>a.save(doc()));await a.load();await b.load();await a.save(doc());assert.equal(a.dirty(doc()),false);
  await assert.rejects(()=>b.save(doc()),/conflict/);assert.equal(remote.revision,1);
  const afterLogin=layoutStore(rpc);assert.deepEqual((await afterLogin.load()).layout,layoutDocument(doc()));assert.equal(afterLogin.dirty(doc()),false);
  assert.ok(calls.every(x=>['get_admin_graph_layout','save_admin_graph_layout'].includes(x)));
});
