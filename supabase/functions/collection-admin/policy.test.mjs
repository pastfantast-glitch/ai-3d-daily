import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {validateSettings,publicURL,publicIP,ORIGIN} from './policy.mjs';
import {handle} from './index.ts';
const settings=JSON.parse(fs.readFileSync(new URL('../../../config/collection-admin.json',import.meta.url)));
test('production config valid; secrets, private URLs and removal of primary rejected',()=>{
  validateSettings(settings);
  for(const url of ['http://example.com','https://127.0.0.1','https://[::1]','https://user:pass@example.com','https://x.local','https://0x7f000001'])assert.equal(publicURL(url),false,url);
  for(const ip of ['127.0.0.1','10.0.1.1','169.254.169.254','100.64.1.1','::1','::ffff:127.0.0.1','2001:db8::1'])assert.equal(publicIP(ip),false,ip);
  assert.equal(publicIP('8.8.8.8'),true);
  assert.throws(()=>validateSettings({...settings,token:'never-save'}));
  const next=structuredClone(settings);next.topics[0].enabled=false;assert.throws(()=>validateSettings(next));
});
test('owner authorization, version conflicts and fixed-path writes are enforced by actual handler',async()=>{
  const original=globalThis.fetch,deno=globalThis.Deno;let isOwner=false,conflict=false,writes=[];
  globalThis.Deno={env:{get:k=>({SUPABASE_URL:'https://test.supabase.co',SUPABASE_SERVICE_ROLE_KEY:'fixture-service',COLLECTION_GITHUB_TOKEN:'fixture-repo'})[k]}};
  globalThis.fetch=async(url,opts={})=>{
    if(url.endsWith('/auth/v1/user'))return Response.json({id:'test-user'});
    if(url.includes('/app_owner?'))return Response.json([{user_id:isOwner?'test-user':'other-user'}]);
    if(opts.method==='PUT'){writes.push({url,body:JSON.parse(opts.body),headers:opts.headers});return conflict?Response.json({}, {status:409}):Response.json({content:{sha:'b'.repeat(40)},commit:{html_url:'https://github.com/fixture/commit'}});}
    throw new Error('Unexpected request: '+url);
  };
  const call=(body,origin=ORIGIN,auth=true)=>handle(new Request('https://test/admin',{method:'POST',headers:{Origin:origin,...(auth?{Authorization:'Bearer '+'a'.repeat(30)}:{})},body:JSON.stringify(body)}));
  try{
    assert.equal((await call({op:'save'},'https://evil.example')).status,403);
    assert.equal((await call({op:'save'},ORIGIN,false)).status,403);
    assert.equal((await call({op:'save'})).status,403);assert.equal(writes.length,0);
    isOwner=true;
    assert.equal((await call({op:'save',settings})).status,400);assert.equal(writes.length,0);
    const response=await call({op:'save',sha:'a'.repeat(40),settings,path:'data/publish/fake.done.json'});
    assert.equal(response.status,200);assert.equal(writes.length,1);
    assert.ok(writes[0].url.endsWith('/contents/config/collection-admin.json'));
    assert.equal(writes[0].body.sha,'a'.repeat(40));assert.equal(writes[0].body.branch,'main');
    assert.deepEqual(JSON.parse(Buffer.from(writes[0].body.content,'base64')),settings);
    conflict=true;assert.equal((await call({op:'save',sha:'a'.repeat(40),settings})).status,409);
    assert.equal(writes.length,2); // Exactly one attempted write per request; no retries or alternative writer.
    assert.equal((await call({op:'dispatch'})).status,400);
    assert.equal((await call({op:'probe',url:'http://127.0.0.1'})).status,503);
  }finally{globalThis.fetch=original;globalThis.Deno=deno;}
});
